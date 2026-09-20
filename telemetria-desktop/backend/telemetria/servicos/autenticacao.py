"""
Senha e token: as duas regras de autenticacao, sem saber de HTTP.

Quem fala HTTP e `rotas/auth.py`; quem toca o banco sao os repositorios.
Aqui ficam so as decisoes de criptografia e validade.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta
from typing import Optional

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from ..modelos import TokenAcesso, Usuario, agora
from ..repositorios import tokens as repo_tokens
from ..repositorios import usuarios as repo_usuarios

# Validade UNICA e fixa. Nao ha "manter conectado" - quando houver, e este
# numero que passa a variar por login, e nao um segundo tipo de token.
VALIDADE = timedelta(hours=12)

SENHA_MINIMA = 8

# argon2 direto, sem passlib: a camada extra esta semi-abandonada e hoje so
# acrescenta avisos de incompatibilidade. Os parametros sao os padroes da
# biblioteca, que seguem a recomendacao da RFC 9106.
_hasher = PasswordHasher()

# Hash descartavel, de uma senha que ninguem tem. Serve para o login gastar
# o mesmo tempo quando o e-mail NAO existe - sem isso, responder rapido
# demais contaria que a conta nao existe, que e justamente o que a
# mensagem unica de erro esconde.
_HASH_FALSO = _hasher.hash("conta-inexistente-" + secrets.token_hex(8))


def cifrar_senha(senha: str) -> str:
    """O hash que vai para o banco. A senha em texto morre aqui."""
    return _hasher.hash(senha)


def conferir_senha(senha: str, hash_guardado: Optional[str]) -> bool:
    """A senha bate com o hash?

    `hash_guardado` None significa "conta nao existe": confere contra um
    hash falso para gastar o mesmo tempo e devolve False.
    """
    try:
        _hasher.verify(hash_guardado or _HASH_FALSO, senha)
    except (VerifyMismatchError, InvalidHashError):
        return False
    return hash_guardado is not None


def _hash_do_token(token: str) -> str:
    """SHA-256 do token.

    SHA-256 e nao argon2 de proposito: o token e 32 bytes aleatorios, nao
    uma senha escolhida por gente. Nao ha o que adivinhar por forca bruta,
    e a busca acontece a cada requisicao - argon2 ali custaria caro sem
    proteger de nada.
    """
    return hashlib.sha256(token.encode()).hexdigest()


def abrir_login(usuario: Usuario) -> str:
    """Cria o token do login e devolve o valor CRU.

    E a unica vez que o valor cru existe: o banco guarda so o hash. Quem
    chama entrega esse valor ao navegador (no cookie) e esquece.
    """
    token = secrets.token_urlsafe(32)
    repo_tokens.criar(usuario.id, _hash_do_token(token), agora() + VALIDADE)
    return token


def fechar_login(token: Optional[str]) -> bool:
    """Apaga o token. False quando nao havia o que apagar."""
    if not token:
        return False
    return repo_tokens.apagar(_hash_do_token(token))


def usuario_do_token(token: Optional[str]) -> Optional[Usuario]:
    """A conta dona deste token, ou None se ele nao vale mais.

    Nao distingue "nao existe" de "expirou": as duas respostas sao 401, e
    dizer qual e nao ajuda quem tem o token nem quem nao tem.
    """
    if not token:
        return None
    linha: Optional[TokenAcesso] = repo_tokens.buscar_valido(_hash_do_token(token))
    if linha is None:
        return None
    return repo_usuarios.buscar(linha.usuario_id)
