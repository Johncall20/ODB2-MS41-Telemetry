"""Os clientes de uma conta.

Cliente e a raiz da propriedade: `veiculo -> cliente -> usuario`. Por isso
toda funcao aqui recebe `usuario_id` e filtra por ele - nao ha leitura de
cliente "em geral".
"""

from typing import Optional

from sqlmodel import func, select

from ..banco import sessao_db
from ..modelos import Cliente, Veiculo, agora


def listar(
    usuario_id: int, arquivados: bool = False, incluir_implicito: bool = False
) -> list[dict]:
    """Os clientes da conta, com quantos carros ativos cada um tem.

    A contagem vem em SQL, num LEFT JOIN - buscar os veiculos de cada
    cliente em Python seria o N+1 que a convencao do projeto proibe.

    `arquivados` escolhe o lado: False traz so os ativos (a lista e o
    seletor do formulario de veiculo), True so os arquivados (a aba da
    tela). Nunca os dois juntos - nenhuma tela mistura.

    O implicito fica de fora por padrao: ele nao e um cliente que a pessoa
    cadastrou, e sim o "eu mesmo" que o sistema criou para a conta poder
    ter carro proprio.
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
        if arquivados:
            consulta = consulta.where(Cliente.arquivado_em != None)  # noqa: E711
        else:
            consulta = consulta.where(Cliente.arquivado_em == None)  # noqa: E711
        if not incluir_implicito:
            consulta = consulta.where(Cliente.implicito == False)  # noqa: E712
        return [
            {"cliente": cliente, "veiculos": veiculos}
            for cliente, veiculos in db.exec(consulta)
        ]


def buscar(cliente_id: int, usuario_id: int) -> Optional[Cliente]:
    """O cliente, se for desta conta. De outra conta responde None - e o
    que faz a rota devolver 404 em vez de 403: 403 confirmaria que o id
    existe.

    Devolve arquivado e implicito tambem: quem decide se eles servem e a
    rota (o detalhe do carro mostra o cliente que ele tem, seja qual for;
    o seletor de dono so aceita ativo)."""
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


def _editavel(db, cliente_id: int, usuario_id: int) -> Optional[Cliente]:
    """O cliente desta conta que a pessoa cadastrou, numa Session aberta.

    O implicito fica de fora de toda escrita: ele e o "eu mesmo" da conta,
    nao alguem que se edita ou arquiva. Para essas operacoes ele responde
    como inexistente.
    """
    return db.exec(
        select(Cliente).where(
            Cliente.id == cliente_id,
            Cliente.usuario_id == usuario_id,
            Cliente.implicito == False,  # noqa: E712
        )
    ).first()


def editar(cliente_id: int, usuario_id: int, campos: dict) -> Optional[Cliente]:
    """Grava nome e contato. None se o cliente nao e desta conta, ou e o
    implicito."""
    with sessao_db() as db:
        cliente = _editavel(db, cliente_id, usuario_id)
        if cliente is None:
            return None
        for campo, valor in campos.items():
            if campo in ("arquivado_em", "implicito", "usuario_id"):
                continue
            setattr(cliente, campo, valor)
        db.add(cliente)
        db.commit()
        db.refresh(cliente)
        return cliente


def veiculos_ativos(cliente_id: int) -> int:
    """Quantos carros ativos o cliente tem. E o que decide se ele pode ser
    arquivado. So por id: quem chama ja conferiu a posse do cliente."""
    with sessao_db() as db:
        return db.exec(
            select(func.count(Veiculo.id)).where(
                Veiculo.cliente_id == cliente_id,
                Veiculo.arquivado_em == None,  # noqa: E711
            )
        ).one()


def arquivar(cliente_id: int, usuario_id: int) -> Optional[Cliente]:
    """Marca o cliente como arquivado. Arquivar de novo nao mexe na data.

    Nao confere os carros: a regra "sem carro ativo" e a mensagem com a
    contagem sao da rota.
    """
    with sessao_db() as db:
        cliente = _editavel(db, cliente_id, usuario_id)
        if cliente is None:
            return None
        if cliente.arquivado_em is None:
            cliente.arquivado_em = agora()
            db.add(cliente)
            db.commit()
            db.refresh(cliente)
        return cliente


def restaurar(cliente_id: int, usuario_id: int) -> Optional[Cliente]:
    """Zera arquivado_em. None se o cliente nao existe nesta conta."""
    with sessao_db() as db:
        cliente = _editavel(db, cliente_id, usuario_id)
        if cliente is None:
            return None
        cliente.arquivado_em = None
        db.add(cliente)
        db.commit()
        db.refresh(cliente)
        return cliente


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
