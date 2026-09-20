"""
O carro cadastrado, com placa unica entre os ativos. Nunca e apagado:
arquivar preenche `arquivado_em` e preserva as sessoes.
"""

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import DateTime, Index, text
from sqlmodel import Field, Relationship, SQLModel

from .comum import agora

if TYPE_CHECKING:
    from .sessao import Sessao


def normalizar_placa(bruta: str) -> str:
    """Placa como ela e guardada: maiuscula e sem separador.

    "abc-1234", "ABC 1234" e "abc.1234" tem de dar a mesma linha. O hifen
    volta so na exibicao.
    """
    return "".join(c for c in (bruta or "").upper() if c.isalnum())


class Veiculo(SQLModel, table=True):
    """Um carro do cadastro.

    A placa e guardada normalizada (maiuscula, sem separador) - e o que
    permite a busca casar e o indice unico funcionar.
    """

    # Unicidade da placa **por conta**, e so entre os ativos: arquivar
    # libera a placa, e o mesmo carro pode ser cadastrado de novo depois -
    # ou restaurado, que e o que a tela oferece.
    #
    # `usuario_id` entra no indice, e e por isso que ele existe como coluna
    # desta tabela mesmo o dono ja vindo por `cliente -> usuario`:
    # unicidade por conta e garantia que tem de morar no banco, e o
    # Postgres so indexa coluna da propria tabela. Por `(cliente_id,
    # placa)` o mesmo mecanico duplicaria a placa entre dois clientes - que
    # e justamente o erro de digitacao que o indice existe para pegar.
    __table_args__ = (
        Index(
            "ix_veiculo_placa_ativa",
            "usuario_id",
            "placa",
            unique=True,
            postgresql_where=text("arquivado_em IS NULL"),
        ),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    marca: str
    modelo: str
    ano: int
    placa: str
    ecu: str = "MS41.1"

    # Campos da tela de veiculo do Figma (node 2:295). Todos opcionais: o
    # carro do TCC e um so e conhecido, mas a tela e a mesma para a oficina
    # que cadastra um carro de cliente sabendo pouco dele.
    motor: str = ""
    protocolo: str = "DS2"
    quilometragem: int = 0

    # O dono, em dois campos que TEM DE CONCORDAR:
    # `veiculo.usuario_id == veiculo.cliente.usuario_id`.
    #
    # `cliente_id` e a relacao de negocio - de quem e o carro. `usuario_id`
    # e a mesma informacao desnormalizada, e existe por duas razoes: o
    # indice unico da placa por conta (acima), e tirar um JOIN de toda
    # consulta filtrada por dono. Quem garante a concordancia e
    # `rotas/veiculos.py`, que so aceita cliente da propria conta - ver
    # "Propriedade" no CLAUDE.md.
    #
    # `cliente_id` continua anulavel: a migration 0004 nao tinha a quem
    # atribuir carro de um banco sem conta nenhuma.
    usuario_id: int = Field(foreign_key="usuario.id", index=True)
    cliente_id: Optional[int] = Field(default=None, foreign_key="cliente.id", index=True)

    criado_em: datetime = Field(default_factory=agora, sa_type=DateTime(timezone=True))

    # Soft delete: nulo = ativo. O veiculo sai das listas mas as sessoes
    # dele continuam gravadas e acessiveis - o historico e o dado que o
    # TCC precisa defender, entao nada e removido de verdade.
    arquivado_em: Optional[datetime] = Field(default=None, sa_type=DateTime(timezone=True))

    sessoes: List["Sessao"] = Relationship(back_populates="veiculo")
