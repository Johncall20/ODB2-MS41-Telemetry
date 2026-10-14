"""
O catalogo de marca e modelo. Vem da tabela FIPE (`gerar_catalogo.py` ->
`catalogo_veiculos.json`), e o veiculo aponta para um MODELO - a marca sai
dele.

Modelo tem dois donos possiveis:

- `usuario_id` nulo: item do catalogo, visivel para todas as contas;
- `usuario_id` preenchido: modelo customizado ("Nao encontrei meu
  modelo"), visivel so para aquela conta.

A unicidade sem diferenciar maiusculas vem de indices em `lower(nome)`,
parciais: um para o catalogo, outro por conta. Um nome customizado pode
repetir o de outra conta - cada uma so ve o seu.
"""

from datetime import date
from typing import Optional

from sqlalchemy import CheckConstraint, Index, text
from sqlmodel import Field, Relationship, SQLModel

from ..normalizacao import ANO_MINIMO

# Marca do carro cuja marca nao existe na FIPE. Nao tem modelo de
# catalogo: tudo nela e customizado por conta.
MARCA_OUTRA = "Outra"


def descrever(marca: str, modelo: str) -> str:
    """O nome do carro como toda tela, o PDF e o arquivo baixado escrevem.

    Na marca "Outra" sai so o modelo: "Puma GTE", e nao "Outra Puma GTE" -
    ali o texto do modelo ja e marca e modelo juntos. E o UNICO lugar com
    essa regra; a API devolve o resultado pronto em `descricao`.
    """
    if marca == MARCA_OUTRA:
        return (modelo or "").strip()
    return f"{marca or ''} {modelo or ''}".strip()


class Marca(SQLModel, table=True):
    __table_args__ = (Index("ux_marca_nome", text("lower(nome)"), unique=True),)

    id: Optional[int] = Field(default=None, primary_key=True)
    nome: str


class Modelo(SQLModel, table=True):
    __table_args__ = (
        Index(
            "ux_modelo_catalogo",
            "marca_id",
            text("lower(nome)"),
            unique=True,
            postgresql_where=text("usuario_id IS NULL"),
        ),
        Index(
            "ux_modelo_customizado",
            "usuario_id",
            "marca_id",
            text("lower(nome)"),
            unique=True,
            postgresql_where=text("usuario_id IS NOT NULL"),
        ),
        # Espelham a migration 0012, que e quem os cria.
        CheckConstraint("(ano_min IS NULL) = (ano_max IS NULL)", name="ck_modelo_faixa_completa"),
        CheckConstraint(
            "ano_min IS NULL OR (ano_min >= 1950 AND ano_min <= ano_max)",
            name="ck_modelo_faixa_ordem",
        ),
        CheckConstraint(
            "usuario_id IS NULL OR ano_min IS NULL", name="ck_modelo_faixa_so_catalogo"
        ),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    marca_id: int = Field(foreign_key="marca.id", index=True)
    nome: str
    # Nulo = catalogo. Preenchido = customizado daquela conta, apagado
    # junto com ela (`repositorios/usuarios.excluir`).
    usuario_id: Optional[int] = Field(default=None, foreign_key="usuario.id", index=True)
    # Os anos de modelo em que a FIPE tem esta versao (`gerar_catalogo.py`).
    # Nulos = faixa desconhecida: catalogo ainda parcial, ou customizado,
    # que nunca tem faixa.
    ano_min: Optional[int] = None
    ano_max: Optional[int] = None

    # selectin: o veiculo carrega o modelo, e o modelo a marca, sempre -
    # o nome do carro aparece em toda tela, e o objeto volta desanexado da
    # Session, onde carga preguicosa nao funciona.
    marca: Optional[Marca] = Relationship(sa_relationship_kwargs={"lazy": "selectin"})

    def customizado(self) -> bool:
        return self.usuario_id is not None

    def faixa_anos(self) -> tuple[int, int]:
        """Os anos de modelo aceitos. Sem faixa, a de sempre: do piso ate
        o ano que vem (o modelo pode estar um ano a frente)."""
        if self.ano_min is None or self.ano_max is None:
            return ANO_MINIMO, date.today().year + 1
        return self.ano_min, self.ano_max
