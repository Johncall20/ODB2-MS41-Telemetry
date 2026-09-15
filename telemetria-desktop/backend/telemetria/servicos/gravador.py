"""
O maestro da gravacao: leitor -> broadcast para a tela -> buffer -> banco.
Mexe aqui quem mudar o caminho entre a leitura e o disco.

A tela e avisada ANTES do commit: o painel nao pode esperar disco.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Optional

from ..modelos import (
    Amostra,
    EstadoLeitor,
    Evento,
    TipoEvento,
    agora,
    campos_invalidos,
)
from ..repositorios import amostras as repo_amostras
from ..repositorios import sessoes as repo_sessoes
from .detector import DetectorEventos

# De quanto em quanto tempo o buffer vai para o disco, e de quantas
# amostras. Os dois juntos decidem quanto se perde se o processo morrer no
# meio: no pior caso, tres segundos de gravacao. Baixar mais poria o disco
# no caminho do ciclo de leitura.
INTERVALO_FLUSH = 3.0   # segundos
TAMANHO_LOTE = 20

# Abaixo disto a sessao vai fora ao encerrar. A 1 Hz nominal sao menos de
# dez segundos de gravacao: nao da para tirar pico, duracao nem integridade
# de uma janela dessas, e a lista encheria de sessao inutil de clique
# errado.
MINIMO_AMOSTRAS = 10


class Hub:
    """Reparte uma mensagem entre todos os websockets abertos.

    Sem ping nem limpeza: a falha do send e que denuncia quem caiu.
    """

    def __init__(self) -> None:
        self._clientes: set = set()

    def entrar(self, ws) -> None:
        """Registra um websocket recem-conectado."""
        self._clientes.add(ws)

    def sair(self, ws) -> None:
        """Tira o websocket da lista. Chamar duas vezes nao da erro."""
        self._clientes.discard(ws)

    async def enviar(self, tipo: str, dados: dict) -> None:
        """Manda a mensagem para todos. Cliente que falha sai da lista."""
        if not self._clientes:
            return
        texto = json.dumps({"tipo": tipo, "dados": dados}, default=str)
        mortos = []
        for ws in list(self._clientes):
            try:
                await ws.send_text(texto)
            except Exception:
                mortos.append(ws)
        for ws in mortos:
            self._clientes.discard(ws)


class Gravador:
    """Recebe as leituras, avisa a tela e grava. Uma sessao por vez."""

    def __init__(self, hub: Hub) -> None:
        self.hub = hub
        self.sessao_id: Optional[int] = None
        self.estado_leitor = EstadoLeitor.DESLIGADO
        self.detalhe_leitor = ""
        self.ultima: Optional[dict] = None
        self.total_amostras = 0
        self._buffer: list[Amostra] = []
        self._detector: Optional[DetectorEventos] = None
        self._lock = asyncio.Lock()
        self._task_flush: Optional[asyncio.Task] = None

    # ------------------------------------------------------------- sessao

    def iniciar_sessao(self, veiculo_id: int, observacao: str = "") -> dict:
        """Abre a gravacao e prepara o detector.

        Os limites entram por copia: mexer neles nao afeta esta sessao.
        """
        sessao = repo_sessoes.criar(veiculo_id, observacao)
        limites = repo_sessoes.limites_da_sessao()
        dados = {
            "id": sessao.id,
            "veiculo_id": sessao.veiculo_id,
            "iniciada_em": sessao.iniciada_em,
            "encerrada_em": sessao.encerrada_em,
            "status": sessao.status.value,
            "observacao": sessao.observacao,
        }

        self.sessao_id = dados["id"]
        self.total_amostras = 0
        self._detector = DetectorEventos(limites=limites)
        return dados

    async def encerrar_sessao(self) -> Optional[dict]:
        """Fecha a sessao, ou joga fora se for curta demais.

        None quando nao havia sessao aberta.
        """
        if self.sessao_id is None:
            return None
        await self._descarregar()
        sid = self.sessao_id

        # Uma consulta so serve as duas coisas: o total decide se a sessao
        # e curta demais, e o resto e o agregado que fica gravado na linha
        # para a listagem nao ter de reabrir as amostras depois.
        agregados = repo_amostras.agregados(sid)
        gravadas = agregados["total_amostras"]
        descartada = gravadas < MINIMO_AMOSTRAS

        if descartada:
            repo_sessoes.descartar(sid)
        else:
            repo_sessoes.encerrar(sid, agregados)

        self.sessao_id = None
        self._detector = None
        await self.hub.enviar(
            "sessao", {"id": sid, "status": "DESCARTADA" if descartada else "ENCERRADA"}
        )
        return {"sessao_id": sid, "amostras": gravadas, "descartada": descartada}

    # ------------------------------------------------------------ leitura

    async def receber(self, leitura: dict) -> None:
        """Uma leitura recem-chegada do leitor.

        Se o processo morrer aqui perde-se no maximo o buffer, nunca uma
        sessao ja encerrada.
        """
        self.ultima = leitura
        payload = dict(leitura)
        payload["invalidos"] = campos_invalidos(leitura["valid"])
        payload["gravando"] = self.sessao_id is not None
        await self.hub.enviar("amostra", payload)

        if self.sessao_id is None:
            return

        amostra = Amostra(sessao_id=self.sessao_id, recebida_em=agora(), **leitura)

        eventos: list[Evento] = []
        if self._detector:
            eventos = self._detector.avaliar(amostra)

        async with self._lock:
            self._buffer.append(amostra)
            self.total_amostras += 1
            if len(self._buffer) >= TAMANHO_LOTE:
                await self._descarregar_sem_lock()

        if eventos:
            for e in repo_sessoes.registrar_eventos(eventos):
                await self.hub.enviar(
                    "evento",
                    {"tipo": e.tipo.value, "mensagem": e.mensagem, "criado_em": e.criado_em},
                )

    async def ao_mudar_estado(self, estado: EstadoLeitor, detalhe: str) -> None:
        """O leitor mudou de estado: avisa a tela e anota a queda do link.

        Cair gravando vira PERDA_CONEXAO, que explica o buraco na serie.
        """
        anterior = self.estado_leitor
        self.estado_leitor = estado
        self.detalhe_leitor = detalhe
        await self.hub.enviar("leitor", {"estado": estado.value, "detalhe": detalhe})

        caiu = anterior == EstadoLeitor.CONECTADO and estado != EstadoLeitor.CONECTADO
        if caiu and self.sessao_id is not None:
            repo_sessoes.registrar_eventos(
                [
                    Evento(
                        sessao_id=self.sessao_id,
                        tipo=TipoEvento.PERDA_CONEXAO,
                        mensagem=detalhe or "link BLE caiu",
                    )
                ]
            )
            await self.hub.enviar(
                "evento", {"tipo": "PERDA_CONEXAO", "mensagem": detalhe, "criado_em": agora()}
            )

    # --------------------------------------------------------------- flush

    async def _descarregar(self) -> None:
        """Grava o buffer, tomando o lock."""
        async with self._lock:
            await self._descarregar_sem_lock()

    async def _descarregar_sem_lock(self) -> None:
        """Grava o buffer. So chame com o lock ja tomado."""
        if not self._buffer:
            return
        lote, self._buffer = self._buffer, []
        repo_amostras.gravar_lote(lote)

    async def laco_flush(self) -> None:
        """Descarrega o buffer de tempos em tempos. Erro de escrita nao pode
        derrubar o laco e parar de gravar a sessao inteira."""
        while True:
            await asyncio.sleep(INTERVALO_FLUSH)
            try:
                await self._descarregar()
            except Exception:
                pass

    def iniciar_flush(self) -> None:
        """Liga o laco periodico de gravacao. Chamar uma vez, no start."""
        if self._task_flush is None:
            self._task_flush = asyncio.create_task(self.laco_flush())

    async def parar(self) -> None:
        """Encerra o laco e grava o que sobrou no buffer."""
        if self._task_flush:
            self._task_flush.cancel()
            self._task_flush = None
        await self._descarregar()
