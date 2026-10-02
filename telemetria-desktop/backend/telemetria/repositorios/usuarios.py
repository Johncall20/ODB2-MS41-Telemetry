"""Consultas de usuario: cadastro, as buscas do login, a edicao da conta
e a exclusao dela.

O objeto volta desanexado, como em todo repositorio deste pacote - inclui
o `senha_hash`, entao quem monta resposta usa
`rotas/esquemas.usuario_publico()` e nunca serializa o modelo inteiro.
"""

from typing import Optional

from sqlmodel import delete, func, select

from ..banco import sessao_db
from ..modelos import (
    Amostra,
    Cliente,
    Evento,
    LimitesVeiculo,
    Sessao,
    TokenAcesso,
    Usuario,
    Veiculo,
)


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


def editar_perfil(usuario_id: int, nome: str, email: str) -> Optional[Usuario]:
    """Grava nome e e-mail. None se a conta sumiu.

    E-mail de outra conta estoura IntegrityError pelo indice unico, como
    no cadastro; quem traduz para 409 e a rota. Quem exige a senha atual
    para trocar o e-mail tambem e a rota - aqui nao se sabe de senha.
    """
    with sessao_db() as db:
        usuario = db.get(Usuario, usuario_id)
        if usuario is None:
            return None
        usuario.nome = nome
        usuario.email = email
        db.add(usuario)
        db.commit()
        db.refresh(usuario)
        return usuario


def trocar_senha(usuario_id: int, senha_hash: str) -> bool:
    """Grava o hash novo. Derrubar os outros logins e da rota."""
    with sessao_db() as db:
        usuario = db.get(Usuario, usuario_id)
        if usuario is None:
            return False
        usuario.senha_hash = senha_hash
        db.add(usuario)
        db.commit()
        return True


def _veiculos_da_conta(usuario_id: int):
    return select(Veiculo.id).where(Veiculo.usuario_id == usuario_id)


def _sessoes_da_conta(usuario_id: int):
    return select(Sessao.id).where(Sessao.veiculo_id.in_(_veiculos_da_conta(usuario_id)))


def contar_dados(usuario_id: int) -> dict:
    """Quantos clientes, veiculos e sessoes a conta tem - o que a tela de
    exclusao precisa dizer que vai sumir. Arquivados contam: vao junto.
    O implicito nao conta como cliente, porque a pessoa nunca o viu."""
    with sessao_db() as db:
        return {
            "clientes": db.exec(
                select(func.count(Cliente.id)).where(
                    Cliente.usuario_id == usuario_id,
                    Cliente.implicito == False,  # noqa: E712
                )
            ).one(),
            "veiculos": db.exec(
                select(func.count(Veiculo.id)).where(Veiculo.usuario_id == usuario_id)
            ).one(),
            "sessoes": db.exec(
                select(func.count(Sessao.id)).where(
                    Sessao.id.in_(_sessoes_da_conta(usuario_id))
                )
            ).one(),
        }


def excluir(usuario_id: int) -> dict:
    """Apaga a conta e TUDO que pertence a ela, numa transacao so.

    E a unica exclusao real de dado de usuario no sistema - o resto so
    arquiva. Existe porque e dado pessoal: a LGPD da ao titular o direito
    de eliminacao (ver "Exclusao de conta" no CLAUDE.md).

    `DELETE` em massa por subconsulta, na ordem das FKs (filho antes do
    pai), e nao o cascade do ORM: aquele carregaria cada amostra na
    memoria para apaga-la uma a uma, e uma conta com meses de gravacao tem
    centenas de milhares. O banco NAO tem `ON DELETE CASCADE` de proposito
    - ver o CLAUDE.md.

    O dono do veiculo vem de `veiculo.usuario_id`. Se algum carro violasse
    o invariante (cliente desta conta, usuario_id de outra), o DELETE de
    cliente falharia por FK e a transacao inteira voltaria: nada fica pela
    metade.

    Devolve quantas linhas sairam de cada tabela.
    """
    sessoes = _sessoes_da_conta(usuario_id)
    veiculos = _veiculos_da_conta(usuario_id)
    ordem = (
        ("evento", delete(Evento).where(Evento.sessao_id.in_(sessoes))),
        ("amostra", delete(Amostra).where(Amostra.sessao_id.in_(sessoes))),
        ("sessao", delete(Sessao).where(Sessao.veiculo_id.in_(veiculos))),
        ("limitesveiculo", delete(LimitesVeiculo).where(LimitesVeiculo.veiculo_id.in_(veiculos))),
        ("veiculo", delete(Veiculo).where(Veiculo.usuario_id == usuario_id)),
        ("cliente", delete(Cliente).where(Cliente.usuario_id == usuario_id)),
        ("tokenacesso", delete(TokenAcesso).where(TokenAcesso.usuario_id == usuario_id)),
        ("usuario", delete(Usuario).where(Usuario.id == usuario_id)),
    )
    apagadas = {}
    with sessao_db() as db:
        for tabela, comando in ordem:
            apagadas[tabela] = db.exec(comando).rowcount or 0
        db.commit()
    return apagadas
