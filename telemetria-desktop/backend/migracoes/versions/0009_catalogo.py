"""catalogo de marca e modelo, combustivel, cambio e perfil da ECU

Revision ID: 0009
Revises: 0008

O que muda:

- Nascem `marca` e `modelo`, e a primeira carga do catalogo FIPE entra
  aqui. Ela le `migracoes/dados/0009_catalogo_veiculos.json`, um SNAPSHOT
  congelado - nunca o `catalogo_veiculos.json` vivo da raiz do backend.
  Se lesse o vivo, regerar o catalogo mudaria o resultado desta migration,
  e dois bancos migrados em datas diferentes sairiam com catalogos
  diferentes. Recarregar o vivo e o `executar.py --carregar-catalogo`.
- `veiculo` troca o texto `marca`/`modelo` por `modelo_id`. Cada carro
  existente e casado com o catalogo pelo nome inteiro, sem diferenciar
  maiusculas, acentos nem espaco repetido:
    - marca e modelo achados: aponta para o modelo do catalogo;
    - marca achada e modelo nao: cria modelo CUSTOMIZADO para o dono do
      carro (um por nome, mesmo que dois carros o usem);
    - marca nao achada: customizado do dono na marca "Outra", com o nome
      "{marca} {modelo}" como estava.
  Nome exato, sem prefixo: "Gol GTI" casaria com duas versoes FIPE.
- `ecu` e `protocolo` (texto que ninguem lia) saem, e entram os enums
  `combustivel`, `cambio` e `perfil_ecu`, anulaveis. Os carros existentes
  ficam com os tres NULO ("Nao informado"): o "MS41.1"/"DS2" que eles
  tinham era o padrao da coluna, nao informacao de alguem.

O downgrade remonta o texto de marca e modelo a partir do catalogo e
devolve `ecu`/`protocolo` com o padrao antigo. Combustivel, cambio e perfil
se perdem - o esquema antigo nao tinha onde guarda-los.

SQL congelado, sem importar nada de `telemetria/`. A comparacao sem
acento e feita aqui mesmo, com `unicodedata`, para nao depender da
extensao `unaccent` (que exige superusuario para ser criada).
"""

import json
import unicodedata
from pathlib import Path
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009"
down_revision: Union[str, Sequence[str], None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SNAPSHOT = Path(__file__).resolve().parents[1] / "dados" / "0009_catalogo_veiculos.json"
MARCA_OUTRA = "Outra"

COMBUSTIVEL = postgresql.ENUM(
    "GASOLINA", "ETANOL", "FLEX", "DIESEL", "GNV", "HIBRIDO", name="combustivel",
    create_type=False,
)
CAMBIO = postgresql.ENUM(
    "MANUAL", "AUTOMATICO", "AUTOMATIZADO", "CVT", name="cambio", create_type=False
)
PERFIL = postgresql.ENUM(
    "OBD2_GENERICO", "SIEMENS_MS41_DS2", name="perfilecu", create_type=False
)


def _limpo(texto: str) -> str:
    """Espaco nas pontas e repetido, como a normalizacao de entrada."""
    return " ".join((texto or "").split())


def _chave(texto: str) -> str:
    """Para comparar: sem acento, minusculo, espaco colapsado."""
    sem_acento = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    return _limpo(sem_acento).lower()


def _criar_tabelas() -> None:
    op.create_table(
        "marca",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nome", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ux_marca_nome", "marca", [sa.text("lower(nome)")], unique=True)

    op.create_table(
        "modelo",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("marca_id", sa.Integer(), nullable=False),
        sa.Column("nome", sa.String(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["marca_id"], ["marca.id"]),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuario.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_modelo_marca_id", "modelo", ["marca_id"])
    op.create_index("ix_modelo_usuario_id", "modelo", ["usuario_id"])
    op.create_index(
        "ux_modelo_catalogo",
        "modelo",
        ["marca_id", sa.text("lower(nome)")],
        unique=True,
        postgresql_where=sa.text("usuario_id IS NULL"),
    )
    op.create_index(
        "ux_modelo_customizado",
        "modelo",
        ["usuario_id", "marca_id", sa.text("lower(nome)")],
        unique=True,
        postgresql_where=sa.text("usuario_id IS NOT NULL"),
    )


def _carregar_snapshot(con) -> None:
    """A primeira carga do catalogo, do arquivo congelado."""
    catalogo = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    marca_t = sa.table("marca", sa.column("id", sa.Integer), sa.column("nome", sa.String))
    modelo_t = sa.table(
        "modelo",
        sa.column("marca_id", sa.Integer),
        sa.column("nome", sa.String),
        sa.column("usuario_id", sa.Integer),
    )
    for marca in catalogo["marcas"]:
        marca_id = con.execute(
            marca_t.insert().values(nome=marca["nome"]).returning(marca_t.c.id)
        ).scalar_one()
        if marca["modelos"]:
            con.execute(
                modelo_t.insert(),
                [{"marca_id": marca_id, "nome": nome, "usuario_id": None} for nome in marca["modelos"]],
            )
    print(f"[0009] catalogo: {len(catalogo['marcas'])} marcas carregadas do snapshot")


def _casar_veiculos(con) -> None:
    """Aponta cada veiculo existente para um modelo (ver o docstring)."""
    marcas = {
        _chave(nome): mid for mid, nome in con.execute(sa.text("SELECT id, nome FROM marca"))
    }
    outra = marcas[_chave(MARCA_OUTRA)]
    catalogo: dict[tuple[int, str], int] = {}
    for mid, marca_id, nome in con.execute(
        sa.text("SELECT id, marca_id, nome FROM modelo WHERE usuario_id IS NULL")
    ):
        catalogo.setdefault((marca_id, _chave(nome)), mid)

    customizados: dict[tuple[int, int, str], int] = {}
    veiculos = con.execute(
        sa.text("SELECT id, usuario_id, marca, modelo FROM veiculo ORDER BY id")
    ).all()
    for vid, dono, marca, modelo in veiculos:
        marca_id = marcas.get(_chave(marca))
        if marca_id is None:
            marca_id, nome, chave = outra, _limpo(f"{marca} {modelo}"), None
        else:
            nome = _limpo(modelo)
            chave = _chave(modelo)

        modelo_id = catalogo.get((marca_id, chave)) if chave is not None else None
        destino = "catalogo"
        if modelo_id is None:
            destino = "customizado" if marca_id != outra else "Outra"
            k = (dono, marca_id, nome.lower())
            modelo_id = customizados.get(k)
            if modelo_id is None:
                modelo_id = con.execute(
                    sa.text(
                        "INSERT INTO modelo (marca_id, nome, usuario_id) "
                        "VALUES (:m, :n, :u) RETURNING id"
                    ),
                    {"m": marca_id, "n": nome, "u": dono},
                ).scalar_one()
                customizados[k] = modelo_id
        con.execute(
            sa.text("UPDATE veiculo SET modelo_id = :mid WHERE id = :vid"),
            {"mid": modelo_id, "vid": vid},
        )
        print(f"[0009] veiculo {vid}: {marca} / {modelo} -> {destino} (modelo {modelo_id})")


def upgrade() -> None:
    con = op.get_bind()
    _criar_tabelas()
    _carregar_snapshot(con)

    op.add_column("veiculo", sa.Column("modelo_id", sa.Integer(), nullable=True))
    _casar_veiculos(con)
    op.alter_column("veiculo", "modelo_id", nullable=False)
    op.create_foreign_key("veiculo_modelo_id_fkey", "veiculo", "modelo", ["modelo_id"], ["id"])
    op.create_index("ix_veiculo_modelo_id", "veiculo", ["modelo_id"])
    op.drop_column("veiculo", "marca")
    op.drop_column("veiculo", "modelo")

    for tipo in (COMBUSTIVEL, CAMBIO, PERFIL):
        tipo.create(con, checkfirst=False)
    op.add_column("veiculo", sa.Column("combustivel", COMBUSTIVEL, nullable=True))
    op.add_column("veiculo", sa.Column("cambio", CAMBIO, nullable=True))
    op.add_column("veiculo", sa.Column("perfil_ecu", PERFIL, nullable=True))
    op.drop_column("veiculo", "ecu")
    op.drop_column("veiculo", "protocolo")


def downgrade() -> None:
    con = op.get_bind()
    op.add_column("veiculo", sa.Column("ecu", sa.String(), nullable=True))
    op.add_column("veiculo", sa.Column("protocolo", sa.String(), nullable=True))
    op.execute("UPDATE veiculo SET ecu = 'MS41.1', protocolo = 'DS2'")
    op.alter_column("veiculo", "ecu", nullable=False)
    op.alter_column("veiculo", "protocolo", nullable=False)
    op.drop_column("veiculo", "perfil_ecu")
    op.drop_column("veiculo", "cambio")
    op.drop_column("veiculo", "combustivel")
    # O tipo enum sai junto - a 0001 nao fazia isso com o `statussessao`,
    # e e por isso que o downgrade dela nao volta limpo.
    for tipo in (PERFIL, CAMBIO, COMBUSTIVEL):
        tipo.drop(con, checkfirst=False)

    op.add_column("veiculo", sa.Column("marca", sa.String(), nullable=True))
    op.add_column("veiculo", sa.Column("modelo", sa.String(), nullable=True))
    op.execute(
        "UPDATE veiculo v SET marca = ma.nome, modelo = mo.nome "
        "FROM modelo mo JOIN marca ma ON ma.id = mo.marca_id WHERE mo.id = v.modelo_id"
    )
    op.alter_column("veiculo", "marca", nullable=False)
    op.alter_column("veiculo", "modelo", nullable=False)
    op.drop_index("ix_veiculo_modelo_id", table_name="veiculo")
    op.drop_constraint("veiculo_modelo_id_fkey", "veiculo", type_="foreignkey")
    op.drop_column("veiculo", "modelo_id")

    op.drop_index("ux_modelo_customizado", table_name="modelo")
    op.drop_index("ux_modelo_catalogo", table_name="modelo")
    op.drop_index("ix_modelo_usuario_id", table_name="modelo")
    op.drop_index("ix_modelo_marca_id", table_name="modelo")
    op.drop_table("modelo")
    op.drop_index("ux_marca_nome", table_name="marca")
    op.drop_table("marca")
