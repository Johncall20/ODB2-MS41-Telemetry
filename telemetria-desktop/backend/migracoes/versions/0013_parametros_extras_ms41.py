"""parametros extras da MS41

Revision ID: 0013
Revises: 0012

Onze colunas novas na `amostra`, uma por parametro que o firmware passou a
ler: carga, MAF (fluxo e tensao), retardo de knock, avanco de ignicao,
tempo de injecao, IACV, as duas integracoes de lambda e as duas sondas.
Todas FLOAT e anulaveis, como o `vbat`: nulo = amostra gravada antes desta migration, ou
por firmware que nao le aquele parametro. Nao grava dado nenhum.

O `valid` nao muda de tipo: os extras usam os bits 7 a 17, e INTEGER
cobre ate o 30.

SQL congelado, sem importar nada de `telemetria/`.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: Union[str, Sequence[str], None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

COLUNAS = (
    "load",
    "maf",
    "mafv",
    "knock",
    "ign",
    "inj",
    "iacv",
    "lint1",
    "lint2",
    "lam1",
    "lam2",
)


def upgrade() -> None:
    for coluna in COLUNAS:
        op.add_column("amostra", sa.Column(coluna, sa.Float(), nullable=True))


def downgrade() -> None:
    for coluna in reversed(COLUNAS):
        op.drop_column("amostra", coluna)
