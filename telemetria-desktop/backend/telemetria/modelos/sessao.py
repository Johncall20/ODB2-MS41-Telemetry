"""
Uma gravacao, do inicio ao fim. Centro do modelo: amostra, evento e os
agregados congelados no encerramento penduram todos aqui.
"""

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import CheckConstraint, DateTime, Index
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
    #
    # Os CHECKs espelham a migration 0008. O de status vale porque
    # `repositorios/sessoes.encerrar()` grava status e `encerrada_em` no
    # mesmo commit, e `criar()` nasce ATIVA sem data de fim.
    __table_args__ = (
        Index("ix_sessao_veiculo_data", "veiculo_id", "iniciada_em"),
        CheckConstraint(
            "encerrada_em IS NULL OR encerrada_em >= iniciada_em",
            name="ck_sessao_encerramento",
        ),
        CheckConstraint(
            "(status = 'ATIVA') = (encerrada_em IS NULL)", name="ck_sessao_status"
        ),
        CheckConstraint(
            "observacao IS NULL OR (observacao <> '' AND observacao = btrim(observacao))",
            name="ck_sessao_observacao",
        ),
        CheckConstraint(
            "observacao IS NULL OR char_length(observacao) <= 2000",
            name="ck_sessao_observacao_tamanho",
        ),
        CheckConstraint("km IS NULL OR km >= 0", name="ck_sessao_km"),
        CheckConstraint(
            "(total_amostras IS NULL OR total_amostras >= 0)"
            " AND (amostras_completas IS NULL OR amostras_completas >= 0)"
            " AND (amostras_completas IS NULL OR total_amostras IS NULL"
            " OR amostras_completas <= total_amostras)"
            " AND (rpm_pico IS NULL OR rpm_pico >= 0)"
            " AND (vss_pico IS NULL OR vss_pico >= 0)",
            name="ck_sessao_agregados",
        ),
        CheckConstraint(
            "(limite_shift_light_rpm IS NULL OR limite_shift_light_rpm > 0)"
            " AND (limite_rpm_alto IS NULL OR limite_rpm_alto > 0)"
            " AND (limite_temp_alta_c IS NULL OR limite_temp_alta_c > 0)"
            " AND (limite_vbat_baixa IS NULL OR limite_vbat_baixa > 0)"
            " AND (limite_rpm_marcha_lenta IS NULL OR limite_rpm_marcha_lenta > 0)"
            " AND (limite_ect_operacao_c IS NULL OR limite_ect_operacao_c > 0)",
            name="ck_sessao_limites",
        ),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    veiculo_id: int = Field(foreign_key="veiculo.id", index=True)
    iniciada_em: datetime = Field(default_factory=agora, sa_type=DateTime(timezone=True))
    encerrada_em: Optional[datetime] = Field(default=None, sa_type=DateTime(timezone=True))
    status: StatusSessao = StatusSessao.ATIVA
    # As "notas" da tela. Texto livre com quebras de linha preservadas,
    # ate 2000 caracteres; editavel antes, durante e depois da gravacao
    # (`PATCH /api/sessoes/{id}`). Nao preenchida = NULL.
    observacao: Optional[str] = None
    # O km do painel no dia da gravacao: o historico de quilometragem do
    # carro. Passa para `veiculo.quilometragem` so quando esta e a sessao
    # mais recente do carro e esta ENCERRADA - ver
    # `repositorios/sessoes._levar_km_ao_carro`.
    km: Optional[int] = None

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

    # Os limites DESTA gravacao - a unica fonte de limite do sistema. Sao
    # escolhidos ao iniciar (ultima sessao do carro, sugeridos ou
    # personalizados) e nao mudam depois: nao ha rota que os edite, nem
    # durante nem apos a gravacao. E o que deixa a sessao explicavel meses
    # depois: nada pode reescrever por que um evento disparou.
    # Prefixo `limite_` porque `rpm_alto` ao lado de `rpm_pico` seria um
    # par de nomes parecidos com sentidos opostos - um e regra, outro e
    # medicao. Nulo = sessao gravada antes deste campo existir; quem le
    # cai no padrao atual (ver repositorios/limites.efetivos_da_sessao).
    limite_shift_light_rpm: Optional[int] = None
    limite_rpm_alto: Optional[int] = None
    limite_temp_alta_c: Optional[int] = None
    limite_vbat_baixa: Optional[float] = None
    limite_rpm_marcha_lenta: Optional[int] = None
    limite_ect_operacao_c: Optional[int] = None

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

        Sem remendo de fuso: as colunas sao TIMESTAMP WITH TIME ZONE e o
        driver devolve datetime com fuso, do mesmo jeito que `agora()`.
        """
        return ((self.encerrada_em or agora()) - self.iniciada_em).total_seconds()
