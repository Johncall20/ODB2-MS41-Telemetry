"""
Rotas da tela de Relatorios: evolucao de um veiculo, frequencia de eventos
e comparacao entre duas sessoes. As agregacoes saem do repositorio, em SQL.
"""

from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from ..modelos import Usuario
from ..repositorios import relatorios as repo_relatorios
from ..repositorios import amostras as repo_amostras
from ..repositorios import limites as repo_limites
from ..repositorios import sessoes as repo_sessoes
from ..repositorios import veiculos as repo_veiculos
from ..servicos import exportador, metricas
from .auth import usuario_atual
from .esquemas import veiculo_resumido

router = APIRouter(prefix="/api/relatorios", tags=["relatorios"])

Periodo = Literal["7d", "30d", "90d", "tudo"]


@router.get("/frota")
def frota(periodo: Periodo = "tudo", usuario: Usuario = Depends(usuario_atual)):
    """Numeros do topo da tela e o ranking de eventos por veiculo.

    "Frota" e a da CONTA, nao a do sistema: as duas agregacoes filtram
    pelo dono, como todo o resto.
    """
    return {
        "periodo": periodo,
        "resumo": repo_relatorios.resumo_da_frota(usuario.id, periodo),
        "por_veiculo": repo_relatorios.eventos_por_veiculo(usuario.id, periodo),
    }


@router.get("/evolucao")
def evolucao(
    veiculo_id: int, periodo: Periodo = "tudo", usuario: Usuario = Depends(usuario_atual)
):
    """Serie historica de um veiculo: uma linha por sessao encerrada.

    Arquivado entra: o historico dele continua valendo, e e justamente
    num relatorio que se olha carro que saiu de circulacao.
    """
    veiculo = repo_veiculos.buscar(veiculo_id, usuario.id, incluir_arquivados=True)
    if veiculo is None:
        raise HTTPException(404, "veiculo nao encontrado")
    return {
        "veiculo": veiculo_resumido(veiculo),
        "periodo": periodo,
        "sessoes": repo_relatorios.evolucao(veiculo_id, usuario.id, periodo),
    }


@router.get("/eventos")
def eventos(
    veiculo_id: Optional[int] = None,
    periodo: Periodo = "tudo",
    usuario: Usuario = Depends(usuario_atual),
):
    """Frequencia de evento por tipo e por dia, opcionalmente de um carro."""
    return {
        "periodo": periodo,
        "veiculo_id": veiculo_id,
        "por_tipo": repo_relatorios.eventos_por_tipo(usuario.id, veiculo_id, periodo),
        "por_dia": repo_relatorios.eventos_por_periodo(usuario.id, veiculo_id, periodo),
    }


@router.get("/comparacao")
def comparacao(
    a: int = Query(...), b: int = Query(...), usuario: Usuario = Depends(usuario_atual)
):
    """Duas sessoes lado a lado, com metricas completas.

    Unico ponto dos relatorios que carrega amostra, e sao duas sessoes
    fixas. Exige o mesmo veiculo - comparar carros diferentes nao diz nada.
    """
    if a == b:
        raise HTTPException(400, "escolha duas sessoes diferentes")

    lados = []
    for sessao_id in (a, b):
        sessao = repo_sessoes.buscar(sessao_id, usuario.id)
        if sessao is None:
            raise HTTPException(404, f"sessao {sessao_id} nao encontrada")
        lados.append(sessao)

    if lados[0].veiculo_id != lados[1].veiculo_id:
        raise HTTPException(400, "as duas sessoes precisam ser do mesmo veiculo")

    veiculo = repo_veiculos.buscar(lados[0].veiculo_id, usuario.id, incluir_arquivados=True)

    def lado(s):
        dados = exportador.resumo(s.id)
        # Os limites de CADA sessao, nao os de agora: e o que permite ao
        # comparar() recusar a subtracao quando os dois lados foram
        # medidos contra limiares diferentes.
        limites = repo_limites.efetivos_da_sessao(s)
        return {
            "sessao": s.model_dump(),
            "resumo": dados,
            "limites": limites,
            "metricas": metricas.calcular(
                repo_amostras.listar(s.id), dados.get("duracao_s"), limites
            ),
        }

    dois = [lado(s) for s in lados]
    return {
        "veiculo": veiculo_resumido(veiculo),
        "sessoes": dois,
        # A diferenca ja vem calculada: a tela compara sem subtrair nada.
        "comparacao": metricas.comparar(dois[0], dois[1]),
    }
