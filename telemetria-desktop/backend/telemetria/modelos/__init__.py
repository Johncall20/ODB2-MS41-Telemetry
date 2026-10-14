"""
As tabelas do banco, uma por modulo; este __init__ reexporta todas, entao
`from .modelos import Amostra` vale de qualquer lugar.
"""

from .amostra import Amostra
from .catalogo import MARCA_OUTRA, Marca, Modelo, descrever
from .cliente import Cliente
from .comum import agora
from .enums import (
    BITS_VALID,
    VALID_COMPLETO,
    Cambio,
    Combustivel,
    EstadoLeitor,
    PapelUsuario,
    PerfilEcu,
    StatusSessao,
    TipoEvento,
    campos_invalidos,
)
from .evento import Evento
from .limites import CAMPOS_LIMITE, LIMITES_SUGERIDOS, Limites
from .sessao import Sessao
from .token_acesso import TokenAcesso
from .usuario import Usuario
from .veiculo import Veiculo, normalizar_placa

__all__ = [
    "Amostra",
    "Cambio",
    "Combustivel",
    "MARCA_OUTRA",
    "descrever",
    "Marca",
    "Modelo",
    "PerfilEcu",
    "Cliente",
    "BITS_VALID",
    "CAMPOS_LIMITE",
    "Evento",
    "EstadoLeitor",
    "LIMITES_SUGERIDOS",
    "Limites",
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
