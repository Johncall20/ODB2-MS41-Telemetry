"""
Uma gravacao, do inicio ao fim. Centro do modelo: amostra, evento e os
agregados congelados no encerramento penduram todos aqui.
"""

from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Index
from sqlmodel import Field, Relationship, SQLModel

from .comum import agora
from .enums import StatusSessao

from .veiculo import Veiculo

if TYPE_CHECKING:
    from .amostra import Amostra
    from .evento import Evento


class Sessao(SQLModel, table=True):
    # As sessoes de um carro sao sempre pedidas em ordem de data, entao o
    # indice cobre o filtro e a ordenacao de uma vez.
    __table_args__ = (Index("ix_sessao_veiculo_data", "veiculo_id", "iniciada_em"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    veiculo_id: int = Field(foreign_key="veiculo.id", index=True)
    iniciada_em: datetime = Field(default_factory=agora)
    encerrada_em: Optional[datetime] = None
    status: StatusSessao = StatusSessao.ATIVA
    observacao: str = ""

    # Agregados congelados no encerramento, para a listagem nao abrir a
    # tabela de amostras por linha. Nulo nao e zero: total_amostras nulo =
    # nunca calculado (o alvo do --recalcular); pico nulo = nenhuma leitura
    # valida daquele campo.
    total_amostras: Optional[int] = None
    amostras_completas: Optional[int] = None
    rpm_pico: Optional[int] = None
    vss_pico: Optional[int] = None
    ect_pico: Optional[int] = None
    vbat_min: Optional[float] = None

    veiculo: Optional[Veiculo] = Relationship(back_populates="sessoes")
    amostras: List["Amostra"] = Relationship(
        back_populates="sessao",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    eventos: List["Evento"] = Relationship(
        back_populates="sessao",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )

    def consolidada(self) -> bool:
        """True quando os agregados desta linha podem ser lidos direto.

        ATIVA nunca conta: os numeros dela ainda estao mudando.
        """
        return self.status == StatusSessao.ENCERRADA and self.total_amostras is not None

    def duracao_s(self) -> float:
        """Quanto a sessao durou; a aberta conta ate agora.

        O SQLite devolve datetime sem fuso e o gravado e UTC: marcar os
        dois lados evita subtrair um com fuso de um sem.
        """
        fim = self.encerrada_em or agora()
        inicio = self.iniciada_em
        if inicio.tzinfo is None:
            inicio = inicio.replace(tzinfo=timezone.utc)
        if fim.tzinfo is None:
            fim = fim.replace(tzinfo=timezone.utc)
        return (fim - inicio).total_seconds()
