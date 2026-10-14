"""
Um login em curso. O nome nao e `Sessao` de proposito: neste projeto
`Sessao` e a GRAVACAO do carro, e reusar a palavra tornaria ambiguo o
vocabulario central do dominio.

Token opaco em tabela, e nao JWT. A razao e o logout: JWT so se revoga com
uma denylist, que traz de volta o estado no servidor que o JWT existia para
evitar. Aqui sair e apagar a linha, e a proxima requisicao nao encontra
nada.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import CheckConstraint, DateTime
from sqlmodel import Field, SQLModel

from .comum import agora


class TokenAcesso(SQLModel, table=True):
    # Espelha a migration 0008: token que nasce vencido nao serve a nada.
    __table_args__ = (
        CheckConstraint("expira_em > criado_em", name="ck_tokenacesso_validade"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)

    # O HASH do token, nunca o token. Quem tiver o banco nao consegue se
    # passar por ninguem - a mesma razao de a senha ser hash. O valor cru
    # existe uma vez so, na resposta do login, e some da memoria depois.
    token_hash: str = Field(unique=True, index=True)

    usuario_id: int = Field(foreign_key="usuario.id", index=True)
    criado_em: datetime = Field(default_factory=agora, sa_type=DateTime(timezone=True))

    # Validade unica e fixa: nao ha "manter conectado" nesta fase. Quando
    # houver, e este campo que passa a variar - nao um segundo tipo de
    # token.
    expira_em: datetime = Field(sa_type=DateTime(timezone=True))
