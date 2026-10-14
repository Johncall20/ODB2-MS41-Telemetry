"""
Gravacao e leitura das amostras. Escreve em lote, para o disco nao entrar
no ciclo de leitura, e agrega em SQL, para nao trazer a serie a memoria.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import case, func
from sqlmodel import select

from ..banco import sessao_db
from ..modelos import BITS_VALID, VALID_COMPLETO, Amostra


def gravar_lote(amostras: list[Amostra]) -> None:
    """Grava o lote de uma vez.

    Escrever amostra por amostra poria o disco no caminho do ciclo de
    leitura.
    """
    if not amostras:
        return
    with sessao_db() as db:
        for a in amostras:
            db.add(a)
        db.commit()


def _quando_valido(campo: str):
    """A coluna quando o bit de `valid` daquele campo esta ligado, senao
    NULL. MAX e MIN ignoram NULL, entao isso e o que mantem o valor
    repetido pelo firmware fora do pico - a mesma regra do resumo()."""
    return case((Amostra.valid.op("&")(BITS_VALID[campo]) != 0, getattr(Amostra, campo)))


def agregados(sessao_id: int) -> dict:
    """Contagens, picos e minimo da sessao, numa consulta so.

    Sem trazer amostra para a memoria. Pico None = nenhuma leitura valida
    daquele campo; as contagens voltam 0, nunca None.
    """
    consulta = select(
        func.count(Amostra.id),
        func.count(case((Amostra.valid == VALID_COMPLETO, 1))),
        func.max(_quando_valido("rpm")),
        func.max(_quando_valido("vss")),
        func.max(_quando_valido("ect")),
        func.min(_quando_valido("vbat")),
    ).where(Amostra.sessao_id == sessao_id)

    with sessao_db() as db:
        total, completas, rpm, vss, ect, vbat = db.exec(consulta).one()

    return {
        "total_amostras": total or 0,
        "amostras_completas": completas or 0,
        "rpm_pico": rpm,
        "vss_pico": vss,
        "ect_pico": ect,
        "vbat_min": vbat,
    }


def ultimo_instante(sessao_id: int) -> Optional[datetime]:
    """A hora da ultima amostra gravada da sessao, ou None sem nenhuma.

    E onde a sessao interrompida e encerrada: a hora do reinicio do
    servidor nao diria nada sobre a gravacao.
    """
    with sessao_db() as db:
        return db.exec(
            select(func.max(Amostra.recebida_em)).where(Amostra.sessao_id == sessao_id)
        ).one()


def listar(sessao_id: int) -> list[Amostra]:
    """Serie da sessao em ordem de t_ms - o relogio do ESP32, que e o unico
    monotonico do conjunto."""
    with sessao_db() as db:
        return list(
            db.exec(select(Amostra).where(Amostra.sessao_id == sessao_id).order_by(Amostra.t_ms))
        )
