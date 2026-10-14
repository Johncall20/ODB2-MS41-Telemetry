"""
Monta o app e o poe no ar: middleware, ciclo de vida, routers, dist do
React e o main() da linha de comando. Sem regra de negocio nem consulta.
"""

from __future__ import annotations

import argparse
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as ErroHTTP

from .contexto import Contexto
from .rotas import auth as rotas_auth
from .rotas import catalogo as rotas_catalogo
from .rotas import clientes as rotas_clientes
from .rotas import limites as rotas_limites
from .rotas import relatorios as rotas_relatorios
from .rotas import sessoes as rotas_sessoes
from .rotas import veiculos as rotas_veiculos
from .rotas import websocket as rotas_websocket
from .servicos import catalogo as servico_catalogo
from .servicos import consolidacao

log = logging.getLogger("telemetria.api")

# A mesma frase que o api.js mostra para 500: o usuario le uma so.
FRASE_ERRO_INTERNO = "Ocorreu um erro inesperado. Tente de novo em instantes."


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
    # Antes de o leitor ligar: nenhuma sessao pode estar aberta de verdade
    # agora, entao a ATIVA no banco e de uma gravacao que caiu no meio.
    interrompidas = consolidacao.encerrar_orfas()
    for i in interrompidas:
        print(
            f"[gravacao] sessao {i['sessao_id']} estava ATIVA de antes do reinicio: "
            + ("descartada, curta demais" if i["descartada"] else f"encerrada com {i['amostras']} amostras")
        )
    app.state.contexto.interrompidas = interrompidas
    await app.state.contexto.iniciar()
    yield
    await app.state.contexto.parar()


app = FastAPI(title="Telemetria DS2/MS41", lifespan=ciclo_de_vida)

# Frases para os erros de tipo do Pydantic, que chegam em ingles. Os
# erros escritos por nos (ValueError dos validators) ja vem em portugues e
# passam direto.
_FRASES_VALIDACAO = {
    "missing": "preencha este campo",
    "int_parsing": "informe um número inteiro",
    "int_type": "informe um número inteiro",
    "int_from_float": "informe um número inteiro",
    "float_parsing": "informe um número",
    "float_type": "informe um número",
    "string_type": "informe um texto",
    "enum": "escolha uma das opções",
    "literal_error": "escolha uma das opções",
    "bool_parsing": "informe sim ou não",
    "bool_type": "informe sim ou não",
    "datetime_parsing": "informe uma data válida",
    "datetime_from_date_parsing": "informe uma data válida",
    "string_too_short": "preencha este campo",
    "json_invalid": "o corpo da requisição não é um JSON válido",
    "model_attributes_type": "dados inválidos",
    "dict_type": "dados inválidos",
    "extra_forbidden": "este campo não pode ser alterado aqui",
}


# Como o campo aparece na `mensagem` geral, que a tela mostra quando nao
# tem onde escrever o erro do campo. O que nao esta aqui sai com o nome da
# chave sem sublinhado.
_ROTULOS = {
    "ano_modelo": "ano do modelo",
    "ano_fabricacao": "ano de fabricação",
    "email": "e-mail",
    "senha_atual": "senha atual",
    "senha_nova": "senha nova",
    "veiculo_id": "veículo",
    "cliente_id": "cliente",
    "modelo_id": "modelo",
    "perfil_ecu": "ECU",
    "cambio": "câmbio",
}


def _frase(erro: dict) -> str:
    """A frase de um erro do Pydantic, em portugues."""
    frase = _FRASES_VALIDACAO.get(erro.get("type"))
    if frase:
        return frase
    if erro.get("type") == "greater_than_equal":
        return f"o valor tem de ser no mínimo {erro.get('ctx', {}).get('ge')}"
    if erro.get("type") == "greater_than":
        return f"o valor tem de ser maior que {erro.get('ctx', {}).get('gt')}"
    if erro.get("type") == "less_than_equal":
        return f"o valor tem de ser no máximo {erro.get('ctx', {}).get('le')}"
    if erro.get("type") == "less_than":
        return f"o valor tem de ser menor que {erro.get('ctx', {}).get('lt')}"
    if erro.get("type") == "string_too_long":
        return f"use no máximo {erro.get('ctx', {}).get('max_length')} caracteres"
    msg = str(erro.get("msg", ""))
    # O EmailStr explica em ingles o que esta errado; aqui vira uma frase so.
    if msg.startswith("value is not a valid email address"):
        return "formato inválido; use algo como nome@provedor.com"
    # O Pydantic prefixa o ValueError dos validators com "Value error, " - e
    # essa frase e nossa, em portugues. Qualquer outra e do Pydantic, em
    # ingles, e nao chega a tela.
    if msg.startswith("Value error, "):
        return msg.removeprefix("Value error, ")
    return "valor inválido"


@app.exception_handler(RequestValidationError)
async def _validacao_por_campo(request: Request, erro: RequestValidationError):
    """O 422 da entrada no mesmo formato de todos os erros com corpo.

    Sem isto o FastAPI devolve uma LISTA em `detail`, e a tela mostraria
    "HTTP 422" no lugar da frase. Aqui sai `{"erro", "mensagem", "campos"}`:
    `campos` leva um erro por campo, para o formulario escrever embaixo de
    cada um, e `mensagem` e o primeiro deles, para quem so mostra uma
    frase. Erro que nao e de campo (corpo inteiro invalido) entra so na
    mensagem.
    """
    campos: dict[str, str] = {}
    primeira = None
    for item in erro.errors():
        local = [str(p) for p in item.get("loc", ()) if p not in ("body", "query", "path")]
        frase = _frase(item)
        if local:
            campos.setdefault(local[0], frase)
            rotulo = _ROTULOS.get(local[0], local[0].replace("_", " "))
            primeira = primeira or f"{rotulo}: {frase}"
        else:
            primeira = primeira or frase
    return JSONResponse(
        status_code=422,
        content={
            "detail": {
                "erro": "validacao",
                "mensagem": primeira or "dados inválidos",
                "campos": campos,
            }
        },
    )


class CapturaErroInterno:
    """Excecao nao tratada vira 500 em JSON, com o traceback no log.

    E middleware ASGI, e nao `exception_handler(Exception)`, por causa do
    CORS: o Starlette roda o handler de Exception generica no middleware de
    erro MAIS EXTERNO, fora do CORSMiddleware, e o 500 saia sem
    `Access-Control-Allow-Origin` - o Vite em outra origem nao conseguia ler
    a resposta, e a tela dizia "sem conexao" em vez de "erro inesperado".
    Registrado ANTES do CORS (o ultimo `add_middleware` e o mais externo),
    este fica por dentro dele, e a resposta passa pelo CORS na volta.

    O corpo e o formato que o `api.js` le (`detail.mensagem`), com a mesma
    frase que ele usa para 500. Nada do erro vai na resposta: o detalhe e
    so do log. Se a resposta ja tinha comecado a sair, nao ha o que trocar:
    a excecao segue para o servidor.
    """

    def __init__(self, app_asgi) -> None:
        self.app = app_asgi

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        comecou = False

        async def enviar(mensagem) -> None:
            nonlocal comecou
            if mensagem["type"] == "http.response.start":
                comecou = True
            await send(mensagem)

        try:
            await self.app(scope, receive, enviar)
        except Exception:
            log.exception("erro nao tratado em %s %s", scope.get("method"), scope.get("path"))
            if comecou:
                raise
            resposta = JSONResponse(
                status_code=500,
                content={"detail": {"erro": "interno", "mensagem": FRASE_ERRO_INTERNO}},
            )
            await resposta(scope, receive, send)


# O contexto nasce pronto com o padrao do ambiente; a linha de comando so
# o reconfigura depois.
app.state.contexto = Contexto()
# Antes do CORS, para ficar POR DENTRO dele - ver CapturaErroInterno.
app.add_middleware(CapturaErroInterno)
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
    # O download e por fetch, e o nome do arquivo vem neste cabecalho: sem
    # expo-lo, o Vite sem proxy (outra origem) nao o le.
    expose_headers=["Content-Disposition"],
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
app.include_router(rotas_catalogo.router, dependencies=PROTEGIDO)

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
    p.add_argument(
        "--carregar-catalogo",
        nargs="?",
        const=str(servico_catalogo.ARQUIVO_PADRAO),
        metavar="ARQUIVO",
        help=(
            "recarrega marcas e modelos do catalogo_veiculos.json (ou do arquivo dado) "
            "e sai. Idempotente: so insere o que falta, nunca apaga"
        ),
    )
    args = p.parse_args()

    if args.recalcular:
        _recalcular(args.recalcular == "tudo")
        return
    if args.carregar_catalogo:
        _carregar_catalogo(args.carregar_catalogo)
        return

    app.state.contexto.configurar(usar_simulador=args.sim, nome_ble=args.nome)

    # O log do app (o traceback do erro interno, entre outros) no terminal,
    # com hora e origem, ao lado do log do uvicorn.
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
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


def _carregar_catalogo(caminho: str) -> None:
    """Recarrega o catalogo do JSON, sem subir o servidor. Le so do
    arquivo: quem fala com a FIPE e o `gerar_catalogo.py`."""
    print(f"[catalogo] lendo {caminho}")
    feito = servico_catalogo.carregar(Path(caminho))
    print(
        f"[catalogo] {feito['marcas_novas']} marca(s) e "
        f"{feito['modelos_novos']} modelo(s) novos; {feito['com_faixa']} com faixa de "
        "anos no arquivo"
    )


if __name__ == "__main__":
    main()
