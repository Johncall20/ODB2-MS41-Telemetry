"""
Rotas da gravacao: estado, ciclo da sessao, detalhe e exportacoes.
Mexe aqui quem mudar o que a tela recebe sobre uma sessao.

/api/status entra aqui porque o que ele reporta e o estado do gravador.
"""

from datetime import datetime
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse, Response

from ..contexto import Contexto, obter_contexto
from ..modelos import TipoEvento, campos_invalidos
from ..repositorios import amostras as repo_amostras
from ..repositorios import limites as repo_limites
from ..repositorios import sessoes as repo_sessoes
from ..repositorios import veiculos as repo_veiculos
from ..servicos import exportador, metricas
from ..servicos.gravador import MINIMO_AMOSTRAS
from .esquemas import InicioSessao, eventos_notaveis, veiculo_resumido

router = APIRouter(tags=["sessoes"])


@router.get("/api/status")
def status(ctx: Contexto = Depends(obter_contexto)):
    """Como esta o sistema agora: fonte, leitor, gravacao e ultima leitura.

    E o que a interface consulta ao abrir, antes de o websocket comecar a
    empurrar novidade.
    """
    gravador = ctx.gravador
    sessao = repo_sessoes.buscar(gravador.sessao_id) if gravador.sessao_id else None
    return {
        "fonte": ctx.fonte,
        "nome_ble": ctx.nome_ble,
        "leitor": gravador.estado_leitor.value,
        "detalhe": gravador.detalhe_leitor,
        "gravando": gravador.sessao_id is not None,
        "sessao": sessao.model_dump() if sessao else None,
        # Os limites que valem NESTA gravacao, para o painel ao vivo marcar
        # a barra de giro pelo que o detector esta realmente usando, e nao
        # pelo padrao atual - que pode ter sido editado no meio da sessao.
        "limites": repo_limites.efetivos_da_sessao(sessao) if sessao else None,
        "amostras_na_sessao": gravador.total_amostras,
        "ultima": gravador.ultima,
    }


@router.get("/api/sessoes")
def listar(
    veiculo_id: Optional[int] = None,
    periodo: Literal["7d", "30d", "90d", "tudo"] = "tudo",
    data_inicio: Optional[datetime] = None,
    data_fim: Optional[datetime] = None,
    tipo_evento: list[TipoEvento] = Query([]),
    sem_eventos: bool = False,
    duracao_minima_s: Optional[float] = Query(None, ge=0),
    integridade_minima: Optional[float] = Query(None, ge=0, le=100),
    ordenar_por: Literal["data", "duracao", "rpm_maximo", "eventos"] = "data",
    direcao: Literal["asc", "desc"] = "desc",
):
    """Lista da tela de Sessoes, ja filtrada e ordenada pelo SQL.

    Tres consultas para a pagina inteira, nenhuma sobre `amostra` - so a
    ATIVA cai no caminho lento. data_inicio/data_fim mandam no periodo.
    """
    sessoes = repo_sessoes.listar_para_tela(
        veiculo_id=veiculo_id,
        periodo=periodo,
        data_inicio=data_inicio,
        data_fim=data_fim,
        tipos_evento=[t.value for t in tipo_evento],
        sem_eventos=sem_eventos,
        duracao_minima_s=duracao_minima_s,
        integridade_minima=integridade_minima,
        ordenar_por=ordenar_por,
        direcao=direcao,
    )
    # Arquivado entra: a sessao de um carro arquivado continua listada, e a
    # tela precisa do carro para marcar a placa.
    carros = {v.id: v for v in repo_veiculos.listar(incluir_arquivados=True)}
    eventos = repo_sessoes.eventos_por_sessao([s.id for s in sessoes])
    return [
        {
            **s.model_dump(),
            "veiculo": veiculo_resumido(carros.get(s.veiculo_id)),
            "resumo": exportador.resumo_de(s, eventos.get(s.id, [])),
            "eventos_notaveis": eventos_notaveis(eventos.get(s.id, [])),
        }
        for s in sessoes
    ]


@router.post("/api/sessoes")
async def iniciar(entrada: InicioSessao, ctx: Contexto = Depends(obter_contexto)):
    """Comeca a gravar para um veiculo. Uma sessao por vez."""
    if ctx.gravador.sessao_id is not None:
        raise HTTPException(409, "ja existe uma sessao ativa")
    veiculo = repo_veiculos.buscar(entrada.veiculo_id, incluir_arquivados=True)
    if veiculo is None:
        raise HTTPException(404, "veiculo nao encontrado")
    # Arquivado nao recebe sessao nova: senao daria para criar justamente o
    # estado que a regra de arquivamento evita - carro fora das listas com
    # gravacao em curso. Por isso ele e buscado com incluir_arquivados e
    # recusado aqui, em vez de virar um 404 enganoso.
    if veiculo.arquivado_em is not None:
        raise HTTPException(409, "este veiculo esta arquivado; restaure antes de gravar")
    sessao = ctx.gravador.iniciar_sessao(entrada.veiculo_id, entrada.observacao)
    await ctx.hub.enviar("sessao", {"id": sessao["id"], "status": "ATIVA"})
    return sessao


@router.post("/api/sessoes/encerrar")
async def encerrar(ctx: Contexto = Depends(obter_contexto)):
    """Encerra a gravacao.

    Sessao curta demais e descartada em vez de gravada; nesse caso a
    resposta diz isso, e nao ha sessao para a tela abrir depois.
    """
    resultado = await ctx.gravador.encerrar_sessao()
    if resultado is None:
        raise HTTPException(409, "nenhuma sessao ativa")
    if resultado["descartada"]:
        return {
            "descartada": True,
            "motivo": "curta demais",
            "amostras": resultado["amostras"],
            "minimo": MINIMO_AMOSTRAS,
        }
    return exportador.resumo(resultado["sessao_id"])


@router.get("/api/sessoes/{sessao_id}")
def detalhe(sessao_id: int):
    """Tudo de uma sessao: resumo, metricas, a serie inteira e os eventos.

    E a rota mais pesada do app, e a unica que devolve amostra. E dela que
    a tela de Analise desenha os graficos.
    """
    sessao = repo_sessoes.buscar(sessao_id)
    if sessao is None:
        raise HTTPException(404, "sessao nao encontrada")
    amostras = repo_amostras.listar(sessao_id)
    resumo = exportador.resumo(sessao_id)
    return {
        "sessao": sessao.model_dump(),
        "veiculo": veiculo_resumido(
            repo_veiculos.buscar(sessao.veiculo_id, incluir_arquivados=True)
        ),
        "resumo": resumo,
        # O snapshot dos limites daquela gravacao. Sessao antiga, sem
        # snapshot, vem com do_snapshot=false e o padrao atual no lugar.
        "limites": repo_limites.efetivos_da_sessao(sessao),
        # As metricas so saem aqui: esta e a unica rota que ja tem a serie
        # inteira carregada.
        "metricas": metricas.calcular(
            amostras, resumo.get("duracao_s"), repo_limites.efetivos_da_sessao(sessao)
        ),
        # Cada amostra sai com o bitmask ja decodificado. Quem sabe que bit
        # e de qual campo e o backend (modelos.BITS_VALID); a tela de
        # analise so precisa saber onde a linha tem buraco.
        "amostras": [
            {**a.model_dump(), "invalidos": campos_invalidos(a.valid)} for a in amostras
        ],
        "eventos": [e.model_dump() for e in repo_sessoes.listar_eventos(sessao_id)],
    }


@router.get("/api/sessoes/{sessao_id}/csv", response_class=PlainTextResponse)
def baixar_csv(sessao_id: int):
    """CSV da sessao, uma linha por amostra. Celula vazia = sem resposta."""
    return PlainTextResponse(
        exportador.para_csv(sessao_id),
        media_type="text/csv",
        headers=exportador.cabecalhos_anexo(sessao_id, "csv"),
    )


@router.get("/api/sessoes/{sessao_id}/json", response_class=PlainTextResponse)
def baixar_json(sessao_id: int):
    """JSON completo da sessao, para reprocessar fora do app."""
    return PlainTextResponse(
        exportador.para_json(sessao_id),
        media_type="application/json",
        headers=exportador.cabecalhos_anexo(sessao_id, "json"),
    )


@router.get("/api/sessoes/{sessao_id}/pdf")
def baixar_pdf(sessao_id: int, secoes: str = ""):
    """Relatorio em PDF; `secoes` separada por virgula.

    Vazio usa o padrao, sem a tabela de amostras - numa sessao longa ela
    vira dezenas de paginas.
    """
    pedidas = [s.strip() for s in secoes.split(",") if s.strip()]
    try:
        conteudo = exportador.para_pdf(sessao_id, pedidas or exportador.SECOES_PADRAO)
    except ValueError as erro:
        raise HTTPException(404, str(erro))
    return Response(
        conteudo,
        media_type="application/pdf",
        headers=exportador.cabecalhos_anexo(sessao_id, "pdf"),
    )
