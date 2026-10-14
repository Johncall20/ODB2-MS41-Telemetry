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

from ..contexto import Contexto, obter_contexto
from ..modelos import PapelUsuario, Usuario
from ..repositorios import clientes as repo_clientes
from ..repositorios import sessoes as repo_sessoes
from ..repositorios import usuarios as repo_usuarios
from ..servicos import autenticacao
from .esquemas import (
    CadastroEntrada,
    ExclusaoEntrada,
    LoginEntrada,
    PapelEntrada,
    PerfilEntrada,
    SenhaEntrada,
    usuario_publico,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])

COOKIE = "telemetria_sessao"

# Resposta unica para e-mail inexistente e senha errada. Dizer qual dos
# dois falhou entrega uma lista de e-mails cadastrados a quem quiser
# tentar.
CREDENCIAL_INVALIDA = "e-mail ou senha incorretos"

EMAIL_EM_USO = {"erro": "email_em_uso", "mensagem": "já existe uma conta com este e-mail"}


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
        raise HTTPException(401, "faça login para continuar")
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
        raise HTTPException(409, EMAIL_EM_USO)

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
        raise HTTPException(404, "conta não encontrada")
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


def _exigir_senha(usuario: Usuario, senha: str) -> None:
    """403 se a senha atual nao confere.

    403 e nao 401: a pessoa ESTA logada, so digitou a senha errada. 401
    quer dizer "sem sessao", e um tratamento de 401 no front a deslogaria
    por um erro de digitacao.
    """
    if not autenticacao.conferir_senha(senha or "", usuario.senha_hash):
        raise HTTPException(
            403, {"erro": "senha_incorreta", "mensagem": "senha atual incorreta"}
        )


@router.put("/eu/perfil")
def editar_perfil(entrada: PerfilEntrada, usuario: Usuario = Depends(usuario_atual)):
    """Grava nome e e-mail.

    Trocar o e-mail exige a senha atual: e trocar a credencial do login, e
    quem achasse um navegador aberto nao pode tomar a conta por aqui. Nome
    sozinho nao exige.
    """
    if entrada.email != usuario.email:
        _exigir_senha(usuario, entrada.senha_atual)
    try:
        atualizado = repo_usuarios.editar_perfil(usuario.id, entrada.nome, entrada.email)
    except IntegrityError:
        raise HTTPException(409, EMAIL_EM_USO)
    if atualizado is None:
        raise HTTPException(404, "conta não encontrada")
    return usuario_publico(atualizado)


@router.put("/eu/senha")
def trocar_senha(
    entrada: SenhaEntrada, request: Request, usuario: Usuario = Depends(usuario_atual)
):
    """Troca a senha e derruba todo OUTRO login da conta.

    Quem trocou continua logado neste navegador; os outros caem na proxima
    requisicao. E o que se espera de quem troca a senha por desconfiar que
    alguem a tem.
    """
    _exigir_senha(usuario, entrada.senha_atual)
    if len(entrada.senha_nova) < autenticacao.SENHA_MINIMA:
        raise HTTPException(
            422,
            {
                "erro": "senha_curta",
                "mensagem": f"a senha nova precisa ter pelo menos "
                f"{autenticacao.SENHA_MINIMA} caracteres",
            },
        )
    repo_usuarios.trocar_senha(usuario.id, autenticacao.cifrar_senha(entrada.senha_nova))
    derrubados = autenticacao.fechar_outros_logins(usuario.id, _token_da_requisicao(request))
    return {"trocada": True, "logins_encerrados": derrubados}


@router.get("/eu/dados")
def dados_da_conta(usuario: Usuario = Depends(usuario_atual)):
    """O que a exclusao apagaria: clientes, veiculos e sessoes."""
    return repo_usuarios.contar_dados(usuario.id)


@router.post("/eu/excluir")
def excluir_conta(
    entrada: ExclusaoEntrada,
    resposta: Response,
    ctx: Contexto = Depends(obter_contexto),
    usuario: Usuario = Depends(usuario_atual),
):
    """Apaga a conta e tudo que pertence a ela. Nao tem volta.

    Exclusao REAL, e nao arquivamento: e dado pessoal, e a LGPD da ao
    titular o direito de eliminacao. Ver "Exclusao de conta" no CLAUDE.md.

    Recusa com 409 se um carro desta conta esta gravando agora. Encerrar
    sozinho disputaria com o ultimo lote de amostras do `Gravador`, que
    poderia chegar depois do DELETE. Gravacao de outra conta nao bloqueia.

    POST e nao DELETE porque leva corpo (senha e confirmacao), e corpo em
    DELETE e descartado por parte dos proxies.
    """
    _exigir_senha(usuario, entrada.senha)
    if entrada.confirmacao.strip().lower() != usuario.email:
        raise HTTPException(
            422,
            {
                "erro": "confirmacao_invalida",
                "mensagem": "digite o e-mail da conta para confirmar",
            },
        )

    if ctx.gravador.sessao_id is not None:
        if repo_sessoes.buscar(ctx.gravador.sessao_id, usuario.id) is not None:
            raise HTTPException(
                409,
                {
                    "erro": "gravacao_ativa",
                    "mensagem": "encerre a gravação no Ao vivo antes de excluir a conta",
                },
            )

    apagadas = repo_usuarios.excluir(usuario.id)
    resposta.delete_cookie(COOKIE, path="/")
    return {"excluida": True, "apagadas": apagadas}
