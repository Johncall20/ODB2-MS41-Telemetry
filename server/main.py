import asyncio
import json
import os
import re
import time
from typing import Optional, Dict, Callable, Set, Any

from aiohttp import web, WSMsgType
from bleak import BleakClient, BleakScanner

# ========= BLE ELM CONFIG =========
SVC_UUID = "0000fff0-0000-1000-8000-00805f9b34fb"
CH_UUID  = "0000fff1-0000-1000-8000-00805f9b34fb"

TARGET_NAME = os.environ.get("ELM_NAME", "OBDII")
TARGET_MAC  = os.environ.get("ELM_MAC", "").strip()

# timing base
SEND_DELAY_MS   = int(os.environ.get("SEND_DELAY_MS", "8"))
CMD_TIMEOUT_MS  = int(os.environ.get("CMD_TIMEOUT_MS", "700"))
IDLE_DETECT_MS  = int(os.environ.get("IDLE_DETECT_MS", "90"))  # mais alto por padrão (BLE em rajadas)

# anti-flood (gap mínimo + adaptativo)
MIN_CMD_GAP_MS  = int(os.environ.get("MIN_CMD_GAP_MS", "30"))
MAX_CMD_GAP_MS  = int(os.environ.get("MAX_CMD_GAP_MS", "90"))

# idle só vale se recebeu pelo menos isso (evita “cortar cedo”)
MIN_RX_BEFORE_IDLE = int(os.environ.get("MIN_RX_BEFORE_IDLE", "18"))

# flush periódico (para clones que “degradam” com o tempo)
ELM_FLUSH_EVERY_S = int(os.environ.get("ELM_FLUSH_EVERY_S", "0"))  # 0 = desativado
ELM_FLUSH_CMD     = os.environ.get("ELM_FLUSH_CMD", "ATWS")        # ATWS (warm start) é bom

# ========= SERVER CONFIG =========
HTTP_HOST = os.environ.get("HTTP_HOST", "0.0.0.0")
HTTP_PORT = int(os.environ.get("HTTP_PORT", "3000"))

DIST_DIR = os.path.join(os.path.dirname(__file__), "..", "web", "dist")


def hex_only_upper(s: str) -> str:
    s = s.upper()
    return "".join(c for c in s if (c.isdigit() or ("A" <= c <= "F")))


def extract_mode01_bytes(raw: str, pid_hex: str, need_bytes: int) -> Optional[bytes]:
    """
    Extrai bytes do '41 <pid> <data...>'.
    Funciona com ou sem headers (ex 7E8).
    """
    h = hex_only_upper(raw)
    idx = -1

    start = h.find("7E8")
    while start >= 0:
        q = h.find("41" + pid_hex, start)
        if q >= 0:
            idx = q + 4  # skip 41 + pid
            break
        start = h.find("7E8", start + 3)

    if idx < 0:
        q = h.find("41" + pid_hex)
        if q < 0:
            return None
        idx = q + 4

    end = idx + need_bytes * 2
    if end > len(h):
        return None

    out = bytearray()
    for i in range(need_bytes):
        b = h[idx + i * 2: idx + i * 2 + 2]
        out.append(int(b, 16))
    return bytes(out)


class BleElm:
    def __init__(self):
        self.client: Optional[BleakClient] = None

        # RX
        self.rx: str = ""
        self._rx_lock = asyncio.Lock()
        self._rx_event = asyncio.Event()

        # garante 1 comando por vez
        self._cmd_lock = asyncio.Lock()

        # anti-flood adaptativo
        self._last_cmd_t = 0.0
        self._gap_min = MIN_CMD_GAP_MS
        self._gap_max = MAX_CMD_GAP_MS
        self._gap_ms = MIN_CMD_GAP_MS

        # guard contra avalanche de notify tasks
        self._notify_backlog_guard = 0
        self._notify_backlog_guard_lock = asyncio.Lock()

        # flush periódico
        self._last_flush_t = time.time()

    # ===== Notify handling =====
    # Callback do Bleak precisa ser SYNC
    def _notify_cb(self, _char: Any, data: bytearray):
        loop = asyncio.get_running_loop()
        loop.create_task(self._handle_notify(data))

    async def _handle_notify(self, data: bytearray):
        async with self._notify_backlog_guard_lock:
            if self._notify_backlog_guard > 250:
                # se o loop ficou atrasado, dropar algumas notificações
                # é melhor do que deixar tudo travar
                return
            self._notify_backlog_guard += 1

        try:
            chunk = data.decode("ascii", errors="ignore")
            async with self._rx_lock:
                self.rx += chunk
                if len(self.rx) > 2400:
                    self.rx = self.rx[-2048:]
                self._rx_event.set()
        finally:
            async with self._notify_backlog_guard_lock:
                self._notify_backlog_guard -= 1

    async def find_device(self) -> Optional[str]:
        if TARGET_MAC:
            return TARGET_MAC

        for _ in range(10):
            devs = await BleakScanner.discover(timeout=3.0)
            for d in devs:
                if (d.name or "") == TARGET_NAME:
                    return d.address
        return None

    async def connect(self):
        addr = await self.find_device()
        if not addr:
            raise RuntimeError(
                f"ELM BLE not found (name={TARGET_NAME}). "
                f"Set ELM_MAC env var to skip scan."
            )

        self.client = BleakClient(addr)
        ok = await self.client.connect(timeout=15.0)
        if not ok:
            raise RuntimeError("Failed to connect BLE ELM")

        await self.client.start_notify(CH_UUID, self._notify_cb)

    async def disconnect(self):
        if self.client:
            try:
                await self.client.stop_notify(CH_UUID)
            except Exception:
                pass
            try:
                await self.client.disconnect()
            except Exception:
                pass
            self.client = None

    async def clear_rx(self):
        async with self._rx_lock:
            self.rx = ""
            self._rx_event.clear()

    async def wait_for_prompt_or_idle(
        self,
        overall_ms: int,
        idle_ms: int = IDLE_DETECT_MS,
        min_rx_before_idle: int = MIN_RX_BEFORE_IDLE,
    ) -> bool:
        """
        Espera até:
          - receber '>' (prompt), OU
          - ficar idle por idle_ms (mas só se já recebeu min_rx_before_idle), OU
          - timeout overall_ms
        """
        t0 = time.time()
        last_len = 0
        last_change = time.time()

        while (time.time() - t0) * 1000 < overall_ms:
            async with self._rx_lock:
                buf = self.rx

            if ">" in buf:
                return True

            L = len(buf)
            if L != last_len:
                last_len = L
                last_change = time.time()
            else:
                if L >= min_rx_before_idle and (time.time() - last_change) * 1000 > idle_ms:
                    return True

            try:
                await asyncio.wait_for(self._rx_event.wait(), timeout=0.06)
                self._rx_event.clear()
            except asyncio.TimeoutError:
                pass

        return False

    async def _respect_gap(self):
        now = time.time()
        dt = now - self._last_cmd_t
        need = (self._gap_ms / 1000.0) - dt
        if need > 0:
            await asyncio.sleep(need)
        self._last_cmd_t = time.time()

    def _gap_feedback(self, response: str):
        """
        Ajusta o gap adaptativo:
          - se resposta ruim -> aumenta gap (backoff)
          - se resposta ok -> diminui devagar
        """
        up = response.upper()
        h = hex_only_upper(response)

        bad = False
        if not response:
            bad = True
        elif "NO DATA" in up or "STOPPED" in up or "ERROR" in up or "?" in up:
            bad = True
        # se não veio prompt e veio “pouco” é suspeito (idle cortou cedo)
        elif (">" not in response) and (len(h) < 12):
            bad = True

        if bad:
            # cresce mais rápido
            self._gap_ms = min(self._gap_max, int(self._gap_ms * 1.35) + 2)
        else:
            # recupera devagar
            self._gap_ms = max(self._gap_min, self._gap_ms - 1)

    async def send_cmd(self, cmd: str, timeout_ms: int, log: bool = False) -> str:
        if not self.client:
            raise RuntimeError("BLE client not connected")

        async with self._cmd_lock:
            # anti-flood
            await self._respect_gap()

            await self.clear_rx()

            out = (cmd + "\r").encode("ascii", errors="ignore")
            if log:
                print(f">> {cmd} (gap={self._gap_ms}ms)")

            try:
                await self.client.write_gatt_char(CH_UUID, out, response=True)
            except Exception:
                await self.client.write_gatt_char(CH_UUID, out, response=False)

            await asyncio.sleep(SEND_DELAY_MS / 1000.0)

            await self.wait_for_prompt_or_idle(timeout_ms)

            async with self._rx_lock:
                r = self.rx

            if log:
                print("<<", r, "\n")

            # feedback do gap (adaptativo)
            self._gap_feedback(r)

            return r

    async def init_fast_elm(self, log: bool = True) -> bool:
        # sequência padrão
        await self.send_cmd("ATZ", 1500, log)
        await asyncio.sleep(0.8)

        await self.send_cmd("ATE0", 800, log)
        await self.send_cmd("ATL0", 800, log)
        await self.send_cmd("ATS0", 800, log)
        await self.send_cmd("ATH0", 800, log)
        await self.send_cmd("ATSP0", 800, log)
        await self.send_cmd("ATM0", 800, log)
        await self.send_cmd("ATAT1", 800, log)
        await self.send_cmd("ATST14", 800, log)
        await self.send_cmd("ATAL", 800, log)

        r = await self.send_cmd("0100", 1200, log)
        h = hex_only_upper(r)
        if "4100" not in h:
            r = await self.send_cmd("0100", 1200, log)
            h = hex_only_upper(r)
        return "4100" in h

    async def maybe_flush(self) -> bool:
        """
        Flush periódico (opcional) para ELM que degrada com o tempo.
        Retorna True se flush ocorreu.
        """
        if ELM_FLUSH_EVERY_S <= 0:
            return False

        now = time.time()
        if (now - self._last_flush_t) < ELM_FLUSH_EVERY_S:
            return False

        self._last_flush_t = now
        try:
            print(f"[ELM] periodic flush: {ELM_FLUSH_CMD}")
            await self.send_cmd(ELM_FLUSH_CMD, 1200, log=True)
            await asyncio.sleep(0.6)
            ok = await self.init_fast_elm(log=False)
            print("[ELM] re-init after flush:", "OK" if ok else "FAIL")
            return True
        except Exception as e:
            print("[ELM] flush failed:", repr(e))
            return False

    # ===== PID getters =====
    async def get_rpm(self) -> Optional[int]:
        r = await self.send_cmd("010C", CMD_TIMEOUT_MS, False)
        b = extract_mode01_bytes(r, "0C", 2)
        if not b:
            return None
        rpm = ((b[0] << 8) | b[1]) // 4
        return int(rpm)

    async def get_ect(self) -> Optional[int]:
        r = await self.send_cmd("0105", CMD_TIMEOUT_MS, False)
        b = extract_mode01_bytes(r, "05", 1)
        if not b:
            return None
        return int(b[0]) - 40

    async def get_iat(self) -> Optional[int]:
        r = await self.send_cmd("010F", CMD_TIMEOUT_MS, False)
        b = extract_mode01_bytes(r, "0F", 1)
        if not b:
            return None
        return int(b[0]) - 40

    async def get_vss(self) -> Optional[int]:
        r = await self.send_cmd("010D", CMD_TIMEOUT_MS, False)
        b = extract_mode01_bytes(r, "0D", 1)
        if not b:
            return None
        return int(b[0])

    async def get_map(self) -> Optional[int]:
        r = await self.send_cmd("010B", CMD_TIMEOUT_MS, False)
        b = extract_mode01_bytes(r, "0B", 1)
        if not b:
            return None
        return int(b[0])

    async def get_tps(self) -> Optional[float]:
        r = await self.send_cmd("0111", CMD_TIMEOUT_MS, False)
        b = extract_mode01_bytes(r, "11", 1)
        if not b:
            return None
        return float(b[0]) * 100.0 / 255.0

    async def get_lambda(self) -> Optional[Dict[str, float]]:
        r = await self.send_cmd("0144", CMD_TIMEOUT_MS, False)
        b = extract_mode01_bytes(r, "44", 2)
        if not b:
            return None
        v = (b[0] << 8) | b[1]
        lam = float(v) / 32768.0
        afr = lam * 14.7
        return {"lambda": lam, "afr": afr}


async def run_telemetry(elm: BleElm, broadcast_fire_and_forget: Callable[[dict], None]):
    """
    Polling com prioridade RPM/Lambda, mas com loop bem comportado.
    """
    steps = [
        ("rpm", elm.get_rpm),
        ("lambda", elm.get_lambda),
        ("vss", elm.get_vss),
        ("rpm", elm.get_rpm),
        ("lambda", elm.get_lambda),
        ("tps", elm.get_tps),
        ("rpm", elm.get_rpm),
        ("lambda", elm.get_lambda),
        ("map_kpa", elm.get_map),
        ("iat", elm.get_iat),
        ("rpm", elm.get_rpm),
        ("lambda", elm.get_lambda),
        ("ect", elm.get_ect),
    ]

    state: Dict[str, object] = {
        "rpm": -1,
        "vss": -1,
        "tps": -1.0,
        "ect": -999,
        "iat": -999,
        "map_kpa": -1,
        "lambda": -1.0,
        "afr": -1.0,
        "ts": 0,
        "gap_ms": MIN_CMD_GAP_MS,
    }

    last_push = 0.0
    i = 0

    while True:
        # flush periódico se ativado
        await elm.maybe_flush()

        t = time.time()
        state["ts"] = int(t * 1000)
        state["gap_ms"] = elm._gap_ms

        key, fn = steps[i]
        i = (i + 1) % len(steps)

        try:
            val = await fn()
        except Exception:
            val = None

        if val is None:
            pass
        elif isinstance(val, dict):
            state["lambda"] = float(val["lambda"])
            state["afr"] = float(val["afr"])
        else:
            state[key] = val

        # push ~120ms
        if (t - last_push) >= 0.12:
            last_push = t
            broadcast_fire_and_forget({"type": "telemetry", "data": state})

        # yield mínimo
        await asyncio.sleep(0.001)


async def main():
    ws_clients: Set[web.WebSocketResponse] = set()

    # ---- Broadcast que não trava o loop do BLE ----
    _send_lock = asyncio.Lock()
    _send_busy = False

    async def _broadcast_send(payload: dict):
        nonlocal _send_busy
        async with _send_lock:
            if _send_busy:
                return
            _send_busy = True

        try:
            if not ws_clients:
                return

            dead = []
            text = json.dumps(payload)

            for c in list(ws_clients):
                try:
                    await asyncio.wait_for(c.send_str(text), timeout=0.12)
                except Exception:
                    dead.append(c)

            for d in dead:
                ws_clients.discard(d)
        finally:
            async with _send_lock:
                _send_busy = False

    def broadcast_fire_and_forget(payload: dict):
        asyncio.get_running_loop().create_task(_broadcast_send(payload))

    async def ws_handler(request):
        ws = web.WebSocketResponse(heartbeat=20)
        await ws.prepare(request)
        ws_clients.add(ws)
        await ws.send_json({"type": "status", "state": "connected"})
        try:
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    # futuro: comandos/controle
                    pass
        finally:
            ws_clients.discard(ws)
        return ws

    async def telemetry_task():
        while True:
            elm = BleElm()
            try:
                print("[BLE] connecting...")
                await elm.connect()
                print("[BLE] connected.")

                ok = await elm.init_fast_elm(log=True)
                if not ok:
                    print("[ELM] init failed (no 0100). Retrying in 2s...")
                    await elm.disconnect()
                    await asyncio.sleep(2.0)
                    continue

                print("[ELM] READY. Streaming telemetry.")
                broadcast_fire_and_forget({"type": "status", "state": "elm_ready"})

                await run_telemetry(elm, broadcast_fire_and_forget)

            except Exception as e:
                print("[ERR]", repr(e))
                broadcast_fire_and_forget({"type": "status", "state": "offline", "error": str(e)})

                try:
                    await elm.disconnect()
                except Exception:
                    pass

                await asyncio.sleep(2.0)

    # ---- HTTP server ----
    app = web.Application()
    app.router.add_get("/ws", ws_handler)

    if os.path.isdir(DIST_DIR):
        app.router.add_static("/", DIST_DIR, show_index=True)
    else:
        async def root(_):
            return web.Response(
                text="web/dist not found. Build the frontend first (see README).",
                content_type="text/plain"
            )
        app.router.add_get("/", root)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, HTTP_HOST, HTTP_PORT)
    await site.start()

    print(f"[HTTP] http://{HTTP_HOST}:{HTTP_PORT}/  (serving {DIST_DIR})")
    print(f"[WS]   ws://{HTTP_HOST}:{HTTP_PORT}/ws")

    await telemetry_task()


if __name__ == "__main__":
    asyncio.run(main())