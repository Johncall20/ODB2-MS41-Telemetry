"""
A conta que usa o app. E-mail unico, senha guardada so como hash.

O hash NUNCA sai daqui por rota nenhuma: quem monta a resposta e
`rotas/esquemas.usuario_publico()`, que escolhe campo a campo em vez de
serializar o modelo inteiro - assim acrescentar coluna sensivel amanha nao
a publica por descuido.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import CheckConstraint, DateTime, Index, text
from sqlmodel import Field, SQLModel

from .comum import agora
from .enums import PapelUsuario


class Usuario(SQLModel, table=True):
    # Espelham a migration 0008. O CHECK de minusculas mais o indice em
    # lower(email) e o que garante unicidade sem diferenciar maiusculas no
    # proprio banco, e nao so na entrada.
    __table_args__ = (
        CheckConstraint("nome <> '' AND nome = btrim(nome)", name="ck_usuario_nome"),
        CheckConstraint("email = lower(email)", name="ck_usuario_email_minusculo"),
        Index("ux_usuario_email_lower", text("lower(email)"), unique=True),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    nome: str
    # Guardado em minusculas e sem espaco nas pontas (normalizado na
    # entrada, em rotas/esquemas.py): senao "Leo@x.com" e "leo@x.com"
    # virariam duas contas, e a pessoa nao entenderia por que o login
    # falha.
    email: str = Field(unique=True, index=True)
    senha_hash: str
    papel: PapelUsuario = PapelUsuario.PROFISSIONAL
    criado_em: datetime = Field(default_factory=agora, sa_type=DateTime(timezone=True))
