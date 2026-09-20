"""
Ambiente do Alembic.

A URL do banco NAO fica no alembic.ini: vem da `DATABASE_URL`, a mesma que
o app usa (`telemetria.banco`). Assim nao existe um segundo lugar dizendo
onde e o banco, que sairia do ar do primeiro na primeira vez que alguem
mudasse so um dos dois.
"""

from logging.config import fileConfig

from alembic import context
from sqlmodel import SQLModel

# Importa o pacote de modelos pelo efeito colateral: e o que registra cada
# tabela no SQLModel.metadata, que o autogenerate compara com o banco.
from telemetria import modelos  # noqa: F401
from telemetria.banco import DATABASE_URL, engine

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    """Gera o SQL sem conectar (`alembic upgrade --sql`)."""
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Roda contra o banco, reusando a engine do app."""
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # Sem isto, mudar o tipo de uma coluna passa despercebido pelo
            # autogenerate - e foi trocar o tipo das datas para
            # TIMESTAMP WITH TIME ZONE que motivou a mudanca para Alembic.
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
