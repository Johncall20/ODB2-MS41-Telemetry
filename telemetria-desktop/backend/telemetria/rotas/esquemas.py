"""
Os formatos que entram e saem pelas rotas: entradas Pydantic, que validam,
e os montadores de dicionario que mais de uma rota reaproveita.
"""

from pydantic import BaseModel, field_validator

from ..modelos import Evento, TipoEvento, Veiculo, normalizar_placa


class VeiculoEntrada(BaseModel):
    """O formulario de veiculo, vindo da tela."""

    marca: str
    modelo: str
    ano: int
    placa: str
    ecu: str = "MS41.1"
    motor: str = ""
    protocolo: str = "DS2"
    quilometragem: int = 0
    cliente: str = ""

    @field_validator("placa")
    @classmethod
    def _placa_normalizada(cls, valor: str) -> str:
        """Normaliza na entrada, entao POST e PUT gravam a placa igual."""
        return normalizar_placa(valor)


class InicioSessao(BaseModel):
    """O que a tela manda para comecar a gravar."""

    veiculo_id: int
    observacao: str = ""


# INICIO_SESSAO e FIM_SESSAO existem em toda sessao; nao dizem nada sobre o
# que aconteceu no motor. As telas so mostram os eventos anomalos.
EVENTOS_DE_ROTINA = {TipoEvento.INICIO_SESSAO, TipoEvento.FIM_SESSAO}


def eventos_notaveis(eventos: list[Evento]) -> list[str]:
    """Tipos de evento anomalo da sessao, sem repetir, na ordem em que
    apareceram. A tela mostra o primeiro e um "+N" com o resto."""
    vistos: list[str] = []
    for e in sorted(eventos, key=lambda e: e.id or 0):
        if e.tipo in EVENTOS_DE_ROTINA:
            continue
        if e.tipo.value not in vistos:
            vistos.append(e.tipo.value)
    return vistos


def veiculo_resumido(veiculo: Veiculo | None) -> dict | None:
    """So o que as telas de sessao mostram do carro.

    `arquivado_em` vai junto porque a sessao de um veiculo arquivado
    continua listada, e a tela precisa marcar a placa.
    """
    if veiculo is None:
        return None
    return {
        "id": veiculo.id,
        "placa": veiculo.placa,
        "marca": veiculo.marca,
        "modelo": veiculo.modelo,
        "arquivado_em": veiculo.arquivado_em,
    }
