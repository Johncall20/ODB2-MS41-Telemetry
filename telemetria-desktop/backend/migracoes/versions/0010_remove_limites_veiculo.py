"""remove limitesveiculo: os limites passam a ser so da sessao

Revision ID: 0010
Revises: 0009

Os limites de alerta deixam de ser do carro. Quem inicia a gravacao
escolhe os seis valores (os da ultima sessao do carro, os sugeridos ou
personalizados), e eles ficam so nas colunas `limite_*` da `sessao`, que
ja existiam como snapshot. A tabela `limitesveiculo` perde a razao de
existir e sai.

**Nenhuma sessao e tocada.** Esta migration nao tem comando sobre
`sessao`: o snapshot de cada gravacao continua exatamente como estava, e
sessao antiga com snapshot nulo continua caindo nos sugeridos pelo
caminho de sempre (`repositorios/limites.efetivos_da_sessao`).

Antes de escrever esta migration foi conferido, nos tres bancos, que todo
carro com sessao tinha na `limitesveiculo` os mesmos valores do snapshot
da ultima sessao dele, e todo carro sem sessao tinha os sugeridos - ou
seja, nenhum valor se perde: ou ele esta no snapshot, ou e o que a opcao
"Sugeridos" oferece.

O downgrade recria a tabela e devolve o invariante antigo (uma linha por
carro, seis valores preenchidos): o snapshot da ultima sessao do carro, ou
os sugeridos como LITERAIS - congelados, nao lidos da constante do app.

SQL congelado, sem importar nada de `telemetria/`.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: Union[str, Sequence[str], None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index("ix_limitesveiculo_veiculo_id", table_name="limitesveiculo")
    op.drop_table("limitesveiculo")


def downgrade() -> None:
    op.create_table(
        "limitesveiculo",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("veiculo_id", sa.Integer(), nullable=False),
        sa.Column("shift_light_rpm", sa.Integer(), nullable=False),
        sa.Column("rpm_alto", sa.Integer(), nullable=False),
        sa.Column("temp_alta_c", sa.Integer(), nullable=False),
        sa.Column("vbat_baixa", sa.Float(), nullable=False),
        sa.Column("rpm_marcha_lenta", sa.Integer(), nullable=False),
        sa.Column("ect_operacao_c", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["veiculo_id"], ["veiculo.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_limitesveiculo_veiculo_id", "limitesveiculo", ["veiculo_id"], unique=True
    )
    op.execute(
        """
        INSERT INTO limitesveiculo (veiculo_id, shift_light_rpm, rpm_alto, temp_alta_c,
                                    vbat_baixa, rpm_marcha_lenta, ect_operacao_c)
        SELECT v.id,
               COALESCE(u.limite_shift_light_rpm, 6200),
               COALESCE(u.limite_rpm_alto, 6800),
               COALESCE(u.limite_temp_alta_c, 105),
               COALESCE(u.limite_vbat_baixa, 11.8),
               COALESCE(u.limite_rpm_marcha_lenta, 1100),
               COALESCE(u.limite_ect_operacao_c, 80)
        FROM veiculo v
        LEFT JOIN LATERAL (
            SELECT * FROM sessao s
            WHERE s.veiculo_id = v.id
              AND s.limite_shift_light_rpm IS NOT NULL
              AND s.limite_rpm_alto IS NOT NULL
              AND s.limite_temp_alta_c IS NOT NULL
              AND s.limite_vbat_baixa IS NOT NULL
              AND s.limite_rpm_marcha_lenta IS NOT NULL
              AND s.limite_ect_operacao_c IS NOT NULL
            ORDER BY s.iniciada_em DESC, s.id DESC
            LIMIT 1
        ) u ON true
        """
    )
