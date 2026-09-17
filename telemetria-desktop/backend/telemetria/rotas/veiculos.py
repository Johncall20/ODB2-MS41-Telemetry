"""
Rotas de veiculo: cadastro, edicao, arquivamento e a lista da tela.
DELETE aqui ARQUIVA, nao apaga - as sessoes gravadas ficam.
"""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError

from ..contexto import Contexto, obter_contexto
from ..modelos import Veiculo
from ..repositorios import limites as repo_limites
from ..repositorios import sessoes as repo_sessoes
from ..repositorios import veiculos as repo_veiculos
from ..servicos import exportador
from .esquemas import (
    LimitesEntrada,
    VeiculoEntrada,
    eventos_notaveis,
    problema_nos_limites,
)

router = APIRouter(prefix="/api/veiculos", tags=["veiculos"])


@router.get("")
def listar(
    busca: str = Query("", description="casa com placa, modelo ou cliente"),
    ordenar_por: Literal[
        "placa", "modelo", "cliente", "ultima_sessao", "criado_em", "total_sessoes"
    ] = "ultima_sessao",
    direcao: Literal["asc", "desc"] = "desc",
    situacao: list[Literal["recentes", "nunca", "arquivados"]] = Query([]),
    incluir_arquivados: bool = False,
):
    """Lista da tela de Veiculos, ja filtrada e ordenada.

    `situacao` repete na query string e as marcadas se SOMAM.
    """
    return [
        {
            **linha["veiculo"].model_dump(),
            "total_sessoes": linha["total_sessoes"],
            "ultima_sessao": linha["ultima_sessao"],
        }
        for linha in repo_veiculos.listar_para_tela(
            busca=busca,
            ordenar_por=ordenar_por,
            direcao=direcao,
            situacoes=list(situacao),
            incluir_arquivados=incluir_arquivados,
        )
    ]


@router.get("/{veiculo_id}")
def detalhe(veiculo_id: int):
    """O veiculo e todas as sessoes dele, com resumo por linha."""
    # Arquivado entra: e por esta tela que se restaura o veiculo, e as
    # sessoes dele continuam sendo consultadas por aqui.
    veiculo = repo_veiculos.buscar(veiculo_id, incluir_arquivados=True)
    if veiculo is None:
        raise HTTPException(404, "veiculo nao encontrado")
    sessoes = repo_sessoes.listar(veiculo_id=veiculo_id)
    # Mesma montagem da tela de Sessoes: os eventos de todas as sessoes do
    # carro vem numa consulta so, e o resumo sai dos agregados gravados na
    # linha, sem abrir a tabela de amostras.
    eventos = repo_sessoes.eventos_por_sessao([s.id for s in sessoes])
    return {
        "veiculo": veiculo.model_dump(),
        "total_sessoes": len(sessoes),
        "sessoes": [
            {
                **s.model_dump(),
                "resumo": exportador.resumo_de(s, eventos.get(s.id, [])),
                "eventos_notaveis": eventos_notaveis(eventos.get(s.id, [])),
            }
            for s in sessoes
        ],
    }


def _conflito_de_placa(placa: str, ignorando: int | None = None) -> None:
    """Levanta 409 se a placa ja e de outro veiculo.

    Ativo e arquivado dao corpos diferentes: com o arquivado a tela
    oferece restaurar, e para isso precisa do id e da data.
    """
    existente = repo_veiculos.buscar_por_placa(placa)
    if existente is None or existente.id == ignorando:
        return
    if existente.arquivado_em is None:
        raise HTTPException(
            409,
            {
                "erro": "placa_em_uso",
                "mensagem": f"ja existe um veiculo ativo com a placa {placa}",
                "veiculo_id": existente.id,
            },
        )
    raise HTTPException(
        409,
        {
            "erro": "placa_arquivada",
            "mensagem": f"o veiculo de placa {placa} foi arquivado",
            "veiculo_id": existente.id,
            "arquivado_em": existente.arquivado_em.isoformat(),
        },
    )


@router.post("")
def criar(entrada: VeiculoEntrada):
    """Cadastra um veiculo. Placa repetida devolve 409, nao 500."""
    _conflito_de_placa(entrada.placa)
    try:
        return repo_veiculos.criar(Veiculo(**entrada.model_dump()))
    except IntegrityError:
        # Rede de seguranca do indice unico parcial: pega a corrida entre a
        # checagem e o insert, e o caso da placa vazia, que a checagem acima
        # deixa passar porque nao ha o que comparar.
        raise HTTPException(409, {"erro": "placa_em_uso", "mensagem": "placa ja cadastrada"})


@router.put("/{veiculo_id}")
def editar(veiculo_id: int, entrada: VeiculoEntrada):
    """Grava o formulario de edicao. Nao desarquiva o veiculo."""
    _conflito_de_placa(entrada.placa, ignorando=veiculo_id)
    try:
        veiculo = repo_veiculos.editar(veiculo_id, entrada.model_dump())
    except IntegrityError:
        raise HTTPException(409, {"erro": "placa_em_uso", "mensagem": "placa ja cadastrada"})
    if veiculo is None:
        raise HTTPException(404, "veiculo nao encontrado")
    return veiculo


@router.delete("/{veiculo_id}")
def arquivar(veiculo_id: int, ctx: Contexto = Depends(obter_contexto)):
    """Arquiva o veiculo. Nao apaga nada - o historico fica inteiro.

    So nao se arquiva o carro que esta gravando agora: deixaria a sessao
    presa a um veiculo fora das listas.
    """
    if repo_veiculos.buscar(veiculo_id, incluir_arquivados=True) is None:
        raise HTTPException(404, "veiculo nao encontrado")

    if ctx.gravador.sessao_id is not None:
        ativa = repo_sessoes.buscar(ctx.gravador.sessao_id)
        if ativa is not None and ativa.veiculo_id == veiculo_id:
            raise HTTPException(409, "este veiculo esta gravando uma sessao agora")

    quando = repo_veiculos.arquivar(veiculo_id)
    return {
        "arquivado": veiculo_id,
        "arquivado_em": quando,
        "sessoes_preservadas": len(repo_sessoes.listar(veiculo_id=veiculo_id)),
    }


@router.post("/{veiculo_id}/restaurar")
def restaurar(veiculo_id: int):
    """Traz o veiculo de volta as listas, com o historico intacto."""
    if not repo_veiculos.restaurar(veiculo_id):
        raise HTTPException(404, "veiculo nao encontrado")
    return repo_veiculos.buscar(veiculo_id)


def _exigir_veiculo(veiculo_id: int) -> None:
    """404 se o carro nao existe. Arquivado passa: e por esta tela que se
    restaura o veiculo, e os limites dele continuam sendo mostrados."""
    if repo_veiculos.buscar(veiculo_id, incluir_arquivados=True) is None:
        raise HTTPException(404, "veiculo nao encontrado")


@router.get("/{veiculo_id}/limites")
def ler_limites(veiculo_id: int):
    """Os seis limites de alerta do carro. Sao os unicos que existem."""
    _exigir_veiculo(veiculo_id)
    return repo_limites.do_veiculo(veiculo_id)


@router.put("/{veiculo_id}/limites")
def gravar_limites(veiculo_id: int, novos: LimitesEntrada):
    """Grava os seis limites do carro.

    Nao afeta a gravacao em curso: a sessao levou o snapshot dos limites
    no inicio, de proposito.
    """
    _exigir_veiculo(veiculo_id)
    valores = novos.model_dump()

    problema = problema_nos_limites(valores)
    if problema is not None:
        raise HTTPException(422, {"erro": "limites_invalidos", "mensagem": problema})

    return repo_limites.gravar_do_veiculo(veiculo_id, valores)
