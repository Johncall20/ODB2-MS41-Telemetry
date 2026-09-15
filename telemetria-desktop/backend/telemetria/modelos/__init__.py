"""
As tabelas do banco, uma por modulo; este __init__ reexporta todas, entao
`from .modelos import Amostra` vale de qualquer lugar.
"""

from .amostra import Amostra
from .comum import agora
from .enums import (
    BITS_VALID,
    VALID_COMPLETO,
    EstadoLeitor,
    StatusSessao,
    TipoEvento,
    campos_invalidos,
)
from .evento import Evento
from .limites import Limites
from .sessao import Sessao
from .veiculo import Veiculo, normalizar_placa

__all__ = [
    "Amostra",
    "BITS_VALID",
    "Evento",
    "EstadoLeitor",
    "Limites",
    "Sessao",
    "StatusSessao",
    "TipoEvento",
    "VALID_COMPLETO",
    "Veiculo",
    "agora",
    "campos_invalidos",
    "normalizar_placa",
]
