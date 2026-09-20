"""clientes, e o texto livre de cliente virando FK

Revision ID: 0004
Revises: 0003

Esquema E dados. A ordem importa: cria `cliente`, acrescenta
`veiculo.cliente_id`, **converte o texto** e so entao derruba a coluna
antiga - derrubar antes perderia o que se quer converter.

A atribuicao: todo carro que ja existe vai para a conta MAIS ANTIGA (menor
id). E a unica escolha automatica defensavel - num banco de
desenvolvimento ha uma conta so, e inventar dono seria pior que assumir o
obvio. Sem conta nenhuma no banco, os carros ficam com `cliente_id` nulo e
a migration avisa quantos foram: carro sem dono ja e invisivel de qualquer
jeito, porque toda consulta filtra por `veiculo -> cliente -> usuario`.

Textos iguais viram UM cliente. A comparacao normaliza espaco e caixa
("  Marcio  Camargo " e "marcio camargo" sao a mesma pessoa), mas o nome
gravado e o que o usuario digitou - normalizar para comparar nao e o mesmo
que reescrever.

Entre as grafias do mesmo nome, o grupo fica com a **mais frequente**, e
nao com a primeira em ordem alfabetica: `min()` escolheria justamente a
que comeca com espaco, porque espaco ordena antes de letra. So o espaco
das pontas e removido - isso e sujeira de digitacao, nao grafia.

SQL congelado, sem importar nada de `telemetria/` - ver "SQL de migration
e CONGELADO" no CLAUDE.md.
"""

from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = "0004"
down_revision: Union[str, Sequence[str], None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# lower(btrim(espacos colapsados)). So para COMPARAR: o nome gravado e o
# texto original.
_CHAVE = "lower(btrim(regexp_replace(cliente, '\\s+', ' ', 'g')))"


def upgrade() -> None:
    op.create_table(
        "cliente",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("nome", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("contato", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("implicito", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuario.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_cliente_usuario_id"), "cliente", ["usuario_id"], unique=False)

    op.add_column("veiculo", sa.Column("cliente_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_veiculo_cliente_id"), "veiculo", ["cliente_id"], unique=False)
    op.create_foreign_key(None, "veiculo", "cliente", ["cliente_id"], ["id"])

    _converter()

    op.drop_column("veiculo", "cliente")


def _converter() -> None:
    """Transforma o texto livre em linhas de `cliente` e liga os veiculos."""
    con = op.get_bind()

    dono = con.execute(sa.text("SELECT id, nome FROM usuario ORDER BY id LIMIT 1")).first()
    se_orfaos = con.execute(sa.text("SELECT count(*) FROM veiculo")).scalar_one()

    if dono is None:
        if se_orfaos:
            print(
                f"[0004] {se_orfaos} veiculo(s) ficaram sem cliente: nao ha conta "
                "neste banco a quem atribui-los. Eles continuam gravados, mas nao "
                "aparecem em tela nenhuma (toda consulta filtra pelo dono). Se for "
                "o banco de demonstracao, rode `python semear.py --recriar`."
            )
        return

    usuario_id, nome_do_dono = dono

    # Um cliente por texto distinto, comparando normalizado. O nome que
    # fica e a grafia MAIS FREQUENTE do grupo (`mode()`), so sem o espaco
    # das pontas.
    con.execute(
        sa.text(
            f"""
            INSERT INTO cliente (usuario_id, nome, contato, implicito)
            SELECT :usuario_id,
                   mode() WITHIN GROUP (ORDER BY btrim(cliente)),
                   '', false
              FROM veiculo
             WHERE cliente IS NOT NULL AND btrim(cliente) <> ''
             GROUP BY {_CHAVE}
            """
        ),
        {"usuario_id": usuario_id},
    )

    con.execute(
        sa.text(
            f"""
            UPDATE veiculo v
               SET cliente_id = c.id
              FROM cliente c
             WHERE c.usuario_id = :usuario_id
               AND lower(btrim(regexp_replace(c.nome, '\\s+', ' ', 'g'))) = {_CHAVE}
               AND v.cliente IS NOT NULL AND btrim(v.cliente) <> ''
            """
        ),
        {"usuario_id": usuario_id},
    )

    # Carro sem texto de cliente tambem precisa de dono. Vai para o cliente
    # implicito da conta - o mesmo que uma conta PARTICULAR usa.
    sem_texto = con.execute(
        sa.text(
            "SELECT count(*) FROM veiculo "
            "WHERE cliente IS NULL OR btrim(cliente) = ''"
        )
    ).scalar_one()

    if sem_texto:
        implicito = con.execute(
            sa.text(
                "INSERT INTO cliente (usuario_id, nome, contato, implicito) "
                "VALUES (:usuario_id, :nome, '', true) RETURNING id"
            ),
            {"usuario_id": usuario_id, "nome": nome_do_dono},
        ).scalar_one()
        con.execute(
            sa.text(
                "UPDATE veiculo SET cliente_id = :cliente_id "
                "WHERE cliente IS NULL OR btrim(cliente) = ''"
            ),
            {"cliente_id": implicito},
        )

    quantos = con.execute(sa.text("SELECT count(*) FROM cliente")).scalar_one()
    print(f"[0004] {quantos} cliente(s) criados, todos na conta #{usuario_id}")


def downgrade() -> None:
    """Devolve a coluna de texto com o nome do cliente.

    Nao e um desfazer perfeito - o contato se perde, e dois clientes com
    nomes diferentes que apontavam para o mesmo carro nao existem para
    desempatar -, mas o nome, que era tudo o que havia antes, volta.
    """
    op.add_column(
        "veiculo",
        sa.Column("cliente", sa.VARCHAR(), nullable=False, server_default=""),
    )
    op.execute(
        """
        UPDATE veiculo v
           SET cliente = c.nome
          FROM cliente c
         WHERE c.id = v.cliente_id AND c.implicito = false
        """
    )
    op.alter_column("veiculo", "cliente", server_default=None)

    op.drop_constraint("veiculo_cliente_id_fkey", "veiculo", type_="foreignkey")
    op.drop_index(op.f("ix_veiculo_cliente_id"), table_name="veiculo")
    op.drop_column("veiculo", "cliente_id")
    op.drop_index(op.f("ix_cliente_usuario_id"), table_name="cliente")
    op.drop_table("cliente")
