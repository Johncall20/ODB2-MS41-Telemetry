"""
Um acontecimento anotado durante a gravacao: shift light, giro alto,
temperatura alta, queda do link. Quem cria e o DetectorEventos.
"""

from datetime import datetime
from typing import Optional

from sqlmodel import Field, Relationship, SQLModel

from .comum import agora
from .enums import TipoEvento

from .sessao import Sessao


class Evento(SQLModel, table=True):
    """Uma linha do diario da sessao: o que houve, quando e o detalhe.

    `criado_em` e o instante da AMOSTRA que disparou, nao o da gravacao -
    e o que poe a marca no lugar certo do grafico.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    sessao_id: int = Field(foreign_key="sessao.id", index=True)
    criado_em: datetime = Field(default_factory=agora)
    tipo: TipoEvento
    mensagem: str = ""

    sessao: Optional[Sessao] = Relationship(back_populates="eventos")
