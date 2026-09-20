"""
O canal que empurra telemetria para a interface: amostra, evento e estado
do leitor, todos repartidos pelo Hub. O cliente nao manda nada de util.

**Exige login.** A dependencia `usuario_atual` das rotas HTTP nao serve
aqui: ela levanta `HTTPException`, e o Starlette so sabe traduzir isso em
resposta HTTP - num handshake de websocket o cliente receberia um erro sem
significado, ou a conexao morreria sem codigo. Por isso o token e lido e
validado a mao, e a recusa sai como `close(1008)`, que e o codigo de
"violacao de politica" do protocolo.
"""

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from ..contexto import Contexto, obter_contexto
from ..servicos import autenticacao
from .auth import COOKIE

router = APIRouter()

# 1008 = Policy Violation, do RFC 6455. Nao ha codigo de "nao autenticado"
# no protocolo; 1008 e o que o ecossistema usa para isso.
POLITICA = 1008


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
    usuario = autenticacao.usuario_do_token(_token(ws))
    if usuario is None:
        # `accept()` antes de fechar: sem isso o navegador recebe so um
        # handshake recusado, sem codigo, e nao tem como distinguir "sem
        # login" de "servidor fora do ar".
        await ws.accept()
        await ws.close(code=POLITICA, reason="faca login para continuar")
        return

    await ws.accept()
    ctx.hub.entrar(ws, usuario.id)
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
            await ws.receive_text()   # so mantem o socket vivo
    except WebSocketDisconnect:
        pass
    finally:
        ctx.hub.sair(ws)
