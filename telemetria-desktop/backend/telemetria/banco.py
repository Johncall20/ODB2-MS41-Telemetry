"""
Conexao com o SQLite (~/.telemetria-ds2/dados.db) e a migracao pobre do
esquema. So sabe ACRESCENTAR coluna e indice, nunca remover nem trocar.
"""

import os
from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine, select

from .modelos import Limites

CAMINHO_DB = Path(os.environ.get("TELEMETRIA_DB", Path.home() / ".telemetria-ds2" / "dados.db"))
CAMINHO_DB.parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    f"sqlite:///{CAMINHO_DB}",
    connect_args={"check_same_thread": False},
)


def _completar_colunas() -> None:
    """Acrescenta ao banco existente as colunas que o modelo ganhou depois.

    O create_all() nunca mexe em tabela existente, entao sem isto um
    dados.db antigo levaria "no such column". So sabe ADICIONAR coluna.
    """
    with engine.begin() as con:
        for tabela in SQLModel.metadata.sorted_tables:
            existe = con.exec_driver_sql(f"PRAGMA table_info({tabela.name})").fetchall()
            if not existe:
                continue                       # tabela nova, ja veio completa
            presentes = {linha[1] for linha in existe}
            for coluna in tabela.columns:
                if coluna.name in presentes:
                    continue
                tipo = coluna.type.compile(engine.dialect)
                trecho = f"ALTER TABLE {tabela.name} ADD COLUMN {coluna.name} {tipo}"
                padrao = getattr(coluna.default, "arg", None)
                if not coluna.nullable:
                    if padrao is None or callable(padrao):
                        # Sem default utilizavel, entra como nula para nao
                        # quebrar as linhas que ja estao gravadas.
                        pass
                    else:
                        literal = f"'{padrao}'" if isinstance(padrao, str) else padrao
                        trecho += f" NOT NULL DEFAULT {literal}"
                con.exec_driver_sql(trecho)


def _completar_indices() -> None:
    """Cria os indices que o modelo declarou depois da tabela ja existir.

    Indice unico que falha = duplicata ja gravada: avisa e o app sobe
    assim mesmo, porque a rota continua barrando duplicata nova.
    """
    with engine.begin() as con:
        existentes = {
            linha[0]
            for linha in con.exec_driver_sql(
                "SELECT name FROM sqlite_master WHERE type='index'"
            )
        }
        for tabela in SQLModel.metadata.sorted_tables:
            for indice in tabela.indexes:
                if indice.name in existentes:
                    continue
                try:
                    indice.create(bind=con)
                except Exception as erro:
                    print(f"[banco] nao foi possivel criar o indice {indice.name}: {erro}")


def criar_tabelas() -> None:
    """Deixa o banco pronto: tabelas, colunas, indices e limites.

    Roda a cada inicio; barato quando nao ha nada a fazer.
    """
    SQLModel.metadata.create_all(engine)
    _completar_colunas()
    _completar_indices()
    with Session(engine) as s:
        if s.exec(select(Limites)).first() is None:
            s.add(Limites(id=1))
            s.commit()


def sessao_db() -> Session:
    """Abre uma conexao com o banco. So os repositorios chamam isto."""
    return Session(engine)
