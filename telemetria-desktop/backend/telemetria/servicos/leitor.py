"""
De onde vem a telemetria: LeitorBLE (ESP32-C3 real) e LeitorSimulado.
Mexe aqui quem for falar com outro hardware ou mudar o simulador.

O firmware so empurra - nao aceita comando, entao a interface e por
callback e nao ha como pedir um campo isolado.
"""

from __future__ import annotations

import asyncio
import json
import math
import os
import random
import time
from typing import Awaitable, Callable, Optional

from ..modelos import EstadoLeitor, PerfilEcu, VALID_COMPLETO

NUS_TX_CHAR = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"
NOME_PADRAO = "E36-DS2"

CamposEsperados = ("t", "rpm", "ect", "iat", "vbat", "tps", "vanos", "vss", "valid")

RetornoLeitura = Callable[[dict], Awaitable[None]]
RetornoEstado = Callable[[EstadoLeitor, str], Awaitable[None]]

# O unico perfil que o adaptador BLE sabe ler: o ESP32 fala DS2 com a MS41.
PERFIL_DO_ADAPTADOR = PerfilEcu.SIEMENS_MS41_DS2

# Como o perfil aparece na frase de recusa. O rotulo de tela mora no front
# (formato.ROTULO_PERFIL_ECU); este e so o da mensagem do backend.
_NOME_PERFIL = {PerfilEcu.OBD2_GENERICO: "OBD-II genérico"}


def compatibilidade_do_perfil(
    perfil: Optional[PerfilEcu], simulador: bool, nome_ble: str = NOME_PADRAO
) -> Optional[dict]:
    """O carro pode gravar com esta fonte? A regra mora so aqui.

    - simulador: sempre pode - ele nao le central nenhuma, e travar ali so
      impediria de testar o app com qualquer carro do cadastro;
    - BLE e perfil conhecido diferente da MS41: `bloqueia` (a rota de
      iniciar responde 409);
    - BLE e perfil nulo ("nao informado"): so avisa. Nulo e o carro
      cadastrado antes da `0009`, e o mais provavel e ser justamente o E36
      que o adaptador le - bloquear seria punir cadastro incompleto.

    Devolve None quando nao ha nada a dizer, senao `{"bloqueia", "mensagem"}`.
    """
    if simulador or perfil == PERFIL_DO_ADAPTADOR:
        return None
    if perfil is None:
        return {
            "bloqueia": False,
            "mensagem": f"Perfil da ECU não informado. O adaptador {nome_ble} só lê a "
            "Siemens MS41; confira o cadastro do carro.",
        }
    nome = _NOME_PERFIL.get(perfil, perfil.value)
    return {
        "bloqueia": True,
        "mensagem": f"O adaptador {nome_ble} só lê a Siemens MS41, e este carro está "
        f"cadastrado com {nome}.",
    }


class MontadorDeLinha:
    """Remonta as linhas JSON a partir dos pedacos de 20 bytes do notify BLE."""

    LIMITE_LIXO = 4096

    def __init__(self) -> None:
        self._buf = bytearray()

    def alimentar(self, dados: bytes) -> list[str]:
        """Recebe um pedaco cru do BLE e devolve as linhas ja completas.

        Devolve lista vazia enquanto a linha nao fechou - o notify corta o
        JSON no meio a cada 20 bytes.
        """
        linhas: list[str] = []
        self._buf.extend(dados)
        while b"\n" in self._buf:
            bruto, _, resto = self._buf.partition(b"\n")
            self._buf = bytearray(resto)
            texto = bruto.decode("utf-8", errors="replace").strip()
            if texto:
                linhas.append(texto)
        # Fora do while: um link que manda bytes e nunca uma quebra de
        # linha faria o buffer crescer sem limite.
        if len(self._buf) > self.LIMITE_LIXO:
            self._buf.clear()
        return linhas


def decodificar(linha: str) -> Optional[dict]:
    """Uma linha JSON do firmware vira o dicionario da amostra.

    None para lixo. Descartar em silencio e proposital: o link e sem fio,
    e a perda ja aparece na integridade.
    """
    try:
        d = json.loads(linha)
    except json.JSONDecodeError:
        return None
    if not isinstance(d, dict) or "t" not in d:
        return None
    return {
        "t_ms": int(d.get("t", 0)),
        "rpm": int(d.get("rpm", 0)),
        "ect": int(d.get("ect", 0)),
        "iat": int(d.get("iat", 0)),
        "vbat": float(d.get("vbat", 0.0)),
        "tps": float(d.get("tps", 0.0)),
        "vanos": float(d.get("vanos", 0.0)),
        "vss": int(d.get("vss", 0)),
        "valid": int(d.get("valid", 0)),
    }


class LeitorBase:
    """O contrato das fontes: liga, empurra leitura, avisa mudanca de estado.

    Quem herda so precisa escrever `_laco()`. O ciclo de vida da task e o
    aviso de estado ja vem prontos daqui.
    """

    def __init__(self, ao_ler: RetornoLeitura, ao_mudar_estado: RetornoEstado) -> None:
        self._ao_ler = ao_ler
        self._ao_mudar_estado = ao_mudar_estado
        self.estado = EstadoLeitor.DESLIGADO
        self.detalhe = ""
        self._task: Optional[asyncio.Task] = None

    async def _definir_estado(self, estado: EstadoLeitor, detalhe: str = "") -> None:
        """Anota o estado novo e avisa quem escuta - so quando muda mesmo.

        O laco do BLE repete o mesmo estado a cada tentativa; sem esta
        comparacao a interface receberia uma enxurrada de avisos iguais.
        """
        if estado == self.estado and detalhe == self.detalhe:
            return
        self.estado = estado
        self.detalhe = detalhe
        await self._ao_mudar_estado(estado, detalhe)

    async def iniciar(self) -> None:
        """Poe a fonte para rodar. Chamar duas vezes nao cria duas tasks."""
        if self._task and not self._task.done():
            return
        self._task = asyncio.create_task(self._laco())

    async def parar(self) -> None:
        """Cancela a task e espera ela morrer antes de devolver."""
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        await self._definir_estado(EstadoLeitor.DESLIGADO)

    async def _laco(self) -> None:  # pragma: no cover
        raise NotImplementedError


class LeitorBLE(LeitorBase):
    """A fonte real: o ESP32-C3 pelo Nordic UART Service.

    Reconecta para sempre - perder o carro de vista e o caso comum.
    """

    def __init__(self, ao_ler, ao_mudar_estado, nome: str = NOME_PADRAO, endereco: str | None = None):
        super().__init__(ao_ler, ao_mudar_estado)
        self.nome = nome
        self.endereco = endereco

    async def _laco(self) -> None:
        from bleak import BleakClient, BleakScanner

        montador = MontadorDeLinha()
        fila: asyncio.Queue[bytes] = asyncio.Queue()

        def ao_notificar(_remetente, dados: bytearray) -> None:
            fila.put_nowait(bytes(dados))

        while True:
            try:
                await self._definir_estado(EstadoLeitor.PROCURANDO, f'procurando "{self.nome}"')
                if self.endereco:
                    dev = await BleakScanner.find_device_by_address(self.endereco, timeout=8.0)
                else:
                    dev = await BleakScanner.find_device_by_filter(
                        lambda d, _ad: bool(d.name and self.nome.lower() in d.name.lower()),
                        timeout=8.0,
                    )
                if dev is None:
                    await self._definir_estado(EstadoLeitor.PROCURANDO, "módulo não apareceu, tentando de novo")
                    await asyncio.sleep(3)
                    continue

                async with BleakClient(dev) as cliente:
                    await cliente.start_notify(NUS_TX_CHAR, ao_notificar)
                    await self._definir_estado(EstadoLeitor.CONECTADO, str(dev.address))
                    while cliente.is_connected:
                        try:
                            dados = await asyncio.wait_for(fila.get(), timeout=1.0)
                        except asyncio.TimeoutError:
                            continue
                        for linha in montador.alimentar(dados):
                            leitura = decodificar(linha)
                            if leitura:
                                await self._ao_ler(leitura)

            except asyncio.CancelledError:
                raise
            except Exception as exc:
                await self._definir_estado(EstadoLeitor.ERRO, str(exc))
                await asyncio.sleep(2)


def _ler_queda(texto: Optional[str]) -> Optional[tuple[float, float]]:
    """"40:12" -> (40.0, 12.0); vazio ou fora do formato, sem queda."""
    try:
        ativo, parado = (float(x) for x in (texto or "").split(":"))
    except ValueError:
        return None
    return (ativo, parado) if ativo > 0 and parado > 0 else None


class LeitorSimulado(LeitorBase):
    """A fonte de mentira, para trabalhar sem o carro.

    Apaga um bit de `valid` as vezes, de proposito: e assim que se testa
    a regra do `valid` sem depender de um link BLE ruim de verdade.

    Com `TELEMETRIA_SIM_QUEDA="ATIVO:QUEDA"` (segundos) o modulo "some" de
    tempos em tempos: depois de ATIVO s lendo, fica QUEDA s sem mandar
    nada, em PROCURANDO, como o BLE faz quando o link cai - e volta. E o
    caminho de verdade do backend (estado do leitor, PERDA_CONEXAO, buraco
    na serie) e o da tela (leitura parada, "procurando o módulo"), sem
    precisar do carro.
    """

    def __init__(self, ao_ler, ao_mudar_estado, hz: float = 1.0, queda: Optional[str] = None):
        super().__init__(ao_ler, ao_mudar_estado)
        self.periodo = 1.0 / hz
        self.queda = _ler_queda(queda if queda is not None else os.environ.get("TELEMETRIA_SIM_QUEDA"))

    async def _laco(self) -> None:
        await self._definir_estado(EstadoLeitor.PROCURANDO, "iniciando simulador")
        await asyncio.sleep(0.5)
        await self._definir_estado(EstadoLeitor.CONECTADO, "fonte simulada")

        t0 = time.monotonic()
        rpm = 780.0
        ect = 22.0

        while True:
            t = time.monotonic() - t0
            if self.queda:
                ativo, parado = self.queda
                if t % (ativo + parado) >= ativo:
                    await self._definir_estado(
                        EstadoLeitor.PROCURANDO, "módulo não respondeu (queda simulada)"
                    )
                    await asyncio.sleep(self.periodo)
                    continue
                await self._definir_estado(EstadoLeitor.CONECTADO, "fonte simulada")
            alvo = 800 + max(0.0, math.sin(t / 9.0)) ** 3 * 5800
            rpm += (alvo - rpm) * 0.45 + random.uniform(-40, 40)
            rpm = max(650.0, min(7000.0, rpm))

            ect += (94.0 - ect) * 0.012 + random.uniform(-0.3, 0.3)
            tps = max(0.0, min(100.0, (rpm - 750) / 62.0 + random.uniform(-1, 1)))
            vss = int(max(0.0, (rpm - 900) / 38.0))
            vanos = 8.0 if rpm < 1500 else min(96.0, 8 + (rpm - 1500) / 55.0)
            vbat = 13.9 - (rpm > 5000) * 0.25 + random.uniform(-0.06, 0.06)
            iat = 28 + math.sin(t / 30.0) * 3

            valid = VALID_COMPLETO
            if random.random() < 0.06:            # a central deixa de responder um campo
                valid &= ~random.choice([0x04, 0x08, 0x40])

            await self._ao_ler(
                {
                    "t_ms": int(t * 1000),
                    "rpm": int(rpm),
                    "ect": int(ect),
                    "iat": int(iat),
                    "vbat": round(vbat, 2),
                    "tps": round(tps, 1),
                    "vanos": round(vanos, 1),
                    "vss": vss,
                    "valid": valid,
                }
            )
            await asyncio.sleep(self.periodo)
