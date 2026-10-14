"""
Fechamento do que ficou para tras: o recalculo dos agregados de sessao ja
gravada, pelo `executar.py --recalcular` (para as sessoes fechadas antes
desses campos existirem), e as sessoes que o servidor deixou ATIVA ao
cair no meio da gravacao (`encerrar_orfas`, ao subir). No fluxo normal
quem fecha a sessao e congela os numeros e o Gravador.
"""

from __future__ import annotations

from ..repositorios import amostras as repo_amostras
from ..repositorios import sessoes as repo_sessoes
from .gravador import MINIMO_AMOSTRAS

MENSAGEM_INTERROMPIDA = (
    "gravação interrompida: o servidor reiniciou no meio da sessão, "
    "que foi encerrada na última amostra recebida"
)


def encerrar_orfas() -> list[dict]:
    """Fecha as sessoes que o processo anterior deixou ATIVA.

    O gravador guarda a sessao em curso so na memoria: se o servidor cai
    ou reinicia no meio, a linha fica ATIVA para sempre - sem agregado,
    fora dos relatorios, aparecendo como "em andamento". Chamado ao subir,
    ANTES de o leitor ligar, quando nenhuma sessao pode estar aberta de
    verdade (o app e um processo so: dois servidores no mesmo banco
    fechariam a sessao um do outro).

    Cada uma segue a regra do encerramento normal: com menos de
    `MINIMO_AMOSTRAS`, descartada; senao encerrada com os agregados, na
    hora da ULTIMA AMOSTRA (a do reinicio diria nada sobre a gravacao) e
    com o evento de fim explicando o motivo.

    Devolve [{sessao_id, usuario_id, descartada, amostras}], para a tela
    do dono avisar que a gravacao foi interrompida.
    """
    feitas = []
    for sessao_id, usuario_id in repo_sessoes.ativas():
        agregados = repo_amostras.agregados(sessao_id)
        gravadas = agregados["total_amostras"]
        descartada = gravadas < MINIMO_AMOSTRAS
        if descartada:
            repo_sessoes.descartar(sessao_id)
        else:
            repo_sessoes.encerrar(
                sessao_id,
                agregados,
                quando=repo_amostras.ultimo_instante(sessao_id),
                mensagem=MENSAGEM_INTERROMPIDA,
            )
        feitas.append(
            {
                "sessao_id": sessao_id,
                "usuario_id": usuario_id,
                "descartada": descartada,
                "amostras": gravadas,
                "minimo": MINIMO_AMOSTRAS,
            }
        )
    return feitas


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
