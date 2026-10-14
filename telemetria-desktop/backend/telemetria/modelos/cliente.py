"""
O dono do carro, na conta de alguem. Nome e contato, e nada mais.

A cadeia de propriedade do sistema inteiro e `veiculo -> cliente ->
usuario`: e por ela que toda consulta de rota filtra. Sessao, amostra e
evento nao tem dono proprio - herdam o do veiculo.

A conta PARTICULAR tem um cliente **implicito**, que e a propria pessoa: o
modelo e o mesmo para os dois papeis, e o que muda e so a interface
esconder o cadastro de clientes. Duas arvores de consulta - uma com
cliente, outra sem - dobrariam cada filtro de veiculo que ja existe.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import CheckConstraint, DateTime
from sqlmodel import Field, SQLModel


class Cliente(SQLModel, table=True):
    # Espelham a migration 0008. O texto chega normalizado pela entrada
    # (rotas/esquemas.py); o banco recusa o que escapar dela.
    __table_args__ = (
        CheckConstraint("nome <> '' AND nome = btrim(nome)", name="ck_cliente_nome"),
        CheckConstraint(
            "contato IS NULL OR (contato <> '' AND contato = btrim(contato))",
            name="ck_cliente_contato",
        ),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    usuario_id: int = Field(foreign_key="usuario.id", index=True)
    nome: str
    # Texto livre - telefone, e-mail, o que a oficina usar. Nao preenchido
    # e NULL, nunca "".
    contato: Optional[str] = None

    # Marca o cliente que o sistema criou sozinho para uma conta
    # PARTICULAR. Serve para a interface nao oferecer "editar cliente" ao
    # PARTICULAR, e para nao criar um segundo implicito quando um
    # PROFISSIONAL vira PARTICULAR.
    implicito: bool = False

    # Soft delete, igual ao do veiculo: nulo = ativo. O cliente arquivado
    # sai da lista e do seletor do formulario de veiculo, mas continua
    # gravado. So se arquiva cliente sem carro ATIVO - quem garante e
    # `rotas/clientes.py`, que devolve 409 com a contagem.
    arquivado_em: Optional[datetime] = Field(default=None, sa_type=DateTime(timezone=True))
