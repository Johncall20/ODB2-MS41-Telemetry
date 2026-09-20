"""
A conta que usa o app. E-mail unico, senha guardada so como hash.

O hash NUNCA sai daqui por rota nenhuma: quem monta a resposta e
`rotas/esquemas.usuario_publico()`, que escolhe campo a campo em vez de
serializar o modelo inteiro - assim acrescentar coluna sensivel amanha nao
a publica por descuido.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime
from sqlmodel import Field, SQLModel

from .comum import agora
from .enums import PapelUsuario


class Usuario(SQLModel, table=True):
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
