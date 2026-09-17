"""
Os formatos que entram e saem pelas rotas: entradas Pydantic, que validam,
e os montadores de dicionario que mais de uma rota reaproveita.
"""

from typing import Optional

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


class LimitesEntrada(BaseModel):
    """O PUT dos limites de um carro: os seis campos, todos obrigatorios.

    Todos obrigatorios porque nao ha heranca - o carro tem os seis valores
    e nada de fora os completa. Campo ausente nao teria de quem herdar.
    """

    shift_light_rpm: int
    rpm_alto: int
    temp_alta_c: int
    vbat_baixa: float
    rpm_marcha_lenta: int
    ect_operacao_c: int


def problema_nos_limites(valores: dict) -> Optional[str]:
    """A frase do erro se estes limites nao fazem sentido, ou None.

    Os seis valores chegam juntos, entao a checagem e direta: positivos e
    na ordem `rpm_marcha_lenta < shift_light_rpm < rpm_alto`.
    """
    for campo, rotulo in (
        ("shift_light_rpm", "shift light"),
        ("rpm_alto", "giro alto"),
        ("temp_alta_c", "temperatura alta"),
        ("vbat_baixa", "bateria baixa"),
        ("rpm_marcha_lenta", "marcha lenta"),
        ("ect_operacao_c", "temperatura de operacao"),
    ):
        if valores[campo] is None or valores[campo] <= 0:
            return f"o limite de {rotulo} precisa ser maior que zero"

    if valores["shift_light_rpm"] >= valores["rpm_alto"]:
        return (
            f"o shift light ({valores['shift_light_rpm']} rpm) tem de ficar abaixo "
            f"do giro alto ({valores['rpm_alto']} rpm)"
        )
    if valores["rpm_marcha_lenta"] >= valores["shift_light_rpm"]:
        return (
            f"a marcha lenta ({valores['rpm_marcha_lenta']} rpm) tem de ficar abaixo "
            f"do shift light ({valores['shift_light_rpm']} rpm)"
        )
    return None


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
