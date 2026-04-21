import asyncio
import os
import time
from typing import Optional, Dict, Any

from bleak import BleakClient, BleakScanner

# ========= BLE ELM CONFIG =========
SVC_UUID = "0000fff0-0000-1000-8000-00805f9b34fb"
CH_UUID  = "0000fff1-0000-1000-8000-00805f9b34fb"

TARGET_NAME = os.environ.get("ELM_NAME", "OBDII")
TARGET_MAC  = os.environ.get("ELM_MAC", "").strip()

SEND_DELAY_MS   = int(os.environ.get("SEND_DELAY_MS", "8"))
CMD_TIMEOUT_MS  = int(os.environ.get("CMD_TIMEOUT_MS", "700"))
IDLE_DETECT_MS  = int(os.environ.get("IDLE_DETECT_MS", "90"))
MIN_CMD_GAP_MS  = int(os.environ.get("MIN_CMD_GAP_MS", "30"))
MAX_CMD_GAP_MS  = int(os.environ.get("MAX_CMD_GAP_MS", "90"))
MIN_RX_BEFORE_IDLE = int(os.environ.get("MIN_RX_BEFORE_IDLE", "18"))


def hex_only_upper(s: str) -> str:
    s = s.upper()
    return "".join(c for c in s if (c.isdigit() or ("A" <= c <= "F")))


def extract_mode01_bytes(raw: str, pid_hex: str, need_bytes: int) -> Optional[bytes]:
    h = hex_only_upper(raw)
    idx = -1

    start = h.find("7E8")
    while start >= 0:
        q = h.find("41" + pid_hex, start)
        if q >= 0:
            idx = q + 4
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
        self.rx: str = ""
        self._rx_lock = asyncio.Lock()
        self._rx_event = asyncio.Event()
        self._cmd_lock = asyncio.Lock()
        self._last_cmd_t = 0.0
        self._gap_min = MIN_CMD_GAP_MS
        self._gap_max = MAX_CMD_GAP_MS
        self._gap_ms = MIN_CMD_GAP_MS

    def _notify_cb(self, _char: Any, data: bytearray):
        loop = asyncio.get_running_loop()
        loop.create_task(self._handle_notify(data))

    async def _handle_notify(self, data: bytearray):
        chunk = data.decode("ascii", errors="ignore")
        async with self._rx_lock:
            self.rx += chunk
            if len(self.rx) > 2400:
                self.rx = self.rx[-2048:]
            self._rx_event.set()

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
                f"ELM BLE not found (name={TARGET_NAME}). Set ELM_MAC env var to skip scan."
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

    async def wait_for_prompt_or_idle(self, overall_ms: int) -> bool:
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
                if L >= MIN_RX_BEFORE_IDLE and (time.time() - last_change) * 1000 > IDLE_DETECT_MS:
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
        up = response.upper()
        h = hex_only_upper(response)

        bad = False
        if not response:
            bad = True
        elif "NO DATA" in up or "STOPPED" in up or "ERROR" in up or "?" in up:
            bad = True
        elif (">" not in response) and (len(h) < 12):
            bad = True

        if bad:
            self._gap_ms = min(self._gap_max, int(self._gap_ms * 1.35) + 2)
        else:
            self._gap_ms = max(self._gap_min, self._gap_ms - 1)

    async def send_cmd(self, cmd: str, timeout_ms: int, log: bool = False) -> str:
        if not self.client:
            raise RuntimeError("BLE client not connected")

        async with self._cmd_lock:
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

            self._gap_feedback(r)
            return r

    async def init_fast_elm(self, log: bool = True) -> bool:
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

    async def get_rpm(self) -> Optional[int]:
        r = await self.send_cmd("010C", CMD_TIMEOUT_MS, False)
        b = extract_mode01_bytes(r, "0C", 2)
        if not b:
            return None
        return int(((b[0] << 8) | b[1]) // 4)

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


async def main():
    elm = BleElm()
    await elm.connect()
    try:
        ok = await elm.init_fast_elm(log=True)
        if not ok:
            raise RuntimeError("Falha no init do ELM")

        while True:
            rpm = await elm.get_rpm()
            vss = await elm.get_vss()
            ect = await elm.get_ect()
            iat = await elm.get_iat()
            tps = await elm.get_tps()
            lamb = await elm.get_lambda()

            print({
                "rpm": rpm,
                "vss": vss,
                "ect": ect,
                "iat": iat,
                "tps": tps,
                "lambda": lamb,
            })
            await asyncio.sleep(0.2)
    finally:
        await elm.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
