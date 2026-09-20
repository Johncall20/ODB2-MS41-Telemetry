"""
As tabelas do banco, uma por modulo; este __init__ reexporta todas, entao
`from .modelos import Amostra` vale de qualquer lugar.
"""

from .amostra import Amostra
from .cliente import Cliente
from .comum import agora
from .enums import (
    BITS_VALID,
    VALID_COMPLETO,
    EstadoLeitor,
    PapelUsuario,
    StatusSessao,
    TipoEvento,
    campos_invalidos,
)
from .evento import Evento
from .limites import CAMPOS_LIMITE, LIMITES_SUGERIDOS, Limites
from .limites_veiculo import LimitesVeiculo
from .sessao import Sessao
from .token_acesso import TokenAcesso
from .usuario import Usuario
from .veiculo import Veiculo, normalizar_placa

__all__ = [
    "Amostra",
    "Cliente",
    "BITS_VALID",
    "CAMPOS_LIMITE",
    "Evento",
    "EstadoLeitor",
    "LIMITES_SUGERIDOS",
    "Limites",
    "LimitesVeiculo",
    "Sessao",
    "PapelUsuario",
    "TokenAcesso",
    "Usuario",
    "StatusSessao",
    "TipoEvento",
    "VALID_COMPLETO",
    "Veiculo",
    "agora",
    "campos_invalidos",
    "normalizar_placa",
]
