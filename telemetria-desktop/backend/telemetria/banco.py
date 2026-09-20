"""
Conexao com o PostgreSQL. So isso.

O esquema **nao** e criado aqui: quem cria e muda tabela e o Alembic, em
`migracoes/`. Antes este modulo tinha uma migracao pobre feita a mao
(`criar_tabelas`, `_completar_colunas`, `_completar_indices`) que so sabia
ACRESCENTAR coluna e indice - nunca remover nem trocar tipo. Com o Alembic
essa limitacao acaba, e some junto a divergencia entre o esquema de um
banco novo e o de um migrado.
"""

import os

from sqlmodel import Session, create_engine

# Importado pelo efeito colateral: e o import do pacote que registra cada
# tabela no SQLModel.metadata, que o `migracoes/env.py` compara com o banco
# para gerar migration.
from . import modelos  # noqa: F401

# Padrao de desenvolvimento: o Postgres que o `docker compose up` sobe. O
# compose publica a 5432 justamente porque o backend roda na maquina, e nao
# em container - e o unico jeito de ele ler a central por BLE.
URL_PADRAO = "postgresql+psycopg://telemetria:telemetria@localhost:5432/telemetria"

DATABASE_URL = os.environ.get("DATABASE_URL", URL_PADRAO)

# pool_pre_ping porque o banco pode reiniciar debaixo do app: ele vive num
# container que se derruba e sobe a vontade, enquanto o backend continua no
# ar. Sem isto, uma conexao morta no pool derrubaria a primeira requisicao
# depois do restart em vez de reconectar.
engine = create_engine(DATABASE_URL, pool_pre_ping=True)


def sessao_db() -> Session:
    """Abre uma conexao com o banco. So os repositorios chamam isto."""
    return Session(engine)
