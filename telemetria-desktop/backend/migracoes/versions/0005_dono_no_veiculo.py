"""usuario_id no veiculo, e a placa unica por conta

Revision ID: 0005
Revises: 0004

O dono ja vinha por `veiculo -> cliente -> usuario`. Esta migration
acrescenta `veiculo.usuario_id` com a MESMA informacao, por duas razoes:

1. **O indice unico da placa.** Ele era global, e de antes do login: duas
   contas diferentes nao conseguiam cadastrar a mesma placa, e a segunda
   recebia "placa ja cadastrada" - revelando que ALGUEM tinha aquele
   carro. Unicidade por conta e garantia que tem de morar no banco, e o
   Postgres so indexa coluna da propria tabela. Por `(cliente_id, placa)`
   o mesmo mecanico duplicaria a placa entre dois clientes dele, que e
   justamente o erro de digitacao que o indice existe para pegar.
2. **Tirar um JOIN** de toda consulta filtrada por dono.

Os dois campos TEM DE CONCORDAR
(`veiculo.usuario_id == veiculo.cliente.usuario_id`). Quem garante e a
aplicacao, em `rotas/veiculos.py`.

SQL congelado, sem importar nada de `telemetria/`.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, Sequence[str], None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    con = op.get_bind()

    # Carro sem cliente nao tem de quem herdar dono, e a coluna vai ser
    # NOT NULL. Para nao apagar dado nem deixar a coluna anulavel
    # contrariando o que o indice precisa, a migration PARA aqui e diz o
    # que fazer. O Postgres tem DDL transacional: nada foi aplicado, e o
    # banco continua na 0004.
    orfaos = con.execute(
        sa.text("SELECT count(*) FROM veiculo WHERE cliente_id IS NULL")
    ).scalar_one()
    if orfaos:
        raise RuntimeError(
            f"{orfaos} veiculo(s) estao sem cliente e nao tem dono para herdar.\n"
            "Isto so acontece em banco que tinha carros e nenhuma conta quando a\n"
            "migration 0004 rodou - eles ja estao invisiveis no app.\n"
            "Resolva antes de migrar:\n"
            "  - banco de demonstracao: recrie a base e rode `python semear.py`\n"
            "  - banco com dado real: crie a conta dona e aponte os carros para\n"
            "    um cliente dela (UPDATE veiculo SET cliente_id = ...)"
        )

    op.add_column("veiculo", sa.Column("usuario_id", sa.Integer(), nullable=True))

    # O dono vem pela cadeia que ja existia.
    op.execute(
        """
        UPDATE veiculo v
           SET usuario_id = c.usuario_id
          FROM cliente c
         WHERE c.id = v.cliente_id
        """
    )

    op.alter_column("veiculo", "usuario_id", nullable=False)
    op.create_index(op.f("ix_veiculo_usuario_id"), "veiculo", ["usuario_id"])
    op.create_foreign_key(None, "veiculo", "usuario", ["usuario_id"], ["id"])

    # O indice da placa passa a ser por conta. Mesmo nome: e o mesmo
    # proposito, com o recorte corrigido.
    op.drop_index(
        "ix_veiculo_placa_ativa",
        table_name="veiculo",
        postgresql_where=sa.text("arquivado_em IS NULL"),
    )
    op.create_index(
        "ix_veiculo_placa_ativa",
        "veiculo",
        ["usuario_id", "placa"],
        unique=True,
        postgresql_where=sa.text("arquivado_em IS NULL"),
    )


def downgrade() -> None:
    """Volta a placa unica global e tira a coluna.

    **Pode falhar**, e por um motivo legitimo: se duas contas cadastraram a
    mesma placa enquanto a unicidade era por conta, o indice global nao
    pode mais ser criado. Nesse caso o dado precisa ser resolvido a mao -
    nao ha desempate automatico honesto entre dois carros de donos
    diferentes.
    """
    op.drop_index(
        "ix_veiculo_placa_ativa",
        table_name="veiculo",
        postgresql_where=sa.text("arquivado_em IS NULL"),
    )
    op.create_index(
        "ix_veiculo_placa_ativa",
        "veiculo",
        ["placa"],
        unique=True,
        postgresql_where=sa.text("arquivado_em IS NULL"),
    )

    op.drop_constraint("veiculo_usuario_id_fkey", "veiculo", type_="foreignkey")
    op.drop_index(op.f("ix_veiculo_usuario_id"), table_name="veiculo")
    op.drop_column("veiculo", "usuario_id")
