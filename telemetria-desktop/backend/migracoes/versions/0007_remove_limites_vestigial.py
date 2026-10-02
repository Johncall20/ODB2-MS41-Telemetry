"""remove a tabela limites, vestigial

Revision ID: 0007
Revises: 0006

`limites` era o limite GLOBAL, de onde os carros herdavam, de antes de os
limites virarem por veiculo (`limitesveiculo`, migration 0002). Desde entao
ninguem le nem escreve nela. A classe continuava no modelo porque o
`banco.py` antigo so sabia acrescentar tabela, e tira-la faria banco novo e
banco migrado divergirem - motivo que acabou com o Alembic.

O downgrade recria a ESTRUTURA, igual a da 0001, e nao os dados: a linha
que houvesse ali nao era lida por ninguem, e nao ha de onde recupera-la.

SQL congelado, sem importar nada de `telemetria/`.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: Union[str, Sequence[str], None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table("limites")


def downgrade() -> None:
    op.create_table(
        "limites",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("shift_light_rpm", sa.Integer(), nullable=False),
        sa.Column("rpm_alto", sa.Integer(), nullable=False),
        sa.Column("temp_alta_c", sa.Integer(), nullable=False),
        sa.Column("vbat_baixa", sa.Float(), nullable=False),
        sa.Column("rpm_marcha_lenta", sa.Integer(), nullable=False),
        sa.Column("ect_operacao_c", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
