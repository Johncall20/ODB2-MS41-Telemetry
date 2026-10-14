"""
O canal que empurra telemetria para a interface: amostra, evento e estado
do leitor, todos repartidos pelo Hub. O cliente nao manda nada de util.

**Exige login.** A dependencia `usuario_atual` das rotas HTTP nao serve
aqui: ela levanta `HTTPException`, e o Starlette so sabe traduzir isso em
resposta HTTP - num handshake de websocket o cliente receberia um erro sem
significado, ou a conexao morreria sem codigo. Por isso o token e lido e
validado a mao, e a recusa sai como `close(1008)`, que e o codigo de
"violacao de politica" do protocolo.

**O token e conferido de novo enquanto o socket vive** (`_vigiar`, a cada
`INTERVALO_VIGIA_S`): sem isso, um socket aberto antes de a sessao vencer
- ou antes de um logout em outra aba - continuaria recebendo telemetria
para sempre. Venceu, fecha com o mesmo 1008, e o frontend leva ao login.
"""

import asyncio
import contextlib

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from ..contexto import Contexto, obter_contexto
from ..servicos import autenticacao
from .auth import COOKIE

router = APIRouter()

# 1008 = Policy Violation, do RFC 6455. Nao ha codigo de "nao autenticado"
# no protocolo; 1008 e o que o ecossistema usa para isso.
POLITICA = 1008

# De quanto em quanto tempo o token do socket aberto e conferido. Uma
# consulta por socket a cada meio minuto: barato, e a sessao vencida nao
# passa mais que isso recebendo dado.
INTERVALO_VIGIA_S = 30.0

MOTIVO_SEM_LOGIN = "faça login para continuar"


async def _vigiar(ws: WebSocket, token: str) -> None:
    """Fecha o socket com 1008 quando o token deixa de valer."""
    while True:
        await asyncio.sleep(INTERVALO_VIGIA_S)
        if autenticacao.usuario_do_token(token) is None:
            with contextlib.suppress(Exception):
                await ws.close(code=POLITICA, reason=MOTIVO_SEM_LOGIN)
            return


def _token(ws: WebSocket) -> str | None:
    """O token do cookie, ou do Bearer para quem conecta por script."""
    do_cookie = ws.cookies.get(COOKIE)
    if do_cookie:
        return do_cookie
    cabecalho = ws.headers.get("authorization", "")
    if cabecalho.lower().startswith("bearer "):
        return cabecalho[7:].strip()
    return None


@router.websocket("/ws")
async def websocket(ws: WebSocket, ctx: Contexto = Depends(obter_contexto)):
    """Aceita a conexao de quem esta logado e deixa o Hub empurrar por ela.

    Manda o estado do leitor logo de cara: quem acabou de abrir a tela
    precisa saber se ha carro conectado antes da primeira amostra chegar.
    """
    token = _token(ws)
    usuario = autenticacao.usuario_do_token(token)
    if usuario is None:
        # `accept()` antes de fechar: sem isso o navegador recebe so um
        # handshake recusado, sem codigo, e nao tem como distinguir "sem
        # login" de "servidor fora do ar".
        await ws.accept()
        await ws.close(code=POLITICA, reason=MOTIVO_SEM_LOGIN)
        return

    await ws.accept()
    ctx.hub.entrar(ws, usuario.id)
    vigia = asyncio.create_task(_vigiar(ws, token))
    try:
        await ws.send_json(
            {
                "tipo": "leitor",
                "dados": {
                    "estado": ctx.gravador.estado_leitor.value,
                    "detalhe": ctx.gravador.detalhe_leitor,
                },
            }
        )
        while True:
            # So mantem o socket vivo. O fechamento pela vigia chega aqui
            # como desconexao.
            mensagem = await ws.receive()
            if mensagem["type"] == "websocket.disconnect":
                break
    except (WebSocketDisconnect, RuntimeError):
        # RuntimeError: a vigia fechou o socket enquanto este receive
        # esperava - o Starlette nao deixa receber de socket fechado.
        pass
    finally:
        vigia.cancel()
        ctx.hub.sair(ws)
