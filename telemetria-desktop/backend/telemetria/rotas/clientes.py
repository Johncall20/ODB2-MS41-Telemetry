"""
Rotas de cliente: a lista, o detalhe, o cadastro, a edicao e o
arquivamento da tela de Clientes.

**Leitura** existe para as duas contas - o `/conta` do PARTICULAR ainda
conta os clientes para o aviso de troca de papel. **Escrita** e so do
PROFISSIONAL: criar, editar, arquivar e desarquivar respondem 403 para o
PARTICULAR. Aqui e 403 e nao 404 porque o motivo e o PAPEL, nao a posse -
o cliente e da conta, so que essa conta nao gerencia clientes. Nao ha
nada a esconder: a propria pessoa sabe que o cliente existe.

O cliente implicito (o "eu mesmo" da conta) nao aparece na listagem, e
para detalhe, edicao e arquivamento responde 404, como se nao existisse:
ele nao e alguem que a pessoa cadastrou, e sim o dono dos "Meus carros".
"""

from fastapi import APIRouter, Depends, HTTPException

from ..modelos import PapelUsuario, Usuario
from ..repositorios import clientes as repo_clientes
from .auth import usuario_atual
from .esquemas import ClienteEntrada, cliente_publico

router = APIRouter(prefix="/api/clientes", tags=["clientes"])


def exige_profissional(usuario: Usuario = Depends(usuario_atual)) -> Usuario:
    """A conta logada, se ela gerencia clientes. PARTICULAR recebe 403."""
    if usuario.papel != PapelUsuario.PROFISSIONAL:
        raise HTTPException(
            403,
            {
                "erro": "papel_sem_clientes",
                "mensagem": "conta particular nao gerencia clientes",
            },
        )
    return usuario


def _nao_encontrado() -> HTTPException:
    return HTTPException(404, "cliente nao encontrado")


@router.get("")
def listar(arquivados: bool = False, usuario: Usuario = Depends(usuario_atual)):
    """Os clientes da conta, com quantos carros ativos cada um tem.

    `arquivados=true` troca de lado: so os arquivados, para a aba da tela.
    """
    return [
        {**cliente_publico(linha["cliente"]), "veiculos": linha["veiculos"]}
        for linha in repo_clientes.listar(usuario.id, arquivados=arquivados)
    ]


@router.get("/{cliente_id}")
def detalhe(cliente_id: int, usuario: Usuario = Depends(usuario_atual)):
    """O cliente, mesmo arquivado - e pela tela dele que se desarquiva.

    Os carros nao vem aqui: a tela pede `GET /api/veiculos?cliente_id=`,
    que ja tem os filtros e a ordenacao da lista de Veiculos.
    """
    cliente = repo_clientes.buscar(cliente_id, usuario.id)
    if cliente is None or cliente.implicito:
        raise _nao_encontrado()
    return {
        **cliente_publico(cliente),
        "veiculos": repo_clientes.veiculos_ativos(cliente.id),
    }


@router.post("", status_code=201)
def criar(entrada: ClienteEntrada, usuario: Usuario = Depends(exige_profissional)):
    """Cadastra um cliente na conta."""
    cliente = repo_clientes.criar(usuario.id, entrada.nome, entrada.contato)
    return cliente_publico(cliente)


@router.put("/{cliente_id}")
def editar(
    cliente_id: int,
    entrada: ClienteEntrada,
    usuario: Usuario = Depends(exige_profissional),
):
    """Grava nome e contato. Arquivado tambem se edita.

    Cliente de outra conta, ou o implicito, responde 404, e nao 403: 403
    confirmaria que o id existe.
    """
    cliente = repo_clientes.editar(cliente_id, usuario.id, entrada.model_dump())
    if cliente is None:
        raise _nao_encontrado()
    return cliente_publico(cliente)


@router.delete("/{cliente_id}")
def arquivar(cliente_id: int, usuario: Usuario = Depends(exige_profissional)):
    """Arquiva o cliente. Nao apaga nada, e os carros continuam nele.

    Com carro ATIVO recusa com 409 e a contagem: arquivar o cliente e
    deixar o carro ativo poria um carro nas listas pendurado num dono que
    saiu delas. Quem decide o destino dos carros e a pessoa - arquiva-los
    ou move-los para outro cliente -, nao a rota.
    """
    cliente = repo_clientes.buscar(cliente_id, usuario.id)
    if cliente is None or cliente.implicito:
        raise _nao_encontrado()

    ativos = repo_clientes.veiculos_ativos(cliente.id)
    if ativos:
        carros = "1 carro ativo" if ativos == 1 else f"{ativos} carros ativos"
        raise HTTPException(
            409,
            {
                "erro": "cliente_com_veiculos",
                "mensagem": f"{cliente.nome} tem {carros}; arquive ou mova "
                "os carros para outro cliente antes de arquivar",
                "veiculos": ativos,
            },
        )

    return cliente_publico(repo_clientes.arquivar(cliente.id, usuario.id))


@router.post("/{cliente_id}/restaurar")
def restaurar(cliente_id: int, usuario: Usuario = Depends(exige_profissional)):
    """Traz o cliente de volta a lista e ao seletor do formulario.

    Os carros dele que estavam arquivados continuam arquivados: cada um se
    restaura pela propria tela.
    """
    cliente = repo_clientes.restaurar(cliente_id, usuario.id)
    if cliente is None:
        raise _nao_encontrado()
    return cliente_publico(cliente)
