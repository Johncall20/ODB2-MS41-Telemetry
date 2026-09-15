"""
Os nomes fixos do dominio e a leitura do bitmask do firmware. BITS_VALID
tem de espelhar o firmware - mexe aqui quem acrescentar campo ou evento.
"""

from enum import Enum


class StatusSessao(str, Enum):
    """Se a sessao ainda esta gravando ou ja foi fechada."""

    ATIVA = "ATIVA"
    ENCERRADA = "ENCERRADA"


class TipoEvento(str, Enum):
    """O que o detector sabe registrar.

    INICIO_SESSAO e FIM_SESSAO sao rotina e existem em toda gravacao; so
    os outros contam como evento nas telas.
    """

    INICIO_SESSAO = "INICIO_SESSAO"
    FIM_SESSAO = "FIM_SESSAO"
    SHIFT_LIGHT = "SHIFT_LIGHT"
    RPM_ALTO = "RPM_ALTO"
    TEMP_ALTA = "TEMP_ALTA"
    BATERIA_BAIXA = "BATERIA_BAIXA"
    PERDA_CONEXAO = "PERDA_CONEXAO"
    LEITURA_INCOMPLETA = "LEITURA_INCOMPLETA"


class EstadoLeitor(str, Enum):
    """Em que pe esta a ligacao com o adaptador BLE."""

    DESLIGADO = "DESLIGADO"
    PROCURANDO = "PROCURANDO"
    CONECTADO = "CONECTADO"
    ERRO = "ERRO"


# Bitmask publicado pelo firmware no campo "valid".
BITS_VALID: dict[str, int] = {
    "ect": 0x01,
    "rpm": 0x02,
    "tps": 0x04,
    "vanos": 0x08,
    "vbat": 0x10,
    "iat": 0x20,
    "vss": 0x40,
}
VALID_COMPLETO = 0x7F


def campos_invalidos(valid: int) -> list[str]:
    """Os campos que a central NAO respondeu naquela leitura.

    O firmware repete o numero anterior quando falha, entao sem esta lista
    o dado velho passaria por medicao nova.
    """
    return [nome for nome, bit in BITS_VALID.items() if not valid & bit]
