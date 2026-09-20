"""
Os limites de UM carro - os unicos que existem. Uma linha por veiculo,
com os seis valores **sempre preenchidos**: nao ha limite global nem
heranca, entao nulo aqui nao significa nada.

A linha nasce junto com o veiculo (`repositorios/veiculos.criar()`), e o
backfill de `banco.py` cobre os carros cadastrados antes disso.
"""

from typing import Optional

from sqlmodel import Field, SQLModel

from .limites import LIMITES_SUGERIDOS


class LimitesVeiculo(SQLModel, table=True):
    """Os limites de alerta de um veiculo. Exatamente uma linha por carro."""

    id: Optional[int] = Field(default=None, primary_key=True)
    veiculo_id: int = Field(foreign_key="veiculo.id", unique=True, index=True)

    # Os sugeridos entram como default so para o carro que nasce agora; a
    # partir dai o valor e dele e nao acompanha mais nada.
    #
    # As seis colunas sao NOT NULL no banco, sem excecao: com Alembic ha um
    # esquema so, e a divergencia antiga entre banco novo e banco migrado
    # (que obrigava o backfill a rodar no boot) deixou de existir. Quem
    # garante que todo veiculo tenha uma linha e
    # `repositorios/veiculos.criar()`, na mesma transacao do veiculo, e a
    # migration de dados 0002 para o que entrar por fora.
    shift_light_rpm: int = LIMITES_SUGERIDOS["shift_light_rpm"]
    rpm_alto: int = LIMITES_SUGERIDOS["rpm_alto"]
    temp_alta_c: int = LIMITES_SUGERIDOS["temp_alta_c"]
    vbat_baixa: float = LIMITES_SUGERIDOS["vbat_baixa"]
    rpm_marcha_lenta: int = LIMITES_SUGERIDOS["rpm_marcha_lenta"]
    ect_operacao_c: int = LIMITES_SUGERIDOS["ect_operacao_c"]
