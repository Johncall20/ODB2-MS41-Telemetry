"""km e notas da sessao; quilometragem do carro anulavel

Revision ID: 0011
Revises: 0010

O que muda:

- `sessao.km`: inteiro, anulavel, `CHECK km >= 0`. A quilometragem do
  painel no dia da gravacao - e o historico de km do carro.
- `sessao.observacao` (as "notas" da tela) ganha teto de 2000 caracteres
  no banco. A coluna ja existia; o resto da regra (quebras de linha
  preservadas, vazio = NULL) e da entrada.
- `veiculo.quilometragem` passa a ANULAVEL e sem default, e o 0 que havia
  vira NULL. Ate aqui 0 queria dizer "nao informado", e isso confundia o
  valor com a falta dele: um carro com 0 km de verdade nao tinha como se
  distinguir de um cadastro sem o campo. O `CHECK >= 0` continua.

O downgrade devolve o 0 no lugar do NULL - e com isso volta a ambiguidade
que esta migration desfez, porque o esquema antigo nao tinha outra forma.

SQL congelado, sem importar nada de `telemetria/`.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: Union[str, Sequence[str], None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("sessao", sa.Column("km", sa.Integer(), nullable=True))
    op.create_check_constraint("ck_sessao_km", "sessao", "km IS NULL OR km >= 0")
    op.create_check_constraint(
        "ck_sessao_observacao_tamanho",
        "sessao",
        "observacao IS NULL OR char_length(observacao) <= 2000",
    )

    op.alter_column("veiculo", "quilometragem", nullable=True)
    op.execute("UPDATE veiculo SET quilometragem = NULL WHERE quilometragem = 0")


def downgrade() -> None:
    op.execute("UPDATE veiculo SET quilometragem = 0 WHERE quilometragem IS NULL")
    op.alter_column("veiculo", "quilometragem", nullable=False)

    op.drop_constraint("ck_sessao_observacao_tamanho", "sessao", type_="check")
    op.drop_constraint("ck_sessao_km", "sessao", type_="check")
    op.drop_column("sessao", "km")
