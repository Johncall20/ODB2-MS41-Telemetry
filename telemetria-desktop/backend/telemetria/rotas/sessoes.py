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
from ..modelos import TipoEvento, Usuario, campos_sem_resposta
from ..repositorios import amostras as repo_amostras
from ..repositorios import limites as repo_limites
from ..repositorios import sessoes as repo_sessoes
from ..repositorios import veiculos as repo_veiculos
from ..servicos import exportador, metricas
from ..servicos.gravador import MINIMO_AMOSTRAS
from .auth import usuario_atual
from .esquemas import (
    EdicaoSessao,
    InicioSessao,
    eventos_notaveis,
    problema_nos_limites,
    veiculo_resumido,
)

router = APIRouter(tags=["sessoes"])


@router.get("/api/status")
def status(
    ctx: Contexto = Depends(obter_contexto),
    usuario: Usuario = Depends(usuario_atual),
):
    """Como esta o sistema agora: fonte, leitor, gravacao e ultima leitura.

    E o que a interface consulta ao abrir, antes de o websocket comecar a
    empurrar novidade.
    """
    gravador = ctx.gravador
    # A sessao ativa so aparece para o dono do carro: de outra conta o
    # buscar responde None, e o status fica como "nao gravando".
    sessao = (
        repo_sessoes.buscar(gravador.sessao_id, usuario.id) if gravador.sessao_id else None
    )
    return {
        "fonte": ctx.fonte,
        "nome_ble": ctx.nome_ble,
        "leitor": gravador.estado_leitor.value,
        "detalhe": gravador.detalhe_leitor,
        "gravando": sessao is not None,
        "sessao": sessao.model_dump() if sessao else None,
        # Os limites que valem NESTA gravacao, para o painel ao vivo marcar
        # a barra de giro pelo que o detector esta realmente usando, e nao
        # pelo padrao atual - que pode ter sido editado no meio da sessao.
        "limites": repo_limites.efetivos_da_sessao(sessao) if sessao else None,
        "amostras_na_sessao": gravador.total_amostras,
        "ultima": gravador.ultima,
        # A gravacao desta conta que o servidor deixou no meio ao reiniciar
        # e fechou ao subir: {sessao_id, descartada, amostras, minimo}. A
        # tela avisa ate a pessoa dizer que viu (POST /api/status/ciente).
        "interrompida": ctx.interrompida_de(usuario.id),
    }


@router.post("/api/status/ciente", status_code=204)
def ciente_da_interrupcao(
    ctx: Contexto = Depends(obter_contexto),
    usuario: Usuario = Depends(usuario_atual),
):
    """A pessoa viu o aviso da gravacao interrompida: ele nao volta."""
    ctx.ciente(usuario.id)


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
    usuario: Usuario = Depends(usuario_atual),
):
    """Lista da tela de Sessoes, ja filtrada e ordenada pelo SQL.

    Tres consultas para a pagina inteira, nenhuma sobre `amostra` - so a
    ATIVA cai no caminho lento. data_inicio/data_fim mandam no periodo.
    """
    sessoes = repo_sessoes.listar_para_tela(
        usuario.id,
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
    carros = {v.id: v for v in repo_veiculos.listar(usuario.id, incluir_arquivados=True)}
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
async def iniciar(
    entrada: InicioSessao,
    ctx: Contexto = Depends(obter_contexto),
    usuario: Usuario = Depends(usuario_atual),
):
    """Comeca a gravar para um veiculo. Uma sessao por vez.

    Os seis limites vem no corpo e vao DIRETO para o snapshot da sessao:
    sao os unicos limites que ela tera, sem edicao depois. A ordem entre
    eles e conferida antes de tudo, com 422 por campo - e nenhuma sessao
    nasce com limite invalido.
    """
    erros = problema_nos_limites(entrada.limites())
    if erros:
        primeiro = next(iter(erros.values()))
        raise HTTPException(
            422, {"erro": "validacao", "mensagem": primeiro, "campos": erros}
        )
    if ctx.gravador.sessao_id is not None:
        raise HTTPException(409, "já existe uma sessão ativa")
    veiculo = repo_veiculos.buscar(entrada.veiculo_id, usuario.id, incluir_arquivados=True)
    if veiculo is None:
        raise HTTPException(404, "veículo não encontrado")
    # Arquivado nao recebe sessao nova: senao daria para criar justamente o
    # estado que a regra de arquivamento evita - carro fora das listas com
    # gravacao em curso. Por isso ele e buscado com incluir_arquivados e
    # recusado aqui, em vez de virar um 404 enganoso.
    if veiculo.arquivado_em is not None:
        raise HTTPException(409, "este veículo está arquivado; restaure antes de gravar")
    # O adaptador BLE so le a MS41: perfil conhecido e diferente e 409.
    # Perfil nulo so avisa (no inicio-sessao), e o simulador grava tudo.
    perfil = ctx.compatibilidade(veiculo.perfil_ecu)
    if perfil and perfil["bloqueia"]:
        raise HTTPException(409, {"erro": "perfil_incompativel", "mensagem": perfil["mensagem"]})
    sessao = ctx.gravador.iniciar_sessao(
        entrada.veiculo_id,
        entrada.limites(),
        entrada.observacao,
        dono_id=usuario.id,
        km=entrada.km,
    )
    await ctx.hub.enviar(
        "sessao", {"id": sessao["id"], "status": "ATIVA"}, dono=usuario.id
    )
    return sessao


@router.patch("/api/sessoes/{sessao_id}")
def editar(sessao_id: int, entrada: EdicaoSessao, usuario: Usuario = Depends(usuario_atual)):
    """Edita as notas e o km da sessao - e so isso, a qualquer momento.

    Antes de encerrar (inclusive gravando) e depois. Campo fora desses
    dois e 422 (`extra="forbid"`). O que nao veio no corpo nao muda.

    Km numa sessao ENCERRADA e mais recente do carro passa tambem para a
    quilometragem do carro; numa ATIVA, so quando ela encerrar; numa
    antiga, nunca. `quilometragem_do_carro` devolve o valor do carro
    depois disso, para a tela atualizar sem outra consulta.
    """
    sessao = repo_sessoes.buscar(sessao_id, usuario.id)
    if sessao is None:
        raise HTTPException(404, "sessão não encontrada")
    editada = repo_sessoes.editar(sessao_id, entrada.campos())
    veiculo = repo_veiculos.buscar(editada.veiculo_id, usuario.id, incluir_arquivados=True)
    return {
        "observacao": editada.observacao,
        "km": editada.km,
        "quilometragem_do_carro": veiculo.quilometragem if veiculo else None,
    }


@router.post("/api/sessoes/encerrar")
async def encerrar(
    ctx: Contexto = Depends(obter_contexto),
    usuario: Usuario = Depends(usuario_atual),
):
    """Encerra a gravacao.

    Sessao curta demais e descartada em vez de gravada; nesse caso a
    resposta diz isso, e nao ha sessao para a tela abrir depois.
    """
    # So o dono encerra: de outra conta a sessao ativa nem e visivel, e
    # encerrar a gravacao alheia seria pior que nao ver.
    if ctx.gravador.sessao_id is not None:
        if repo_sessoes.buscar(ctx.gravador.sessao_id, usuario.id) is None:
            raise HTTPException(409, "nenhuma sessão ativa")

    resultado = await ctx.gravador.encerrar_sessao()
    if resultado is None:
        raise HTTPException(409, "nenhuma sessão ativa")
    if resultado["descartada"]:
        return {
            "descartada": True,
            "motivo": "curta demais",
            "amostras": resultado["amostras"],
            "minimo": MINIMO_AMOSTRAS,
        }
    return exportador.resumo(resultado["sessao_id"])


@router.get("/api/sessoes/{sessao_id}")
def detalhe(sessao_id: int, usuario: Usuario = Depends(usuario_atual)):
    """Tudo de uma sessao: resumo, metricas, a serie inteira e os eventos.

    E a rota mais pesada do app, e a unica que devolve amostra. E dela que
    a tela de Analise desenha os graficos.
    """
    sessao = repo_sessoes.buscar(sessao_id, usuario.id)
    if sessao is None:
        raise HTTPException(404, "sessão não encontrada")
    amostras = repo_amostras.listar(sessao_id)
    resumo = exportador.resumo(sessao_id)
    limites = repo_limites.efetivos_da_sessao(sessao)
    eventos = repo_sessoes.listar_eventos(sessao_id)
    # Valor, pico e duracao de cada evento anomalo: o evento nao os guarda,
    # e a serie que os responde ja esta carregada aqui.
    detalhes = metricas.detalhar_eventos(amostras, eventos, limites)
    return {
        "sessao": sessao.model_dump(),
        "veiculo": veiculo_resumido(
            repo_veiculos.buscar(sessao.veiculo_id, usuario.id, incluir_arquivados=True)
        ),
        # Se esta e a sessao mais recente do carro: e so nela que mudar o km
        # mexe na quilometragem do carro, e por isso so nela a tela pede a
        # confirmacao de km menor.
        "mais_recente": repo_sessoes.e_a_mais_recente(sessao_id),
        "resumo": resumo,
        # O snapshot dos limites daquela gravacao. Sessao antiga, sem
        # snapshot, vem com do_snapshot=false e o padrao atual no lugar.
        "limites": limites,
        # As metricas so saem aqui: esta e a unica rota que ja tem a serie
        # inteira carregada.
        "metricas": metricas.calcular(
            amostras, resumo.get("duracao_s"), limites
        ),
        # Cada amostra sai com o bitmask ja decodificado. Quem sabe que bit
        # e de qual campo e o backend (modelos.BITS_PARAMETROS); a tela de
        # analise so precisa saber onde a linha tem buraco.
        "amostras": [
            {**a.model_dump(), "invalidos": campos_sem_resposta(a.valid)} for a in amostras
        ],
        "eventos": [{**e.model_dump(), **detalhes.get(e.id, {})} for e in eventos],
        # Onde a leitura falhou, como trecho (inicio e fim): a Analise
        # sombreia. O fim nao esta em evento nenhum, entao sai da serie.
        "trechos": metricas.trechos_sem_leitura(amostras, sessao.iniciada_em),
    }


def _exigir_sessao(sessao_id: int, usuario_id: int) -> None:
    """404 se a sessao nao existe OU nao e desta conta.

    E esta checagem que autoriza o `repositorios/amostras.py` a trabalhar
    so por `sessao_id`, sem filtrar por dono.
    """
    if repo_sessoes.buscar(sessao_id, usuario_id) is None:
        raise HTTPException(404, "sessão não encontrada")


@router.get("/api/sessoes/{sessao_id}/csv", response_class=PlainTextResponse)
def baixar_csv(sessao_id: int, usuario: Usuario = Depends(usuario_atual)):
    """CSV da sessao, uma linha por amostra. Celula vazia = sem resposta."""
    _exigir_sessao(sessao_id, usuario.id)
    return PlainTextResponse(
        exportador.para_csv(sessao_id),
        media_type="text/csv",
        headers=exportador.cabecalhos_anexo(sessao_id, "csv"),
    )


@router.get("/api/sessoes/{sessao_id}/json", response_class=PlainTextResponse)
def baixar_json(sessao_id: int, usuario: Usuario = Depends(usuario_atual)):
    """JSON completo da sessao, para reprocessar fora do app."""
    _exigir_sessao(sessao_id, usuario.id)
    return PlainTextResponse(
        exportador.para_json(sessao_id),
        media_type="application/json",
        headers=exportador.cabecalhos_anexo(sessao_id, "json"),
    )


@router.get("/api/sessoes/{sessao_id}/pdf")
def baixar_pdf(
    sessao_id: int, secoes: str = "", usuario: Usuario = Depends(usuario_atual)
):
    """Relatorio em PDF; `secoes` separada por virgula.

    Vazio usa o padrao, sem a tabela de amostras - numa sessao longa ela
    vira dezenas de paginas.
    """
    _exigir_sessao(sessao_id, usuario.id)
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
