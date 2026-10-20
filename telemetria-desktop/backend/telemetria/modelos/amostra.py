"""
Uma leitura da central, como o firmware publicou. E a tabela que mais
cresce: uma linha por ciclo, ~1 Hz durante toda a gravacao.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Index
from sqlmodel import Field, Relationship, SQLModel

from .comum import agora
from .enums import BITS_PARAMETROS, VALID_COMPLETO

from .sessao import Sessao


class Amostra(SQLModel, table=True):
    # Toda leitura e "as amostras da sessao X em ordem de t_ms", entao o
    # indice cobre filtro e ordem de uma vez.
    __table_args__ = (Index("ix_amostra_sessao_t", "sessao_id", "t_ms"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    sessao_id: int = Field(foreign_key="sessao.id", index=True)

    # t_ms = millis() do ESP32 no instante da publicacao.
    # recebida_em = relogio do PC, para cruzar com video/planilha externa.
    t_ms: int
    recebida_em: datetime = Field(default_factory=agora, sa_type=DateTime(timezone=True))

    rpm: int = 0
    ect: int = 0
    iat: int = 0
    vbat: float = 0.0
    tps: float = 0.0
    vanos: float = 0.0
    vss: int = 0

    # Os extras da MS41 (enums.BITS_EXTRAS). Nulo = gravado por firmware
    # que nao le aquele parametro, ou antes da migration 0013.
    load: Optional[float] = None
    maf: Optional[float] = None
    mafv: Optional[float] = None
    knock: Optional[float] = None
    ign: Optional[float] = None
    inj: Optional[float] = None
    iacv: Optional[float] = None
    lint1: Optional[float] = None
    lint2: Optional[float] = None
    lam1: Optional[float] = None
    lam2: Optional[float] = None

    valid: int = 0

    sessao: Optional[Sessao] = Relationship(back_populates="amostras")

    def valido(self, campo: str) -> bool:
        """A central respondeu este campo nesta leitura?

        False = o numero na coluna e o do ciclo anterior, repetido pelo
        firmware. Todo calculo consulta isto antes de usar o valor.
        """
        return bool(self.valid & BITS_PARAMETROS.get(campo, 0))

    def completa(self) -> bool:
        """Os sete campos do nucleo responderam nesta leitura.

        Mascara, e nao igualdade: o firmware novo liga tambem os bits dos
        extras, e `valid == VALID_COMPLETO` daria toda leitura por
        incompleta.
        """
        return self.valid & VALID_COMPLETO == VALID_COMPLETO
