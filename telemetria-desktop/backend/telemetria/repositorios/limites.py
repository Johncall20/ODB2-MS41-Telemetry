"""Os limites de alerta, que sao da SESSAO.

Nao ha limite global nem limite do carro: os seis valores sao escolhidos
ao iniciar a gravacao e ficam nas colunas `limite_*` da `Sessao`. Este
modulo responde de onde partir (a ultima sessao do carro, ou os
sugeridos) e o que valeu numa sessao gravada.

So por `veiculo_id`, sem filtro de dono: quem chama ja conferiu a posse
do carro (`rotas/veiculos.py`).

Mexe aqui quem mudar como um limite chega ao detector ou as metricas.
"""

from typing import Optional

from sqlmodel import select

from ..banco import sessao_db
from ..modelos import CAMPOS_LIMITE, LIMITES_SUGERIDOS, Sessao

_COLUNAS = [getattr(Sessao, f"limite_{campo}") for campo in CAMPOS_LIMITE]


def sugeridos() -> dict:
    """O ponto de partida que a tela oferece. Copia, nao a constante."""
    return dict(LIMITES_SUGERIDOS)


def da_ultima_sessao(veiculo_id: int) -> Optional[dict]:
    """Os limites da sessao mais recente do carro com snapshot, ou None.

    "Mais recente" e por `iniciada_em`, em qualquer status e de qualquer
    idade - o que vale e ser a ultima gravacao com os seis valores. Sessao
    com snapshot nulo (gravada antes das colunas existirem) nao conta: os
    valores dela seriam os sugeridos, um palpite, e nao uma escolha.
    Sessao descartada por ser curta demais tambem nao, porque nao existe
    mais.

    Devolve os seis campos mais `sessao_id` e `iniciada_em`, para a tela
    dizer de qual gravacao eles vieram.
    """
    with sessao_db() as db:
        sessao = db.exec(
            select(Sessao)
            .where(Sessao.veiculo_id == veiculo_id, *[c.is_not(None) for c in _COLUNAS])
            .order_by(Sessao.iniciada_em.desc(), Sessao.id.desc())
        ).first()
    if sessao is None:
        return None
    return {
        **{campo: getattr(sessao, f"limite_{campo}") for campo in CAMPOS_LIMITE},
        "sessao_id": sessao.id,
        "iniciada_em": sessao.iniciada_em,
    }


def efetivos_da_sessao(sessao: Sessao) -> dict:
    """Os limites que valeram NAQUELA gravacao.

    Sessao gravada antes das colunas de snapshot existirem tem tudo nulo:
    cai nos valores SUGERIDOS, que sao um palpite e nao o que valeu na
    epoca - o valor daquele dia nunca foi guardado. `do_snapshot` diz qual
    dos dois casos e, para a tela poder avisar.
    """
    gravados = {campo: getattr(sessao, f"limite_{campo}", None) for campo in CAMPOS_LIMITE}
    if all(valor is None for valor in gravados.values()):
        return {**sugeridos(), "do_snapshot": False}
    base = sugeridos()
    return {
        **{campo: (gravados[campo] if gravados[campo] is not None else base[campo])
           for campo in CAMPOS_LIMITE},
        "do_snapshot": True,
    }


def para_snapshot(limites: dict) -> dict:
    """Os seis campos com o prefixo `limite_`, como a Sessao os guarda."""
    return {f"limite_{campo}": limites[campo] for campo in CAMPOS_LIMITE}
