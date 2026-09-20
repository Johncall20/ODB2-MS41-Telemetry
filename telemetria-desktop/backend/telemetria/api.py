"""
Monta o app e o poe no ar: middleware, ciclo de vida, routers, dist do
React e o main() da linha de comando. Sem regra de negocio nem consulta.
"""

from __future__ import annotations

import argparse
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as ErroHTTP

from .contexto import Contexto
from .rotas import auth as rotas_auth
from .rotas import clientes as rotas_clientes
from .rotas import limites as rotas_limites
from .rotas import relatorios as rotas_relatorios
from .rotas import sessoes as rotas_sessoes
from .rotas import veiculos as rotas_veiculos
from .rotas import websocket as rotas_websocket
from .servicos import consolidacao


def _avisar_pendentes() -> None:
    """Avisa no terminal se ha sessao sem agregado calculado.

    Ela mostra numero certo na tela mas some dos filtros por pico e
    integridade, e a tela nao tem como explicar isso.
    """
    faltando = consolidacao.pendentes()
    if faltando:
        print(
            f"[banco] {len(faltando)} sessao(oes) sem pico e integridade gravados: "
            f"elas ficam de fora dos filtros por esses campos. "
            f"Rode: python executar.py --recalcular"
        )


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    """Liga o leitor ao subir; desliga tudo ao descer.

    **Nao mexe no esquema.** Quem cria e altera tabela e o Alembic, e
    `alembic upgrade head` e **passo manual**, rodado antes de subir o app.
    Nao ha entrypoint que o faca por voce. App que altera esquema no boot
    esconde a migration que falhou e deixa dois caminhos de evolucao do
    banco; por isso o boot aqui nao tenta consertar nada - se o esquema
    estiver atrasado, as rotas falham e o erro aponta para a migration que
    falta.

    O que vem depois do `yield` roda no encerramento, e e o que garante
    que o buffer do gravador chegue ao disco antes de o processo morrer.
    """
    _avisar_pendentes()
    await app.state.contexto.iniciar()
    yield
    await app.state.contexto.parar()


app = FastAPI(title="Telemetria DS2/MS41", lifespan=ciclo_de_vida)

# O contexto nasce pronto com o padrao do ambiente; a linha de comando so
# o reconfigura depois.
app.state.contexto = Contexto()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    # allow_credentials para o cookie de sessao atravessar quando o Vite
    # roda sem proxy. Com credenciais, o CORS proibe `allow_origins=["*"]`
    # - e ainda bem: origem curinga com cookie seria qualquer site do mundo
    # falando pela conta de quem esta logado.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Auth fica FORA da protecao, senao ninguem conseguiria entrar.
app.include_router(rotas_auth.router)

# Todo o resto do /api exige login. A dependencia entra no router inteiro,
# e nao rota a rota: assim rota nova nasce protegida por omissao, e deixar
# uma aberta passa a ser um ato explicito em vez de um esquecimento.
PROTEGIDO = [Depends(rotas_auth.usuario_atual)]
app.include_router(rotas_sessoes.router, dependencies=PROTEGIDO)
app.include_router(rotas_veiculos.router, dependencies=PROTEGIDO)
app.include_router(rotas_clientes.router, dependencies=PROTEGIDO)
app.include_router(rotas_limites.router, dependencies=PROTEGIDO)
app.include_router(rotas_relatorios.router, dependencies=PROTEGIDO)

# O /ws fica de fora: a dependencia levanta HTTPException, que num
# handshake de websocket viraria erro sem significado para o cliente.
# Autenticar o socket e trabalho proprio, e esta fora desta fase.
app.include_router(rotas_websocket.router)


class ArquivosUI(StaticFiles):
    """Serve os arquivos da interface.

    Caminho que nao e arquivo cai no index.html, senao recarregar /sessoes
    daria 404. Erro em /api continua 404, para nao virar HTML.
    """

    async def get_response(self, path: str, scope):
        try:
            return await super().get_response(path, scope)
        except ErroHTTP as erro:
            if erro.status_code != 404 or path.startswith(("api", "ws")):
                raise
            return await super().get_response("index.html", scope)


# A interface e servida pela propria API, entao o app roda em uma URL so.
DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if DIST.is_dir():
    app.mount("/", ArquivosUI(directory=DIST, html=True), name="ui")


def main() -> None:
    """Le a linha de comando e sobe o servidor, ou so recalcula e sai."""
    import uvicorn

    p = argparse.ArgumentParser(description="Backend da telemetria DS2/MS41")
    p.add_argument("--sim", action="store_true", help="usa a fonte simulada em vez do BLE")
    p.add_argument(
        "--nome", default=app.state.contexto.nome_ble, help="nome anunciado pelo ESP32"
    )
    p.add_argument("--porta", type=int, default=8000)
    p.add_argument(
        "--host",
        default="127.0.0.1",
        help=(
            "endereco de escuta. O padrao so aceita conexao da propria maquina, "
            "que e como o app roda em desenvolvimento; hospedar pede 0.0.0.0"
        ),
    )
    p.add_argument(
        "--recalcular",
        nargs="?",
        const="pendentes",
        choices=["pendentes", "tudo"],
        help=(
            "recalcula pico, minimo e contagens das sessoes ja gravadas e sai. "
            "Sem argumento, so as que ainda nao tem; 'tudo' refaz todas as encerradas"
        ),
    )
    args = p.parse_args()

    if args.recalcular:
        _recalcular(args.recalcular == "tudo")
        return

    app.state.contexto.configurar(usar_simulador=args.sim, nome_ble=args.nome)

    uvicorn.run(app, host=args.host, port=args.porta, log_level="info")


def _recalcular(todas: bool) -> None:
    """Roda o recalculo sem subir o servidor.

    Nao abre o leitor nem o websocket de proposito: e uma tarefa de banco,
    e o app no ar nao precisa estar no caminho dela.
    """

    def imprimir(sessao_id: int, dados: dict) -> None:
        print(
            f"  sessao {sessao_id}: {dados['total_amostras']} amostras, "
            f"{dados['amostras_completas']} completas, "
            f"rpm_pico={dados['rpm_pico']}"
        )

    alvo = "todas as sessoes encerradas" if todas else "as sessoes sem agregado"
    print(f"[recalcular] {alvo}")
    feitas = consolidacao.recalcular(todas=todas, ao_progredir=imprimir)
    print(f"[recalcular] {len(feitas)} sessao(oes) atualizada(s)")


if __name__ == "__main__":
    main()
