"""Os clientes de uma conta.

Cliente e a raiz da propriedade: `veiculo -> cliente -> usuario`. Por isso
toda funcao aqui recebe `usuario_id` e filtra por ele - nao ha leitura de
cliente "em geral".
"""

from typing import Optional

from sqlmodel import func, select

from ..banco import sessao_db
from ..modelos import Cliente, Veiculo


def listar(usuario_id: int, incluir_implicito: bool = False) -> list[dict]:
    """Os clientes da conta, com quantos carros cada um tem.

    A contagem vem em SQL, num LEFT JOIN - buscar os veiculos de cada
    cliente em Python seria o N+1 que a convencao do projeto proibe.

    O implicito fica de fora por padrao: ele nao e um cliente que a pessoa
    cadastrou, e sim o "eu mesmo" que o sistema criou para a conta
    PARTICULAR poder ter carro.
    """
    with sessao_db() as db:
        consulta = (
            select(Cliente, func.count(Veiculo.id).label("veiculos"))
            .join(
                Veiculo,
                (Veiculo.cliente_id == Cliente.id) & (Veiculo.arquivado_em == None),  # noqa: E711
                isouter=True,
            )
            .where(Cliente.usuario_id == usuario_id)
            .group_by(Cliente.id)
            .order_by(func.lower(Cliente.nome))
        )
        if not incluir_implicito:
            consulta = consulta.where(Cliente.implicito == False)  # noqa: E712
        return [
            {"cliente": cliente, "veiculos": veiculos}
            for cliente, veiculos in db.exec(consulta)
        ]


def buscar(cliente_id: int, usuario_id: int) -> Optional[Cliente]:
    """O cliente, se for desta conta. De outra conta responde None - e o
    que faz a rota devolver 404 em vez de 403: 403 confirmaria que o id
    existe."""
    with sessao_db() as db:
        return db.exec(
            select(Cliente).where(
                Cliente.id == cliente_id, Cliente.usuario_id == usuario_id
            )
        ).first()


def criar(usuario_id: int, nome: str, contato: str = "", implicito: bool = False) -> Cliente:
    """Grava um cliente na conta."""
    with sessao_db() as db:
        cliente = Cliente(
            usuario_id=usuario_id, nome=nome, contato=contato, implicito=implicito
        )
        db.add(cliente)
        db.commit()
        db.refresh(cliente)
        return cliente


def editar(cliente_id: int, usuario_id: int, campos: dict) -> Optional[Cliente]:
    """Grava nome e contato. None se o cliente nao e desta conta."""
    with sessao_db() as db:
        cliente = db.exec(
            select(Cliente).where(
                Cliente.id == cliente_id, Cliente.usuario_id == usuario_id
            )
        ).first()
        if cliente is None:
            return None
        for campo, valor in campos.items():
            setattr(cliente, campo, valor)
        db.add(cliente)
        db.commit()
        db.refresh(cliente)
        return cliente


def contar(usuario_id: int, incluir_implicito: bool = False) -> int:
    """Quantos clientes a conta tem.

    Quem usa e o aviso de trocar PROFISSIONAL -> PARTICULAR, que precisa
    dizer quantos vao sumir da interface.
    """
    with sessao_db() as db:
        consulta = select(func.count(Cliente.id)).where(Cliente.usuario_id == usuario_id)
        if not incluir_implicito:
            consulta = consulta.where(Cliente.implicito == False)  # noqa: E712
        return db.exec(consulta).one()


def implicito_de(usuario_id: int, nome: str) -> Cliente:
    """O cliente "eu mesmo" da conta, criando se ainda nao existir.

    E o que permite a conta PARTICULAR ter carro sem nunca ver a palavra
    "cliente": o modelo continua sendo `veiculo -> cliente -> usuario`, e
    so a interface esconde o meio do caminho.

    Idempotente de proposito: um PROFISSIONAL que vira PARTICULAR cai aqui
    e recebe o implicito dele, sem ganhar um segundo a cada carro novo.
    """
    with sessao_db() as db:
        achado = db.exec(
            select(Cliente).where(
                Cliente.usuario_id == usuario_id,
                Cliente.implicito == True,  # noqa: E712
            )
        ).first()
        if achado is not None:
            return achado
        cliente = Cliente(usuario_id=usuario_id, nome=nome, implicito=True)
        db.add(cliente)
        db.commit()
        db.refresh(cliente)
        return cliente
