"""
Consultas de veiculo: cadastro, busca, arquivamento e a lista da tela.
Veiculo arquivado fica de fora por padrao; quem precisa dele pede.

**Toda funcao daqui filtra pelo dono.** O carro pertence a um `Cliente`, e
o cliente a um `Usuario`: por isso as consultas atravessam
`veiculo -> cliente -> usuario` com `_do_usuario()`. `usuario_id` e
parametro OBRIGATORIO - `None` e aceito (o `semear.py` e o `--recalcular`
passam None de proposito), mas tem de ser escrito. Esquecer vira TypeError
na hora, em vez de devolver silenciosamente o carro de outra conta.
"""

from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import and_, case, func, or_
from sqlmodel import select

from ..banco import sessao_db
from ..modelos import (
    LIMITES_SUGERIDOS,
    Cliente,
    LimitesVeiculo,
    Sessao,
    Veiculo,
    agora,
    normalizar_placa,
)

# Janela do filtro "recentes". Trinta dias e a mesma da tela de Sessoes.
DIAS_RECENTES = 30

ORDENACOES = ("placa", "modelo", "cliente", "ultima_sessao", "criado_em", "total_sessoes")
DIRECOES = ("asc", "desc")

# Estados que a tela oferece como filtro. Sao combinaveis: marcar dois
# soma os dois conjuntos, nao intersecta - "recentes" e "nunca" juntos nao
# devolveriam nada se fosse E.
SITUACOES = ("recentes", "nunca", "arquivados")


def _dentro(db, veiculo_id: int, usuario_id: Optional[int]) -> Optional[Veiculo]:
    """O veiculo da conta, numa Session ja aberta - para quem vai escrever.

    `db.get()` nao serve aqui: ele acha por id e ignora o dono, e era por
    ele que editar/arquivar/restaurar alcancariam carro de outra conta.
    """
    return db.exec(
        _do_usuario(select(Veiculo).where(Veiculo.id == veiculo_id), usuario_id)
    ).first()


def _do_usuario(consulta, usuario_id: Optional[int]):
    """Recorta a consulta para os carros de uma conta.

    Um WHERE, sem JOIN: `veiculo.usuario_id` guarda o dono desnormalizado
    (ver o comentario no modelo). A cadeia `veiculo -> cliente -> usuario`
    continua sendo a verdade de negocio; esta coluna e a mesma informacao
    onde o indice e o filtro precisam dela.

    `None` nao filtra nada, e e usado so fora da web (seed, recalculo).
    """
    if usuario_id is None:
        return consulta
    return consulta.where(Veiculo.usuario_id == usuario_id)


def listar(usuario_id: Optional[int], incluir_arquivados: bool = False) -> list[Veiculo]:
    """Todos os veiculos, sem filtro nem agregado.

    E a lista crua, para quem so precisa preencher um seletor. A tela de
    Veiculos usa listar_para_tela(), que traz o resumo das sessoes junto.
    """
    with sessao_db() as db:
        consulta = _do_usuario(select(Veiculo), usuario_id).order_by(Veiculo.id)
        if not incluir_arquivados:
            consulta = consulta.where(Veiculo.arquivado_em == None)  # noqa: E711
        return list(db.exec(consulta))


def listar_para_tela(
    usuario_id: Optional[int],
    busca: str = "",
    ordenar_por: str = "ultima_sessao",
    direcao: str = "desc",
    situacoes: Optional[list[str]] = None,
    incluir_arquivados: bool = False,
) -> list[dict]:
    """Linhas da tela de Veiculos: o carro mais o agregado das sessoes.

    Dicionario e nao modelo porque total e ultima sessao saem de um LEFT
    JOIN. `situacoes` soma com OR e vai no HAVING, nao no WHERE.
    """
    total = func.count(Sessao.id)
    ultima = func.max(Sessao.iniciada_em)

    # O nome do cliente vem no mesmo SELECT: buscar por linha seria o N+1
    # que a convencao do projeto proibe. LEFT JOIN porque carro sem
    # cliente existe em banco migrado sem conta (ver a migration 0004).
    consulta = (
        select(
            Veiculo,
            Cliente.nome.label("cliente"),
            total.label("total_sessoes"),
            ultima.label("ultima_sessao"),
        )
        .join(Cliente, Cliente.id == Veiculo.cliente_id, isouter=True)
        .join(Sessao, Sessao.veiculo_id == Veiculo.id, isouter=True)
        .group_by(Veiculo.id, Cliente.nome)
    )
    consulta = _do_usuario(consulta, usuario_id)

    situacoes = [s for s in (situacoes or []) if s in SITUACOES]

    # Arquivado continua fora por padrao. Ele so entra quando quem chama
    # pediu a lista inteira (incluir_arquivados, que e o seletor de veiculo
    # da tela de Sessoes) ou quando "arquivados" e uma das situacoes
    # escolhidas - senao o proprio filtro se anularia no WHERE.
    if not incluir_arquivados and "arquivados" not in situacoes:
        consulta = consulta.where(Veiculo.arquivado_em == None)  # noqa: E711

    termo = (busca or "").strip()
    if termo:
        # A placa e guardada normalizada; o resto casa como foi digitado.
        alvo = f"%{termo.lower()}%"
        placa_alvo = f"%{normalizar_placa(termo)}%"
        consulta = consulta.where(
            func.lower(Veiculo.placa).like(func.lower(placa_alvo))
            | func.lower(Veiculo.modelo).like(alvo)
            | func.lower(Cliente.nome).like(alvo)
        )

    if situacoes:
        corte = agora() - timedelta(days=DIAS_RECENTES)
        ativo = Veiculo.arquivado_em == None  # noqa: E711
        predicados = {
            # "recente" e "nunca" descrevem carro em uso; arquivado tem
            # secao propria e nao deve aparecer nos dois primeiros so por
            # ter (ou nao ter) sessao.
            "recentes": and_(ativo, ultima >= corte),
            "nunca": and_(ativo, total == 0),
            "arquivados": Veiculo.arquivado_em != None,  # noqa: E711
        }
        consulta = consulta.having(or_(*[predicados[s] for s in situacoes]))

    colunas = {
        "placa": Veiculo.placa,
        "modelo": Veiculo.modelo,
        "cliente": func.lower(Cliente.nome),
        "criado_em": Veiculo.criado_em,
        "ultima_sessao": ultima,
        "total_sessoes": total,
    }
    coluna = colunas.get(ordenar_por, ultima)
    alvo = coluna.desc() if direcao == "desc" else coluna.asc()

    if ordenar_por == "ultima_sessao":
        # Carro que nunca rodou vai para o fim nos dois sentidos: "sem
        # data" nao e uma data pequena nem grande, e alternar a direcao
        # nao deveria trazer os vazios para o topo.
        consulta = consulta.order_by(case((ultima.is_(None), 1), else_=0), alvo)
    else:
        consulta = consulta.order_by(alvo)

    with sessao_db() as db:
        return [
            {"veiculo": v, "cliente": cliente, "total_sessoes": n, "ultima_sessao": quando}
            for v, cliente, n, quando in db.exec(consulta).all()
        ]


def buscar(
    veiculo_id: int, usuario_id: Optional[int], incluir_arquivados: bool = False
) -> Optional[Veiculo]:
    """O veiculo, ou None. Volta desanexado da Session: os atributos ja
    carregados continuam legiveis, mas as relacoes preguicosas nao.

    Carro de outra conta responde None, igual a carro inexistente - e o
    que faz a rota devolver 404 em vez de 403. Um 403 confirmaria que o id
    existe, que e exatamente o que nao se quer contar.
    """
    with sessao_db() as db:
        consulta = _do_usuario(select(Veiculo).where(Veiculo.id == veiculo_id), usuario_id)
        if not incluir_arquivados:
            consulta = consulta.where(Veiculo.arquivado_em == None)  # noqa: E711
        return db.exec(consulta).first()


def buscar_por_placa(
    placa: str, usuario_id: Optional[int], incluir_arquivados: bool = True
) -> Optional[Veiculo]:
    """Veiculo com essa placa. Inclui arquivado por padrao, ao contrario
    do resto do modulo: quem chama e a checagem de duplicata, que precisa
    justamente enxergar o arquivado para oferecer a restauracao."""
    if not placa:
        return None
    with sessao_db() as db:
        consulta = _do_usuario(select(Veiculo).where(Veiculo.placa == placa), usuario_id)
        if not incluir_arquivados:
            consulta = consulta.where(Veiculo.arquivado_em == None)  # noqa: E711
        return db.exec(consulta.order_by(Veiculo.arquivado_em)).first()


def criar(veiculo: Veiculo) -> Veiculo:
    """Grava o veiculo novo e devolve com o id preenchido.

    Placa repetida estoura IntegrityError pelo indice unico parcial; quem
    trata e a rota, que sabe distinguir ativo de arquivado.
    """
    with sessao_db() as db:
        db.add(veiculo)
        db.commit()
        db.refresh(veiculo)
        # Os limites do carro nascem na MESMA transacao: em dois commits
        # haveria um instante com veiculo sem limites, e um GET nessa
        # janela quebraria - os seis campos nao sao mais opcionais.
        db.add(LimitesVeiculo(veiculo_id=veiculo.id, **LIMITES_SUGERIDOS))
        db.commit()
        db.refresh(veiculo)
        return veiculo


def editar(veiculo_id: int, usuario_id: Optional[int], campos: dict) -> Optional[Veiculo]:
    """Grava os campos do formulario.

    arquivado_em nao entra: senao um PUT desarquivaria sem querer.
    """
    with sessao_db() as db:
        veiculo = _dentro(db, veiculo_id, usuario_id)
        if veiculo is None:
            return None
        for campo, valor in campos.items():
            if campo == "arquivado_em":
                continue
            setattr(veiculo, campo, valor)
        db.add(veiculo)
        db.commit()
        db.refresh(veiculo)
        return veiculo


def arquivar(veiculo_id: int, usuario_id: Optional[int]) -> Optional[datetime]:
    """Marca o veiculo como arquivado e devolve o instante gravado.

    Nao apaga linha nenhuma: as sessoes, amostras e eventos continuam onde
    estavam. Arquivar de novo nao mexe na data original.
    """
    with sessao_db() as db:
        veiculo = _dentro(db, veiculo_id, usuario_id)
        if veiculo is None:
            return None
        if veiculo.arquivado_em is None:
            veiculo.arquivado_em = agora()
            db.add(veiculo)
            db.commit()
            db.refresh(veiculo)
        return veiculo.arquivado_em


def restaurar(veiculo_id: int, usuario_id: Optional[int]) -> bool:
    """Zera arquivado_em. Devolve False se o veiculo nem existe."""
    with sessao_db() as db:
        veiculo = _dentro(db, veiculo_id, usuario_id)
        if veiculo is None:
            return False
        veiculo.arquivado_em = None
        db.add(veiculo)
        db.commit()
        return True
