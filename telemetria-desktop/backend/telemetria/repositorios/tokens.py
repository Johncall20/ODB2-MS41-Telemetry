"""Os tokens de acesso: criar no login, achar na requisicao, apagar no
logout.

Guarda o HASH do token, nunca o token - por isso toda busca aqui recebe o
hash ja calculado por `servicos/autenticacao`.
"""

from datetime import datetime
from typing import Optional

from sqlmodel import delete, select

from ..banco import sessao_db
from ..modelos import TokenAcesso, agora


def criar(usuario_id: int, token_hash: str, expira_em: datetime) -> TokenAcesso:
    """Registra um login em curso."""
    with sessao_db() as db:
        linha = TokenAcesso(
            usuario_id=usuario_id, token_hash=token_hash, expira_em=expira_em
        )
        db.add(linha)
        db.commit()
        db.refresh(linha)
        return linha


def buscar_valido(token_hash: str) -> Optional[TokenAcesso]:
    """O token, se existir E ainda nao tiver expirado.

    A validade entra na consulta em vez de ser conferida depois: assim nao
    ha caminho em que alguem esqueca de checar e um token vencido passe.
    """
    with sessao_db() as db:
        return db.exec(
            select(TokenAcesso).where(
                TokenAcesso.token_hash == token_hash,
                TokenAcesso.expira_em > agora(),
            )
        ).first()


def apagar(token_hash: str) -> bool:
    """Encerra este login. False se ja nao havia nada para apagar.

    E o logout de verdade: some a linha, e a proxima requisicao com esse
    token nao encontra nada. Era isto que o JWT nao daria sem uma denylist.
    """
    with sessao_db() as db:
        linha = db.exec(
            select(TokenAcesso).where(TokenAcesso.token_hash == token_hash)
        ).first()
        if linha is None:
            return False
        db.delete(linha)
        db.commit()
        return True


def apagar_do_usuario(usuario_id: int) -> int:
    """Derruba TODOS os logins de uma conta. Devolve quantos cairam.

    Nao ha rota que use ainda; existe porque trocar senha ou suspeitar de
    vazamento pede exatamente isto, e o lugar dessa consulta e aqui.
    """
    with sessao_db() as db:
        resultado = db.exec(
            delete(TokenAcesso).where(TokenAcesso.usuario_id == usuario_id)
        )
        db.commit()
        return resultado.rowcount or 0


def limpar_expirados() -> int:
    """Remove o que ja venceu. Devolve quantas linhas saiu.

    Token vencido nao autentica ninguem (a validade esta na consulta), mas
    a tabela cresceria para sempre sem isto.
    """
    with sessao_db() as db:
        resultado = db.exec(delete(TokenAcesso).where(TokenAcesso.expira_em <= agora()))
        db.commit()
        return resultado.rowcount or 0
