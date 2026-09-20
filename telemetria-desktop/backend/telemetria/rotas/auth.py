"""
Cadastro, login, logout e "quem sou eu" - e a dependencia que protege o
resto do `/api`.

O token viaja num cookie httpOnly. O `Authorization: Bearer` tambem e
aceito, para curl e script: o navegador nunca o usa (nao consegue ler o
cookie httpOnly), mas sem ele a API so seria utilizavel de dentro do
navegador.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.exc import IntegrityError

from ..modelos import PapelUsuario, Usuario
from ..repositorios import clientes as repo_clientes
from ..repositorios import usuarios as repo_usuarios
from ..servicos import autenticacao
from .esquemas import CadastroEntrada, LoginEntrada, PapelEntrada, usuario_publico

router = APIRouter(prefix="/api/auth", tags=["auth"])

COOKIE = "telemetria_sessao"

# Resposta unica para e-mail inexistente e senha errada. Dizer qual dos
# dois falhou entrega uma lista de e-mails cadastrados a quem quiser
# tentar.
CREDENCIAL_INVALIDA = "e-mail ou senha incorretos"


def _gravar_cookie(resposta: Response, token: str, request: Request) -> None:
    """Poe o token no cookie, com as tres protecoes.

    - `httponly`: o JS da pagina nao le o token, entao um XSS nao o rouba.
    - `samesite="strict"`: o navegador so manda o cookie em requisicao que
      partiu do proprio site. Sem isso, qualquer pagina aberta noutra aba
      conseguiria disparar uma requisicao autenticada em nome de quem esta
      logado (CSRF).
    - `secure`: so quando a requisicao chegou por https. Fixo em True
      quebraria o desenvolvimento em http://localhost, onde o navegador
      descarta cookie seguro; fixo em False mandaria o token em texto
      claro quando o app for hospedado.
    """
    resposta.set_cookie(
        COOKIE,
        token,
        httponly=True,
        samesite="strict",
        secure=request.url.scheme == "https",
        max_age=int(autenticacao.VALIDADE.total_seconds()),
        path="/",
    )


def _token_da_requisicao(request: Request) -> Optional[str]:
    """O token, do cookie ou do cabecalho. Nessa ordem."""
    do_cookie = request.cookies.get(COOKIE)
    if do_cookie:
        return do_cookie
    cabecalho = request.headers.get("authorization", "")
    if cabecalho.lower().startswith("bearer "):
        return cabecalho[7:].strip()
    return None


def usuario_atual(request: Request) -> Usuario:
    """A conta logada, ou 401.

    Montada em `api.py` como dependencia dos routers protegidos, e nao
    rota a rota: assim rota nova nasce protegida por omissao, e esquecer
    de proteger exige um ato explicito em vez de um descuido.
    """
    usuario = autenticacao.usuario_do_token(_token_da_requisicao(request))
    if usuario is None:
        raise HTTPException(401, "faca login para continuar")
    return usuario


@router.post("/cadastro", status_code=201)
def cadastro(entrada: CadastroEntrada, resposta: Response, request: Request):
    """Cria a conta e ja deixa a pessoa logada.

    Entrar em seguida seria um segundo passo sem utilidade: quem acabou de
    provar que tem a senha nao precisa prova-la de novo.
    """
    novo = Usuario(
        nome=entrada.nome,
        email=entrada.email,
        senha_hash=autenticacao.cifrar_senha(entrada.senha),
        papel=entrada.papel,
    )
    try:
        usuario = repo_usuarios.criar(novo)
    except IntegrityError:
        # O indice unico e quem decide, nao uma consulta antes do insert:
        # entre a checagem e a gravacao cabe outro cadastro igual.
        raise HTTPException(
            409,
            {
                "erro": "email_em_uso",
                "mensagem": "ja existe uma conta com este e-mail",
            },
        )

    # A conta PARTICULAR ganha o cliente "eu mesmo" ja no cadastro: e ele
    # que os carros dela vao usar, e sem isso o primeiro cadastro de
    # veiculo teria de criar um cliente que a interface nunca mostra.
    if usuario.papel == PapelUsuario.PARTICULAR:
        repo_clientes.implicito_de(usuario.id, usuario.nome)

    _gravar_cookie(resposta, autenticacao.abrir_login(usuario), request)
    return usuario_publico(usuario)


@router.post("/login")
def login(entrada: LoginEntrada, resposta: Response, request: Request):
    """Confere as credenciais e abre o login.

    A mesma frase para e-mail inexistente e senha errada, e o
    `conferir_senha` gasta o mesmo tempo nos dois casos - senao a demora
    da resposta contaria o que a mensagem esconde.
    """
    usuario = repo_usuarios.buscar_por_email(entrada.email)
    if not autenticacao.conferir_senha(
        entrada.senha, usuario.senha_hash if usuario else None
    ):
        raise HTTPException(401, CREDENCIAL_INVALIDA)

    _gravar_cookie(resposta, autenticacao.abrir_login(usuario), request)
    return usuario_publico(usuario)


@router.post("/logout")
def logout(request: Request, resposta: Response):
    """Encerra o login: apaga a linha do token e o cookie.

    Sempre 200, mesmo sem token valido - "sair" nao tem por que falhar, e
    o resultado pedido (nao estar mais logado) ja esta valendo.
    """
    autenticacao.fechar_login(_token_da_requisicao(request))
    resposta.delete_cookie(COOKIE, path="/")
    return {"saiu": True}


@router.put("/eu")
def trocar_papel(
    entrada: PapelEntrada, usuario: Usuario = Depends(usuario_atual)
):
    """Troca o papel da conta.

    **Nao apaga nada.** Sair de PROFISSIONAL para PARTICULAR so muda o que
    a interface mostra: os clientes continuam gravados, e os carros
    continuam pendurados neles. A tela avisa quantos vao sumir de vista
    antes de confirmar - e a conta pode voltar a PROFISSIONAL e reencontrar
    tudo.

    Virando PARTICULAR, garante o cliente implicito: e nele que os carros
    novos vao entrar.
    """
    atualizado = repo_usuarios.trocar_papel(usuario.id, entrada.papel)
    if atualizado is None:
        raise HTTPException(404, "conta nao encontrada")
    if atualizado.papel == PapelUsuario.PARTICULAR:
        repo_clientes.implicito_de(atualizado.id, atualizado.nome)
    return usuario_publico(atualizado)


@router.get("/eu")
def eu(usuario: Usuario = Depends(usuario_atual)):
    """Quem esta logado.

    E por aqui que o frontend se recupera de um F5: o estado dele vive em
    memoria e some, mas o cookie sobrevive e esta rota o traduz de volta
    em usuario.
    """
    return usuario_publico(usuario)
