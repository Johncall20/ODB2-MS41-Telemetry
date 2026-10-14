"""
O carro cadastrado, com placa unica entre os ativos. Nunca e apagado:
arquivar preenche `arquivado_em` e preserva as sessoes.
"""

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import CheckConstraint, DateTime, Index, text
from sqlmodel import Field, Relationship, SQLModel

from ..normalizacao import normalizar_placa
from .catalogo import Modelo, descrever
from .comum import agora
from .enums import Cambio, Combustivel, PerfilEcu

if TYPE_CHECKING:
    from .sessao import Sessao

# Reexportado: `from .modelos import normalizar_placa` continua valendo.
__all__ = ["Veiculo", "normalizar_placa"]


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
        # Os CHECKs espelham a migration 0008, que e quem os cria. O teto do
        # ano (o ano corrente) fica so no backend: CHECK com data atual
        # mudaria de significado sozinho, de um ano para o outro.
        CheckConstraint("ano_fabricacao >= 1950", name="ck_veiculo_ano_fabricacao_piso"),
        CheckConstraint(
            "ano_modelo = ano_fabricacao OR ano_modelo = ano_fabricacao + 1",
            name="ck_veiculo_ano_modelo",
        ),
        CheckConstraint(
            "placa IS NULL OR placa ~ '^[A-Z]{3}[0-9][A-Z0-9][0-9]{2}$'",
            name="ck_veiculo_placa_formato",
        ),
        CheckConstraint(
            "motor IS NULL OR (motor <> '' AND motor = btrim(motor))",
            name="ck_veiculo_motor",
        ),
        CheckConstraint("quilometragem >= 0", name="ck_veiculo_quilometragem"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    # Marca e modelo vem do catalogo: o carro aponta para um MODELO, e a
    # marca sai dele. Modelo do catalogo (visivel a todos) ou customizado
    # da propria conta - quem confere e `rotas/veiculos.py`.
    modelo_id: int = Field(foreign_key="modelo.id", index=True)
    # Fabricacao e modelo, como no documento do carro ("1996/1997"). O
    # modelo e o da fabricacao ou o seguinte - o banco confere.
    ano_modelo: int
    ano_fabricacao: int
    # Opcional: carro sem placa (antigo, de pista) grava NULL, nunca "".
    # Com "" o indice unico tratava dois carros sem placa como repetidos.
    placa: Optional[str] = None

    # Campos da tela de veiculo do Figma (node 2:295). Todos opcionais: o
    # carro do TCC e um so e conhecido, mas a tela e a mesma para a oficina
    # que cadastra um carro de cliente sabendo pouco dele.
    motor: Optional[str] = None
    # Nulo = nao informado. Zero e zero km: ate a migration 0011 o 0 fazia
    # as duas vezes, e um carro novo nao tinha como se distinguir de um
    # cadastro sem o campo.
    quilometragem: Optional[int] = None

    # Anulaveis no banco - carro cadastrado antes deles mostra "Nao
    # informado" -, obrigatorios no formulario (`VeiculoEntrada`). Nao ha
    # campo de protocolo: ele e consequencia do perfil da ECU.
    combustivel: Optional[Combustivel] = None
    cambio: Optional[Cambio] = None
    perfil_ecu: Optional[PerfilEcu] = None

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

    # selectin, e nao a carga preguicosa padrao: o objeto volta desanexado
    # da Session, e o nome do carro aparece em toda tela. Com selectin o
    # modelo (e a marca dele) chegam numa consulta a mais por SELECT de
    # veiculo, nao uma por carro.
    modelo: Optional[Modelo] = Relationship(sa_relationship_kwargs={"lazy": "selectin"})

    @property
    def nome_marca(self) -> str:
        return self.modelo.marca.nome if self.modelo and self.modelo.marca else ""

    @property
    def nome_modelo(self) -> str:
        return self.modelo.nome if self.modelo else ""

    def descricao(self) -> str:
        """O nome do carro como as telas, o PDF e o arquivo baixado
        escrevem - sem o "Outra" na marca Outra (`catalogo.descrever`)."""
        return descrever(self.nome_marca, self.nome_modelo)
