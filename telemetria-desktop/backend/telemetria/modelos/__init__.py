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
from .limites import CAMPOS_LIMITE, LIMITES_SUGERIDOS, Limites
from .limites_veiculo import LimitesVeiculo
from .sessao import Sessao
from .veiculo import Veiculo, normalizar_placa

__all__ = [
    "Amostra",
    "BITS_VALID",
    "CAMPOS_LIMITE",
    "Evento",
    "EstadoLeitor",
    "LIMITES_SUGERIDOS",
    "Limites",
    "LimitesVeiculo",
    "Sessao",
    "StatusSessao",
    "TipoEvento",
    "VALID_COMPLETO",
    "Veiculo",
    "agora",
    "campos_invalidos",
    "normalizar_placa",
]
