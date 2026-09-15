"""
O carro cadastrado, com placa unica entre os ativos. Nunca e apagado:
arquivar preenche `arquivado_em` e preserva as sessoes.
"""

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Index, text
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

    # Unicidade so entre os ativos: arquivar libera a placa, e o mesmo
    # carro pode ser cadastrado de novo depois - ou restaurado, que e o
    # que a tela oferece.
    __table_args__ = (
        Index(
            "ix_veiculo_placa_ativa",
            "placa",
            unique=True,
            sqlite_where=text("arquivado_em IS NULL"),
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
    cliente: str = ""

    criado_em: datetime = Field(default_factory=agora)

    # Soft delete: nulo = ativo. O veiculo sai das listas mas as sessoes
    # dele continuam gravadas e acessiveis - o historico e o dado que o
    # TCC precisa defender, entao nada e removido de verdade.
    arquivado_em: Optional[datetime] = None

    sessoes: List["Sessao"] = Relationship(back_populates="veiculo")
