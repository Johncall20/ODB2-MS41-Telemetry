"""
Agregacoes que atravessam varias sessoes - o que a tela de Relatorios usa.
Mexe aqui quem precisar de um corte novo por veiculo ou por periodo.

Nenhuma consulta toca em `amostra`: pico e integridade ja estao gravados
na linha de Sessao. Sessao ATIVA fica de fora, seus numeros ainda mudam.
"""

from datetime import timedelta
from typing import Optional

from sqlalchemy import Float, case, func
from sqlmodel import select

from ..banco import sessao_db
from ..modelos import Evento, Sessao, StatusSessao, Veiculo, agora
from .sessoes import EVENTOS_DE_ROTINA, PERIODOS


def _corte(periodo: str):
    """Data inicial do periodo, ou None para "tudo"."""
    dias = PERIODOS.get(periodo)
    return agora() - timedelta(days=dias) if dias is not None else None


def _integridade():
    """Integridade a partir das colunas gravadas.

    NULL, e nao zero, sem agregado calculado: zero diria "nenhuma amostra
    completa", que e outra afirmacao.
    """
    return case(
        (
            Sessao.total_amostras > 0,
            func.cast(Sessao.amostras_completas, Float)
            * 100.0
            / func.cast(Sessao.total_amostras, Float),
        ),
        else_=None,
    )


def _duracao():
    return (
        func.julianday(Sessao.encerrada_em) - func.julianday(Sessao.iniciada_em)
    ) * 86400.0


def evolucao(veiculo_id: int, periodo: str = "tudo") -> list[dict]:
    """Uma linha por sessao encerrada do veiculo, em ordem cronologica.

    Crescente porque e serie temporal - as outras listas do app sao de
    escolha e vao da mais recente. Sessao sem agregado vem com nulo.
    """
    integridade = _integridade()
    eventos = (
        select(func.count(Evento.id))
        .where(Evento.sessao_id == Sessao.id, Evento.tipo.notin_(EVENTOS_DE_ROTINA))
        .scalar_subquery()
    )

    consulta = (
        select(
            Sessao.id,
            Sessao.iniciada_em,
            Sessao.observacao,
            _duracao().label("duracao_s"),
            Sessao.rpm_pico,
            Sessao.vss_pico,
            Sessao.ect_pico,
            Sessao.vbat_min,
            Sessao.total_amostras,
            Sessao.amostras_completas,
            integridade.label("integridade_pct"),
            eventos.label("eventos"),
        )
        .where(Sessao.veiculo_id == veiculo_id, Sessao.status == StatusSessao.ENCERRADA)
        .order_by(Sessao.iniciada_em)
    )

    corte = _corte(periodo)
    if corte is not None:
        consulta = consulta.where(Sessao.iniciada_em >= corte)

    with sessao_db() as db:
        return [
            {
                "sessao_id": linha.id,
                "iniciada_em": linha.iniciada_em,
                "observacao": linha.observacao,
                "duracao_s": round(linha.duracao_s, 1) if linha.duracao_s is not None else None,
                "rpm_pico": linha.rpm_pico,
                "vss_pico": linha.vss_pico,
                "ect_pico": linha.ect_pico,
                "vbat_min": linha.vbat_min,
                "amostras": linha.total_amostras,
                "amostras_completas": linha.amostras_completas,
                "integridade_pct": (
                    round(linha.integridade_pct, 1)
                    if linha.integridade_pct is not None
                    else None
                ),
                "eventos": linha.eventos,
            }
            for linha in db.exec(consulta).all()
        ]


def eventos_por_tipo(veiculo_id: Optional[int] = None, periodo: str = "tudo") -> list[dict]:
    """Quantos eventos de cada tipo, e em quantas sessoes distintas.

    As duas contagens dizem coisas diferentes: vinte shift lights numa
    sessao e um dia de pista; em vinte sessoes e o uso de sempre.
    """
    consulta = (
        select(
            Evento.tipo,
            func.count(Evento.id).label("total"),
            func.count(func.distinct(Evento.sessao_id)).label("sessoes"),
        )
        .join(Sessao, Sessao.id == Evento.sessao_id)
        .where(Evento.tipo.notin_(EVENTOS_DE_ROTINA))
        .group_by(Evento.tipo)
        .order_by(func.count(Evento.id).desc())
    )
    consulta = _recortar(consulta, veiculo_id, periodo)

    with sessao_db() as db:
        return [
            {"tipo": tipo.value if hasattr(tipo, "value") else tipo, "total": total, "sessoes": sessoes}
            for tipo, total, sessoes in db.exec(consulta).all()
        ]


def eventos_por_veiculo(periodo: str = "tudo") -> list[dict]:
    """Eventos por veiculo, do mais problematico ao menos.

    Arquivado entra: ele some das listas de escolha, nao do relatorio.
    """
    total = func.count(Evento.id)
    consulta = (
        select(
            Veiculo.id,
            Veiculo.placa,
            Veiculo.marca,
            Veiculo.modelo,
            Veiculo.arquivado_em,
            total.label("total"),
            func.count(func.distinct(Sessao.id)).label("sessoes"),
        )
        .join(Sessao, Sessao.veiculo_id == Veiculo.id)
        .join(Evento, Evento.sessao_id == Sessao.id)
        .where(Evento.tipo.notin_(EVENTOS_DE_ROTINA))
        .group_by(Veiculo.id)
        .order_by(total.desc())
    )
    consulta = _recortar(consulta, None, periodo)

    with sessao_db() as db:
        return [
            {
                "veiculo_id": vid,
                "placa": placa,
                "marca": marca,
                "modelo": modelo,
                "arquivado_em": arquivado,
                "total": total_,
                "sessoes": sessoes,
            }
            for vid, placa, marca, modelo, arquivado, total_, sessoes in db.exec(consulta).all()
        ]


def eventos_por_periodo(
    veiculo_id: Optional[int] = None, periodo: str = "tudo"
) -> list[dict]:
    """Eventos anomalos agrupados por dia.

    Pela data da SESSAO, nao a do evento: mantem a serie alinhada com a
    evolucao acima.
    """
    dia = func.strftime("%Y-%m-%d", Sessao.iniciada_em)
    consulta = (
        select(dia.label("dia"), func.count(Evento.id).label("total"))
        .join(Sessao, Sessao.id == Evento.sessao_id)
        .where(Evento.tipo.notin_(EVENTOS_DE_ROTINA))
        .group_by(dia)
        .order_by(dia)
    )
    consulta = _recortar(consulta, veiculo_id, periodo)

    with sessao_db() as db:
        return [{"dia": d, "total": total} for d, total in db.exec(consulta).all()]


def _recortar(consulta, veiculo_id: Optional[int], periodo: str):
    """Filtro de veiculo e de periodo, igual nas tres consultas de evento."""
    if veiculo_id is not None:
        consulta = consulta.where(Sessao.veiculo_id == veiculo_id)
    corte = _corte(periodo)
    if corte is not None:
        consulta = consulta.where(Sessao.iniciada_em >= corte)
    return consulta


def resumo_da_frota(periodo: str = "tudo") -> dict:
    """Sessoes, tempo gravado e carros que rodaram no periodo."""
    consulta = select(
        func.count(Sessao.id),
        func.count(func.distinct(Sessao.veiculo_id)),
        func.sum(_duracao()),
        func.sum(Sessao.total_amostras),
    ).where(Sessao.status == StatusSessao.ENCERRADA)

    corte = _corte(periodo)
    if corte is not None:
        consulta = consulta.where(Sessao.iniciada_em >= corte)

    with sessao_db() as db:
        sessoes, veiculos, segundos, amostras = db.exec(consulta).one()

    return {
        "sessoes": sessoes or 0,
        "veiculos": veiculos or 0,
        "tempo_total_s": round(segundos, 1) if segundos else 0.0,
        "amostras": amostras or 0,
    }
