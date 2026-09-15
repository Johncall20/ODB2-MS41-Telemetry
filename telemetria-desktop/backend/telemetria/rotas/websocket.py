"""
O canal que empurra telemetria para a interface: amostra, evento e estado
do leitor, todos repartidos pelo Hub. O cliente nao manda nada de util.
"""

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from ..contexto import Contexto, obter_contexto

router = APIRouter()


@router.websocket("/ws")
async def websocket(ws: WebSocket, ctx: Contexto = Depends(obter_contexto)):
    """Aceita a conexao e deixa o Hub empurrar telemetria por ela.

    Manda o estado do leitor logo de cara: quem acabou de abrir a tela
    precisa saber se ha carro conectado antes da primeira amostra chegar.
    """
    await ws.accept()
    ctx.hub.entrar(ws)
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
