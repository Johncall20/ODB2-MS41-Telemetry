"""
Rotas de cliente: a lista e o cadastro da tela de Clientes.

So a conta PROFISSIONAL usa estas telas, mas as rotas **existem para as
duas**: o modelo e o mesmo, e o que muda e a interface esconder o cadastro
para o PARTICULAR. Duas arvores de rota - uma com cliente, outra sem -
dobrariam cada consulta de veiculo que ja existe.

O cliente implicito (o "eu mesmo" da conta PARTICULAR) nao aparece na
listagem: nao e alguem que a pessoa cadastrou.
"""

from fastapi import APIRouter, Depends, HTTPException

from ..modelos import Usuario
from ..repositorios import clientes as repo_clientes
from .auth import usuario_atual
from .esquemas import ClienteEntrada, cliente_publico

router = APIRouter(prefix="/api/clientes", tags=["clientes"])


@router.get("")
def listar(usuario: Usuario = Depends(usuario_atual)):
    """Os clientes da conta, com quantos carros ativos cada um tem."""
    return [
        {**cliente_publico(linha["cliente"]), "veiculos": linha["veiculos"]}
        for linha in repo_clientes.listar(usuario.id)
    ]


@router.post("", status_code=201)
def criar(entrada: ClienteEntrada, usuario: Usuario = Depends(usuario_atual)):
    """Cadastra um cliente na conta."""
    cliente = repo_clientes.criar(usuario.id, entrada.nome, entrada.contato)
    return cliente_publico(cliente)


@router.put("/{cliente_id}")
def editar(
    cliente_id: int, entrada: ClienteEntrada, usuario: Usuario = Depends(usuario_atual)
):
    """Grava nome e contato.

    Cliente de outra conta responde 404, e nao 403: 403 confirmaria que o
    id existe.
    """
    cliente = repo_clientes.editar(cliente_id, usuario.id, entrada.model_dump())
    if cliente is None:
        raise HTTPException(404, "cliente nao encontrado")
    return cliente_publico(cliente)
