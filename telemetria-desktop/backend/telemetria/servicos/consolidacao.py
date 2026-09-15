"""
Recalculo dos agregados de sessao ja gravada, pelo `executar.py
--recalcular`. Existe para as sessoes fechadas antes desses campos
existirem; no fluxo normal quem congela os numeros e o Gravador.
"""

from __future__ import annotations

from ..repositorios import amostras as repo_amostras
from ..repositorios import sessoes as repo_sessoes


def consolidar(sessao_id: int) -> dict | None:
    """Recalcula e grava os agregados de uma sessao. None se ela sumiu."""
    agregados = repo_amostras.agregados(sessao_id)
    if not repo_sessoes.gravar_agregados(sessao_id, agregados):
        return None
    return agregados


def pendentes() -> list[int]:
    """Sessoes encerradas que ainda estao sem agregado."""
    return repo_sessoes.ids_sem_agregados()


def recalcular(todas: bool = False, ao_progredir=None) -> list[tuple[int, dict]]:
    """Recalcula os agregados e devolve o que gravou, por sessao.

    `todas` refaz as encerradas; sem ele, so as que faltam.
    `ao_progredir` recebe (sessao_id, agregados) a cada linha gravada.
    """
    ids = repo_sessoes.ids_encerradas() if todas else pendentes()

    feitas: list[tuple[int, dict]] = []
    for sessao_id in ids:
        agregados = consolidar(sessao_id)
        if agregados is None:
            continue
        feitas.append((sessao_id, agregados))
        if ao_progredir is not None:
            ao_progredir(sessao_id, agregados)
    return feitas
