"""faixa de anos do modelo

Revision ID: 0012
Revises: 0011

`modelo.ano_min` e `modelo.ano_max`: os anos de modelo em que a FIPE tem
aquela versao, inteiros e anulaveis. Nulo = faixa desconhecida, e o
formulario cai no 1950 ate o ano que vem de sempre.

Nao grava dado nenhum: a faixa vem do `gerar_catalogo.py` (uma requisicao
por modelo, sob cota diaria) e entra pelo `executar.py
--carregar-catalogo`. O snapshot congelado da 0009 nao tem anos e nao
muda. Por isso nenhum carro existente fica fora de faixa AQUI - so depois
da recarga, e a rota de veiculo aceita o par modelo + ano que o carro ja
tinha.

CHECKs: os dois juntos ou nenhum, `ano_min <= ano_max`, piso 1950, e
modelo customizado (`usuario_id` preenchido) nunca tem faixa - quem o
criou nao disse em que anos ele existe.

SQL congelado, sem importar nada de `telemetria/`.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: Union[str, Sequence[str], None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("modelo", sa.Column("ano_min", sa.Integer(), nullable=True))
    op.add_column("modelo", sa.Column("ano_max", sa.Integer(), nullable=True))
    op.create_check_constraint(
        "ck_modelo_faixa_completa", "modelo", "(ano_min IS NULL) = (ano_max IS NULL)"
    )
    op.create_check_constraint(
        "ck_modelo_faixa_ordem", "modelo", "ano_min IS NULL OR (ano_min >= 1950 AND ano_min <= ano_max)"
    )
    op.create_check_constraint(
        "ck_modelo_faixa_so_catalogo", "modelo", "usuario_id IS NULL OR ano_min IS NULL"
    )


def downgrade() -> None:
    op.drop_constraint("ck_modelo_faixa_so_catalogo", "modelo", type_="check")
    op.drop_constraint("ck_modelo_faixa_ordem", "modelo", type_="check")
    op.drop_constraint("ck_modelo_faixa_completa", "modelo", type_="check")
    op.drop_column("modelo", "ano_max")
    op.drop_column("modelo", "ano_min")
