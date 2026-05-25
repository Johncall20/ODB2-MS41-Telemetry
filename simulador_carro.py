
import asyncio
import json
import os
import sys
import time
import math
from typing import Dict, Set

from aiohttp import web

DIST_DIR = os.environ.get(
    "DIST_DIR",
    os.path.join(os.path.dirname(__file__), "web", "dist"),
)

HTTP_HOST = os.environ.get("HTTP_HOST", "0.0.0.0")
HTTP_PORT = int(os.environ.get("HTTP_PORT", "3000"))


class CarroSimulado:
    # Relacoes de marcha (1a a 5a) + diferencial. Valores tipicos.
    MARCHAS = [3.50, 2.10, 1.40, 1.00, 0.80]
    DIFERENCIAL = 3.45
    RAIO_PNEU_M = 0.31           # raio do pneu em metros
    RPM_MARCHA_LENTA = 850       # marcha lenta
    RPM_MAXIMO = 7000            # corte (redline)
    RPM_CORTE = 6800             # limitador

    def __init__(self):
        self.motor_ligado = True
        self.rpm = self.RPM_MARCHA_LENTA
        self.marcha = 1           # 0 = neutro, 1..5
        self.velocidade = 0.0     # km/h

        # entradas do "motorista" (0.0 a 1.0)
        self.acelerador = 0.0
        self.freio = 0.0
        self.embreagem = False    # True = desengatada

        # parametros do motor
        self.temp_motor = 20.0    # ECT - comeca fria (temperatura ambiente)
        self.temp_admissao = 20.0 # IAT
        self.tps = 0.0            # posicao da borboleta (%)
        self.map_kpa = 30.0       # pressao no coletor (kPa)
        self.lambda_ = 1.0
        self.afr = 14.7
        self.avanco = 10.0        # avanco de ignicao (graus)
        self.bateria = 12.4       # tensao da bateria (V)

        self._t0 = time.time()

    def rpm_para_velocidade(self) -> float:
        """Calcula a velocidade (km/h) a partir do RPM e da marcha atual."""
        if self.marcha == 0 or self.embreagem:
            return self.velocidade  # neutro/embreagem: velocidade "livre"
        rel = self.MARCHAS[self.marcha - 1] * self.DIFERENCIAL
        # rpm da roda = rpm motor / relacao
        rpm_roda = self.rpm / rel
        # circunferencia do pneu
        circ = 2 * math.pi * self.RAIO_PNEU_M
        # m/min -> km/h
        vel = rpm_roda * circ * 60.0 / 1000.0
        return vel

    def velocidade_para_rpm(self) -> float:
        """Quando engatado, o RPM e ditado pela velocidade e pela marcha."""
        rel = self.MARCHAS[self.marcha - 1] * self.DIFERENCIAL
        circ = 2 * math.pi * self.RAIO_PNEU_M
        rpm_roda = (self.velocidade * 1000.0 / 60.0) / circ
        return rpm_roda * rel

    def passo(self, dt: float):
        """Avanca a simulacao em dt segundos."""
        if not self.motor_ligado:
            self.rpm = max(0.0, self.rpm - 4000 * dt)
            self.tps = 0.0
            self.map_kpa = 101.0
            self.bateria = 12.2
            self.velocidade = max(0.0, self.velocidade - 8.0 * dt)
            return

        # ---- TPS reflete o acelerador (com pequena suavizacao) ----
        alvo_tps = self.acelerador * 100.0
        self.tps += (alvo_tps - self.tps) * min(1.0, dt * 8.0)

        engatado = (self.marcha != 0) and (not self.embreagem)

        if not engatado:
            # ---- Em neutro/embreagem: RPM responde direto ao acelerador ----
            alvo_rpm = self.RPM_MARCHA_LENTA + self.acelerador * (self.RPM_CORTE - self.RPM_MARCHA_LENTA)
            taxa = 6.0 if self.acelerador > 0.05 else 2.5
            self.rpm += (alvo_rpm - self.rpm) * min(1.0, dt * taxa)
            # carro desacelera sozinho (atrito)
            self.velocidade = max(0.0, self.velocidade - 6.0 * dt)
        else:
            # ---- Engatado: forca do motor acelera o carro ----
            rel = self.MARCHAS[self.marcha - 1] * self.DIFERENCIAL
            # torque disponivel cai em rpm muito alto e muito baixo
            fator_rpm = max(0.2, 1.0 - abs(self.rpm - 3500) / 5000.0)
            forca = self.acelerador * fator_rpm * (rel / 5.0)
            # aceleracao do carro (km/h por segundo), simplificada
            acel = forca * 22.0
            # resistencia (ar + rolamento) cresce com a velocidade
            resist = (self.velocidade ** 2) * 0.0009 + self.velocidade * 0.03 + 0.6
            self.velocidade += (acel - resist) * dt
            # freio
            self.velocidade -= self.freio * 35.0 * dt
            self.velocidade = max(0.0, self.velocidade)
            # RPM segue a velocidade pela marcha
            self.rpm = self.velocidade_para_rpm()
            self.rpm = max(self.RPM_MARCHA_LENTA, self.rpm)

        # ---- Limitador de giro ----
        if self.rpm > self.RPM_CORTE:
            self.rpm = self.RPM_CORTE - 150  # "bate no corte" e cai um pouco

        # ---- MAP: depende da carga (acelerador) e do RPM ----
        # aspirado: vacuo alto (kPa baixo) em marcha lenta, ~100 kPa em WOT
        alvo_map = 30.0 + self.tps * 0.70   # 30 kPa (vacuo) ate ~100 kPa
        self.map_kpa += (alvo_map - self.map_kpa) * min(1.0, dt * 6.0)

        # ---- Mistura (lambda/AFR): enriquece ao acelerar forte ----
        if self.tps > 80:
            alvo_lambda = 0.88        # rica em carga total
        elif self.tps < 5:
            alvo_lambda = 1.00        # estequiometrica em marcha lenta
        else:
            alvo_lambda = 0.97
        self.lambda_ += (alvo_lambda - self.lambda_) * min(1.0, dt * 4.0)
        self.afr = self.lambda_ * 14.7

        # ---- Avanco de ignicao: aumenta com RPM, recua em carga alta ----
        self.avanco = 8.0 + (self.rpm / self.RPM_MAXIMO) * 35.0 - (self.tps / 100.0) * 8.0

        # ---- Temperatura do motor: sobe ate ~90C e estabiliza ----
        if self.temp_motor < 90.0:
            self.temp_motor += (4.0 + self.rpm / 2000.0) * dt
        else:
            # oscila um pouco em torno de 90-95 conforme a carga
            alvo = 88.0 + (self.tps / 100.0) * 9.0
            self.temp_motor += (alvo - self.temp_motor) * min(1.0, dt * 0.3)

        # ---- Temperatura de admissao: ambiente + calor do motor ----
        alvo_iat = 25.0 + (self.temp_motor - 20.0) * 0.25 + (self.tps / 100.0) * 10.0
        self.temp_admissao += (alvo_iat - self.temp_admissao) * min(1.0, dt * 0.5)

        # ---- Bateria: ~14.2V com motor girando (alternador) ----
        self.bateria = 13.8 + min(0.6, self.rpm / 12000.0)

    def trocar_marcha(self, delta: int):
        nova = self.marcha + delta
        nova = max(0, min(len(self.MARCHAS), nova))
        self.marcha = nova

    def estado_telemetria(self) -> Dict:
        """Monta o dicionario no MESMO formato do servidor real (server/main.py)."""
        return {
            "rpm": int(self.rpm),
            "vss": int(self.velocidade),
            "tps": round(self.tps, 1),
            "map_kpa": round(self.map_kpa, 1),
            "iat": int(self.temp_admissao),
            "ect": int(self.temp_motor),
            "lambda": round(self.lambda_, 3),
            "afr": round(self.afr, 2),
            "ignAdv": round(self.avanco, 1),
            "battery": round(self.bateria, 2),
            "gear": self.marcha if self.marcha > 0 else 0,
            "ts": int(time.time() * 1000),
        }


class Teclado:
    def __init__(self):
        self.ativo: Dict[str, float] = {}
        self._win = (os.name == "nt")
        if not self._win:
            import termios, tty  # noqa
            self._termios = termios
            self._tty = tty
            self._fd = sys.stdin.fileno()
            self._old = termios.tcgetattr(self._fd)

    def iniciar(self):
        if not self._win:
            self._tty.setcbreak(self._fd)

    def restaurar(self):
        if not self._win:
            self._termios.tcsetattr(self._fd, self._termios.TCSADRAIN, self._old)

    def _ler_bytes(self):
        """Le todas as teclas disponiveis sem bloquear. Retorna lista de tokens."""
        tokens = []
        if self._win:
            import msvcrt
            while msvcrt.kbhit():
                ch = msvcrt.getwch()
                if ch in ("\x00", "\xe0"):       # prefixo de tecla especial
                    ch2 = msvcrt.getwch()
                    tokens.append({"H": "UP", "P": "DOWN", "K": "LEFT", "M": "RIGHT"}.get(ch2, ""))
                else:
                    tokens.append(ch.lower())
        else:
            import select
            while select.select([sys.stdin], [], [], 0)[0]:
                ch = sys.stdin.read(1)
                if ch == "\x1b":                 # sequencia de escape (setas)
                    seq = sys.stdin.read(2)
                    tokens.append({"[A": "UP", "[B": "DOWN", "[D": "LEFT", "[C": "RIGHT"}.get(seq, ""))
                else:
                    tokens.append(ch.lower())
        return [t for t in tokens if t]

    def atualizar(self) -> list:
        """Atualiza o estado das teclas seguradas e retorna eventos de toque unico."""
        agora = time.time()
        eventos = []
        for tok in self._ler_bytes():
            if tok in ("UP", "DOWN", "SPACE", " "):
                self.ativo[tok if tok != " " else "SPACE"] = agora
            else:
                eventos.append(tok)  # toque unico (marcha, ligar, sair)
        # expira teclas seguradas (0.15s sem novo evento = soltou)
        for k in list(self.ativo.keys()):
            if agora - self.ativo[k] > 0.15:
                del self.ativo[k]
        return eventos

    def segurando(self, tecla: str) -> bool:
        return tecla in self.ativo


async def main():
    carro = CarroSimulado()
    ws_clients: Set[web.WebSocketResponse] = set()

    # ---- WebSocket: mesmo endpoint /ws do servidor real ----
    async def ws_handler(request):
        ws = web.WebSocketResponse(heartbeat=20)
        await ws.prepare(request)
        ws_clients.add(ws)
        await ws.send_json({"type": "status", "state": "connected"})
        await ws.send_json({"type": "status", "state": "elm_ready"})
        try:
            async for _ in ws:
                pass
        finally:
            ws_clients.discard(ws)
        return ws

    async def broadcast(payload: dict):
        if not ws_clients:
            return
        texto = json.dumps(payload)
        mortos = []
        for c in list(ws_clients):
            try:
                await c.send_str(texto)
            except Exception:
                mortos.append(c)
        for d in mortos:
            ws_clients.discard(d)

    # ---- Loop da fisica + teclado ----
    async def loop_simulacao():
        tecl = Teclado()
        tecl.iniciar()
        ultimo = time.time()
        ultimo_push = 0.0
        try:
            print("\n" + "=" * 60)
            print(" SIMULADOR DE CARRO - OBD2 + MS41 Telemetry")
            print("=" * 60)
            print(" Abra no navegador:  http://localhost:%d" % HTTP_PORT)
            print("-" * 60)
            print(" CONTROLES:")
            print("   Seta CIMA   = acelerar (segure)")
            print("   Seta BAIXO  = frear")
            print("   Seta DIREITA= sobe marcha    Seta ESQUERDA = desce marcha")
            print("   ESPACO      = embreagem (segure)   S = liga/desliga   Q = sair")
            print("=" * 60 + "\n")

            while True:
                agora = time.time()
                dt = agora - ultimo
                ultimo = agora

                # --- processa teclado ---
                eventos = tecl.atualizar()
                for ev in eventos:
                    if ev == "q":
                        print("\nEncerrando simulador...")
                        for c in list(ws_clients):
                            await c.close()
                        asyncio.get_running_loop().stop()
                        return
                    elif ev == "s":
                        carro.motor_ligado = not carro.motor_ligado
                    elif ev == "RIGHT":
                        carro.trocar_marcha(+1)
                    elif ev == "LEFT":
                        carro.trocar_marcha(-1)

                carro.acelerador = 1.0 if tecl.segurando("UP") else 0.0
                carro.freio = 1.0 if tecl.segurando("DOWN") else 0.0
                carro.embreagem = tecl.segurando("SPACE")

                # --- avanca a fisica ---
                carro.passo(dt)

                # --- envia telemetria ~a cada 100ms ---
                if (agora - ultimo_push) >= 0.10:
                    ultimo_push = agora
                    await broadcast({"type": "telemetry", "data": carro.estado_telemetria()})
                    # status no terminal (uma linha que se atualiza)
                    m = carro.marcha if carro.marcha > 0 else "N"
                    estado = "ON " if carro.motor_ligado else "OFF"
                    sys.stdout.write(
                        "\r [%s] RPM:%5d  Vel:%3d km/h  Marcha:%s  TPS:%3d%%  ECT:%3dC   "
                        % (estado, int(carro.rpm), int(carro.velocidade), m, int(carro.tps), int(carro.temp_motor))
                    )
                    sys.stdout.flush()

                await asyncio.sleep(0.02)
        finally:
            tecl.restaurar()

    # ---- HTTP: serve o dashboard real (web/dist) ----
    app = web.Application()
    app.router.add_get("/ws", ws_handler)

    if os.path.isdir(DIST_DIR):
        app.router.add_static("/", DIST_DIR, show_index=True)
    else:
        async def aviso(_):
            return web.Response(
                text=("Dashboard nao encontrado em '%s'.\n"
                      "Coloque este arquivo na raiz do projeto (ao lado da pasta web),\n"
                      "ou defina a variavel de ambiente DIST_DIR apontando para web/dist."
                      % DIST_DIR),
                content_type="text/plain",
            )
        app.router.add_get("/", aviso)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, HTTP_HOST, HTTP_PORT)
    await site.start()

    await loop_simulacao()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, RuntimeError):
        print("\nSimulador finalizado.")
