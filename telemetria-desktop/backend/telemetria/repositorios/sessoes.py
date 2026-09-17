"""Ciclo de vida da sessao: abrir, fechar, descartar, e os eventos dela.
Mexe aqui quem mudar o que acontece ao iniciar ou encerrar uma gravacao.
Os limites saem de `repositorios/limites.py`; aqui eles so entram gravados,
como o snapshot que `criar()` recebe.
"""

from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import Float, case, func, or_
from sqlmodel import select

from ..banco import sessao_db
from ..modelos import (
    Evento,
    Sessao,
    StatusSessao,
    TipoEvento,
    agora,
)

# INICIO_SESSAO e FIM_SESSAO existem em toda sessao. Contar os dois na
# coluna "eventos" faria toda sessao parecer ter dois eventos.
EVENTOS_DE_ROTINA = (TipoEvento.INICIO_SESSAO, TipoEvento.FIM_SESSAO)

PERIODOS = {"7d": 7, "30d": 30, "90d": 90, "tudo": None}
ORDENACOES = ("data", "duracao", "rpm_maximo", "eventos")
DIRECOES = ("asc", "desc")


def _colunas_derivadas():
    """Colunas derivadas para filtrar e ordenar a lista de sessoes.

    Saem das colunas gravadas, entao sessao sem agregado vem NULL e cai
    fora dos filtros. Espelham exportador.resumo(): mexeu aqui, mexa la.
    """
    eventos = (
        select(func.count(Evento.id))
        .where(Evento.sessao_id == Sessao.id, Evento.tipo.notin_(EVENTOS_DE_ROTINA))
        .scalar_subquery()
    )
    integridade = case(
        (
            Sessao.total_amostras > 0,
            func.cast(Sessao.amostras_completas, Float)
            * 100.0
            / func.cast(Sessao.total_amostras, Float),
        ),
        else_=None,
    )
    # Sessao aberta conta ate agora.
    duracao = (
        func.julianday(func.coalesce(Sessao.encerrada_em, agora()))
        - func.julianday(Sessao.iniciada_em)
    ) * 86400.0

    return {
        "duracao": duracao,
        "rpm_maximo": Sessao.rpm_pico,
        "eventos": eventos,
        "integridade": integridade,
    }


def listar_para_tela(
    veiculo_id: Optional[int] = None,
    periodo: str = "tudo",
    data_inicio: Optional[datetime] = None,
    data_fim: Optional[datetime] = None,
    tipos_evento: Optional[list[str]] = None,
    sem_eventos: bool = False,
    duracao_minima_s: Optional[float] = None,
    integridade_minima: Optional[float] = None,
    ordenar_por: str = "data",
    direcao: str = "desc",
) -> list[Sessao]:
    """Sessoes da tela, ja filtradas e ordenadas pelo banco.

    Tipos de evento e `sem_eventos` somam com OR, nao intersectam. Evento
    de rotina nao conta para `sem_eventos` - existe em toda sessao.
    """
    d = _colunas_derivadas()
    consulta = select(Sessao)

    if veiculo_id is not None:
        consulta = consulta.where(Sessao.veiculo_id == veiculo_id)

    # Intervalo explicito manda; periodo e o atalho.
    if data_inicio is not None or data_fim is not None:
        if data_inicio is not None:
            consulta = consulta.where(Sessao.iniciada_em >= data_inicio)
        if data_fim is not None:
            consulta = consulta.where(Sessao.iniciada_em <= data_fim)
    else:
        dias = PERIODOS.get(periodo)
        if dias is not None:
            consulta = consulta.where(Sessao.iniciada_em >= agora() - timedelta(days=dias))

    recortes = []
    if tipos_evento:
        recortes.append(
            select(Evento.id)
            .where(Evento.sessao_id == Sessao.id, Evento.tipo.in_(tipos_evento))
            .exists()
        )
    if sem_eventos:
        recortes.append(
            ~select(Evento.id)
            .where(Evento.sessao_id == Sessao.id, Evento.tipo.notin_(EVENTOS_DE_ROTINA))
            .exists()
        )
    if recortes:
        consulta = consulta.where(or_(*recortes))

    if duracao_minima_s is not None:
        consulta = consulta.where(d["duracao"] >= duracao_minima_s)

    if integridade_minima is not None:
        consulta = consulta.where(d["integridade"] >= integridade_minima)

    coluna = {
        "data": Sessao.iniciada_em,
        "duracao": d["duracao"],
        "rpm_maximo": d["rpm_maximo"],
        "eventos": d["eventos"],
    }.get(ordenar_por, Sessao.iniciada_em)
    alvo = coluna.desc() if direcao == "desc" else coluna.asc()

    if ordenar_por == "rpm_maximo":
        # Sessao sem nenhuma leitura de rpm valida nao tem pico; vai para
        # o fim nos dois sentidos, como "nunca gravou" na tela de veiculos.
        consulta = consulta.order_by(case((d["rpm_maximo"].is_(None), 1), else_=0), alvo)
    else:
        consulta = consulta.order_by(alvo)

    with sessao_db() as db:
        return list(db.exec(consulta))


def buscar(sessao_id: int) -> Optional[Sessao]:
    """A sessao pelo id, ou None. Volta desanexada da Session."""
    with sessao_db() as db:
        return db.get(Sessao, sessao_id)


def listar(veiculo_id: Optional[int] = None) -> list[Sessao]:
    """Sessoes, opcionalmente so as de um veiculo, da mais recente para a
    mais antiga. Sessao de veiculo arquivado continua aparecendo: arquivar
    o carro nao esconde o que ele gravou."""
    with sessao_db() as db:
        consulta = select(Sessao)
        if veiculo_id is not None:
            consulta = consulta.where(Sessao.veiculo_id == veiculo_id)
        return list(db.exec(consulta.order_by(Sessao.iniciada_em.desc())))


def criar(
    veiculo_id: int, observacao: str = "", snapshot: Optional[dict] = None
) -> Sessao:
    """Abre a sessao e registra o evento de inicio.

    Sao dois commits, como antes: o primeiro precisa fechar para a sessao
    ganhar id, que o evento referencia.

    `snapshot` sao as colunas `limite_*` ja resolvidas - quem busca o
    efetivo do carro e o gravador, para a decisao de qual limite vale
    ficar num lugar so.
    """
    with sessao_db() as db:
        sessao = Sessao(veiculo_id=veiculo_id, observacao=observacao, **(snapshot or {}))
        db.add(sessao)
        db.commit()
        db.refresh(sessao)
        db.add(
            Evento(
                sessao_id=sessao.id,
                tipo=TipoEvento.INICIO_SESSAO,
                mensagem="gravacao iniciada",
            )
        )
        db.commit()
        db.refresh(sessao)
        return sessao


def encerrar(sessao_id: int, agregados: Optional[dict] = None) -> None:
    """Fecha a sessao, grava os agregados e registra o evento de fim.

    Status e agregados na MESMA transacao: em dois commits haveria uma
    janela com a sessao encerrada e sem agregado, e a tela mostraria zero.
    """
    with sessao_db() as db:
        sessao = db.get(Sessao, sessao_id)
        if sessao is None:
            return
        sessao.status = StatusSessao.ENCERRADA
        sessao.encerrada_em = agora()
        for campo, valor in (agregados or {}).items():
            setattr(sessao, campo, valor)
        db.add(sessao)
        db.add(
            Evento(
                sessao_id=sessao_id,
                tipo=TipoEvento.FIM_SESSAO,
                mensagem="gravacao encerrada",
            )
        )
        db.commit()


def descartar(sessao_id: int) -> None:
    """Apaga a sessao inteira.

    Delete do ORM de proposito: o cascade leva amostras e eventos junto.
    """
    with sessao_db() as db:
        sessao = db.get(Sessao, sessao_id)
        if sessao is None:
            return
        db.delete(sessao)
        db.commit()


def registrar_eventos(eventos: list[Evento]) -> list[Evento]:
    """Grava os eventos e devolve com id e criado_em preenchidos, para o
    gravador poder anuncia-los no websocket."""
    if not eventos:
        return []
    with sessao_db() as db:
        for e in eventos:
            db.add(e)
        db.commit()
        for e in eventos:
            db.refresh(e)
        return eventos


def listar_eventos(sessao_id: int) -> list[Evento]:
    """Eventos da sessao na ordem em que foram gravados. A ordem e do SQL
    e nao do chamador: e ela que define qual anomalia a tela mostra
    primeiro no "+N" de eventos_notaveis()."""
    with sessao_db() as db:
        return list(
            db.exec(select(Evento).where(Evento.sessao_id == sessao_id).order_by(Evento.id))
        )


def gravar_agregados(sessao_id: int, agregados: dict) -> bool:
    """Grava agregados numa sessao ja encerrada (so o --recalcular usa;
    no fluxo normal quem grava e encerrar()). False se a sessao sumiu."""
    with sessao_db() as db:
        sessao = db.get(Sessao, sessao_id)
        if sessao is None:
            return False
        for campo, valor in agregados.items():
            setattr(sessao, campo, valor)
        db.add(sessao)
        db.commit()
        return True


def ids_sem_agregados() -> list[int]:
    """Sessoes encerradas ainda sem agregado - o alvo do --recalcular.

    Enquanto estiverem aqui, ficam de fora dos filtros por pico e
    integridade.
    """
    with sessao_db() as db:
        return list(
            db.exec(
                select(Sessao.id)
                .where(
                    Sessao.status == StatusSessao.ENCERRADA,
                    Sessao.total_amostras == None,  # noqa: E711
                )
                .order_by(Sessao.id)
            )
        )


def ids_encerradas() -> list[int]:
    """Toda sessao encerrada, com agregado ou sem. E o alvo do
    `--recalcular tudo`, para quando a regra de calculo mudar."""
    with sessao_db() as db:
        return list(
            db.exec(
                select(Sessao.id)
                .where(Sessao.status == StatusSessao.ENCERRADA)
                .order_by(Sessao.id)
            )
        )


def contar_eventos(sessao_id: int) -> int:
    """Quantos eventos a sessao tem, os de rotina inclusive - e o numero
    que o resumo() sempre reportou. COUNT no banco: quem chama quer o
    total, nao os objetos."""
    with sessao_db() as db:
        return db.exec(
            select(func.count(Evento.id)).where(Evento.sessao_id == sessao_id)
        ).one()


def eventos_por_sessao(ids: list[int]) -> dict[int, list[Evento]]:
    """Eventos de varias sessoes de uma vez, agrupados por sessao_id.

    Uma consulta para a pagina inteira, em vez de uma por linha.
    """
    if not ids:
        return {}
    agrupados: dict[int, list[Evento]] = {}
    with sessao_db() as db:
        consulta = select(Evento).where(Evento.sessao_id.in_(ids)).order_by(Evento.id)
        for evento in db.exec(consulta):
            agrupados.setdefault(evento.sessao_id, []).append(evento)
    return agrupados
