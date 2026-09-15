"""
Rotas da tela de Relatorios: evolucao de um veiculo, frequencia de eventos
e comparacao entre duas sessoes. As agregacoes saem do repositorio, em SQL.
"""

from typing import Literal, Optional

from fastapi import APIRouter, HTTPException, Query

from ..repositorios import relatorios as repo_relatorios
from ..repositorios import amostras as repo_amostras
from ..repositorios import sessoes as repo_sessoes
from ..repositorios import veiculos as repo_veiculos
from ..servicos import exportador, metricas
from .esquemas import veiculo_resumido

router = APIRouter(prefix="/api/relatorios", tags=["relatorios"])

Periodo = Literal["7d", "30d", "90d", "tudo"]


@router.get("/frota")
def frota(periodo: Periodo = "tudo"):
    """Numeros do topo da tela e o ranking de eventos por veiculo."""
    return {
        "periodo": periodo,
        "resumo": repo_relatorios.resumo_da_frota(periodo),
        "por_veiculo": repo_relatorios.eventos_por_veiculo(periodo),
    }


@router.get("/evolucao")
def evolucao(veiculo_id: int, periodo: Periodo = "tudo"):
    """Serie historica de um veiculo: uma linha por sessao encerrada.

    Arquivado entra: o historico dele continua valendo, e e justamente
    num relatorio que se olha carro que saiu de circulacao.
    """
    veiculo = repo_veiculos.buscar(veiculo_id, incluir_arquivados=True)
    if veiculo is None:
        raise HTTPException(404, "veiculo nao encontrado")
    return {
        "veiculo": veiculo_resumido(veiculo),
        "periodo": periodo,
        "sessoes": repo_relatorios.evolucao(veiculo_id, periodo),
    }


@router.get("/eventos")
def eventos(veiculo_id: Optional[int] = None, periodo: Periodo = "tudo"):
    """Frequencia de evento por tipo e por dia, opcionalmente de um carro."""
    return {
        "periodo": periodo,
        "veiculo_id": veiculo_id,
        "por_tipo": repo_relatorios.eventos_por_tipo(veiculo_id, periodo),
        "por_dia": repo_relatorios.eventos_por_periodo(veiculo_id, periodo),
    }


@router.get("/comparacao")
def comparacao(a: int = Query(...), b: int = Query(...)):
    """Duas sessoes lado a lado, com metricas completas.

    Unico ponto dos relatorios que carrega amostra, e sao duas sessoes
    fixas. Exige o mesmo veiculo - comparar carros diferentes nao diz nada.
    """
    if a == b:
        raise HTTPException(400, "escolha duas sessoes diferentes")

    lados = []
    for sessao_id in (a, b):
        sessao = repo_sessoes.buscar(sessao_id)
        if sessao is None:
            raise HTTPException(404, f"sessao {sessao_id} nao encontrada")
        lados.append(sessao)

    if lados[0].veiculo_id != lados[1].veiculo_id:
        raise HTTPException(400, "as duas sessoes precisam ser do mesmo veiculo")

    veiculo = repo_veiculos.buscar(lados[0].veiculo_id, incluir_arquivados=True)

    def lado(s):
        dados = exportador.resumo(s.id)
        return {
            "sessao": s.model_dump(),
            "resumo": dados,
            "metricas": metricas.calcular(repo_amostras.listar(s.id), dados.get("duracao_s")),
        }

    dois = [lado(s) for s in lados]
    return {
        "veiculo": veiculo_resumido(veiculo),
        "sessoes": dois,
        # A diferenca ja vem calculada: a tela compara sem subtrair nada.
        "comparacao": metricas.comparar(dois[0], dois[1]),
    }
