"""
O que vive enquanto o processo vive: leitor, gravador e hub, guardados em
app.state. Mexe aqui quem mudar como o app liga e desliga.
"""

from __future__ import annotations

import os
from typing import Optional

from starlette.requests import HTTPConnection

from .servicos.gravador import Gravador, Hub
from .modelos import PerfilEcu
from .servicos.leitor import (
    NOME_PADRAO,
    LeitorBase,
    LeitorBLE,
    LeitorSimulado,
    compatibilidade_do_perfil,
)


class Contexto:
    def __init__(self, usar_simulador: Optional[bool] = None, nome_ble: Optional[str] = None):
        padrao_sim = os.environ.get("TELEMETRIA_FONTE", "ble").lower() == "sim"
        self.usar_simulador = padrao_sim if usar_simulador is None else usar_simulador
        self.nome_ble = nome_ble or os.environ.get("TELEMETRIA_NOME_BLE", NOME_PADRAO)

        self.hub = Hub()
        self.gravador = Gravador(self.hub)
        self.leitor: Optional[LeitorBase] = None
        # As gravacoes que o processo anterior deixou no meio e que este
        # fechou ao subir (`consolidacao.encerrar_orfas`). Ficam ate o dono
        # dizer que viu: a tela do Ao vivo avisa que foram interrompidas.
        self.interrompidas: list[dict] = []

    def configurar(self, *, usar_simulador: bool, nome_ble: str) -> None:
        """Aplica o que veio da linha de comando. So vale antes de iniciar:
        trocar a fonte com o leitor rodando nao faria sentido."""
        self.usar_simulador = usar_simulador
        self.nome_ble = nome_ble

    @property
    def fonte(self) -> str:
        """"simulador" ou "ble" - o que a tela mostra no topo."""
        return "simulador" if self.usar_simulador else "ble"

    def compatibilidade(self, perfil: Optional[PerfilEcu]) -> Optional[dict]:
        """O carro deste perfil pode gravar com a fonte DESTE processo?"""
        return compatibilidade_do_perfil(perfil, self.usar_simulador, self.nome_ble)

    def interrompida_de(self, usuario_id: int) -> Optional[dict]:
        """A gravacao interrompida mais recente desta conta, ou None."""
        delas = [i for i in self.interrompidas if i["usuario_id"] == usuario_id]
        if not delas:
            return None
        ultima = max(delas, key=lambda i: i["sessao_id"])
        return {k: v for k, v in ultima.items() if k != "usuario_id"}

    def ciente(self, usuario_id: int) -> None:
        """O dono viu o aviso: as interrompidas dele saem da lista."""
        self.interrompidas = [i for i in self.interrompidas if i["usuario_id"] != usuario_id]

    async def iniciar(self) -> None:
        """Cria a fonte escolhida e poe leitor e gravador para rodar."""
        Classe = LeitorSimulado if self.usar_simulador else LeitorBLE
        self.leitor = Classe(self.gravador.receber, self.gravador.ao_mudar_estado)
        if not self.usar_simulador:
            self.leitor.nome = self.nome_ble
        self.gravador.iniciar_flush()
        await self.leitor.iniciar()

    async def parar(self) -> None:
        """Desliga a fonte e grava o que sobrou no buffer, nesta ordem."""
        if self.leitor is not None:
            await self.leitor.parar()
        await self.gravador.parar()


def obter_contexto(conexao: HTTPConnection) -> Contexto:
    """Entrega o contexto do processo para a rota que pedir.

    HTTPConnection, e nao Request, porque e a base comum de Request e
    WebSocket - assim a mesma dependencia serve o /ws e as rotas HTTP.
    """
    return conexao.app.state.contexto
