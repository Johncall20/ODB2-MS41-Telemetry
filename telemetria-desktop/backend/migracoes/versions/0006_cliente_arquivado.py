"""arquivado_em no cliente

Revision ID: 0006
Revises: 0005

Soft delete do cliente, igual ao do veiculo: nulo = ativo. Nada e apagado,
e os carros continuam apontando para ele. Quem impede arquivar cliente com
carro ativo e a rota, nao o banco - a contagem e a mensagem sao da tela.

Sem backfill: todo cliente que ja existe esta ativo, que e o nulo.

SQL congelado, sem importar nada de `telemetria/`.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, Sequence[str], None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "cliente",
        sa.Column("arquivado_em", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("cliente", "arquivado_em")
