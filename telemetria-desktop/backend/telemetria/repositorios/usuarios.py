"""Consultas de usuario: cadastro e as duas buscas que o login precisa.

O objeto volta desanexado, como em todo repositorio deste pacote - inclui
o `senha_hash`, entao quem monta resposta usa
`rotas/esquemas.usuario_publico()` e nunca serializa o modelo inteiro.
"""

from typing import Optional

from sqlmodel import select

from ..banco import sessao_db
from ..modelos import Usuario


def criar(usuario: Usuario) -> Usuario:
    """Grava a conta nova e devolve com o id preenchido.

    E-mail repetido estoura IntegrityError pelo indice unico; quem traduz
    para 409 e a rota, que sabe a frase que a tela mostra.
    """
    with sessao_db() as db:
        db.add(usuario)
        db.commit()
        db.refresh(usuario)
        return usuario


def buscar_por_email(email: str) -> Optional[Usuario]:
    """A conta com este e-mail, ou None.

    O e-mail ja chega normalizado (minusculo, sem espaco nas pontas) da
    entrada Pydantic - aqui nao se normaliza de novo, para nao existirem
    duas regras de normalizacao que possam divergir.
    """
    with sessao_db() as db:
        return db.exec(select(Usuario).where(Usuario.email == email)).first()


def buscar(usuario_id: int) -> Optional[Usuario]:
    """A conta pelo id, ou None. E o que a dependencia de rota usa."""
    with sessao_db() as db:
        return db.get(Usuario, usuario_id)


def trocar_papel(usuario_id: int, papel) -> Optional[Usuario]:
    """Grava o papel novo. None se a conta sumiu.

    So o papel: nome, e-mail e senha nao passam por aqui, para um PUT de
    ajuste de interface nunca poder trocar credencial.
    """
    with sessao_db() as db:
        usuario = db.get(Usuario, usuario_id)
        if usuario is None:
            return None
        usuario.papel = papel
        db.add(usuario)
        db.commit()
        db.refresh(usuario)
        return usuario
