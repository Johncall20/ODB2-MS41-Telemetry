"""
Rotas do catalogo de marca e modelo: o que o formulario de veiculo
oferece nos dois combobox, e o "Nao encontrei meu modelo".
"""

from fastapi import APIRouter, Depends, HTTPException, Response

from ..modelos import MARCA_OUTRA, Modelo, Usuario
from ..repositorios import catalogo as repo_catalogo
from .auth import usuario_atual
from .esquemas import ModeloEntrada

router = APIRouter(prefix="/api/marcas", tags=["catalogo"])


def modelo_publico(modelo: Modelo) -> dict:
    """Um modelo como a tela o ve. `customizado` diz que e da conta."""
    return {
        "id": modelo.id,
        "marca_id": modelo.marca_id,
        "nome": modelo.nome,
        "customizado": modelo.customizado(),
        # A faixa de anos de modelo da FIPE; nulos quando desconhecida (o
        # formulario cai no 1950 ate o ano que vem).
        "ano_min": modelo.ano_min,
        "ano_max": modelo.ano_max,
    }


def _exigir_marca(marca_id: int) -> None:
    if repo_catalogo.buscar_marca(marca_id) is None:
        raise HTTPException(404, "marca não encontrada")


@router.get("")
def listar_marcas():
    """Todas as marcas, por nome. Sao as mesmas para qualquer conta.

    `outra` marca a marca de quem nao esta na FIPE: a tela a prende no fim
    da lista e troca o combobox de modelo por um campo de texto. E um
    campo, e nao o nome, para o front nao depender da grafia - quem sabe
    qual e a "Outra" e o backend (`MARCA_OUTRA`).
    """
    return [
        {"id": m.id, "nome": m.nome, "outra": m.nome == MARCA_OUTRA}
        for m in repo_catalogo.listar_marcas()
    ]


@router.get("/{marca_id}/modelos")
def listar_modelos(marca_id: int, usuario: Usuario = Depends(usuario_atual)):
    """Catalogo da marca mais os modelos customizados DESTA conta.

    A lista inteira, sem paginar: a maior marca tem perto de 600 modelos,
    e a busca por digitacao e do combobox.
    """
    _exigir_marca(marca_id)
    return [modelo_publico(m) for m in repo_catalogo.listar_modelos(marca_id, usuario.id)]


@router.post("/{marca_id}/modelos")
def criar_modelo(
    marca_id: int,
    entrada: ModeloEntrada,
    resposta: Response,
    usuario: Usuario = Depends(usuario_atual),
):
    """Cria um modelo customizado da conta - ou devolve o que ja existe.

    Mesmo nome (sem diferenciar maiusculas) no catalogo ou nos
    customizados da conta devolve o existente com 200, em vez de
    duplicar. Criado de verdade, 201.
    """
    _exigir_marca(marca_id)
    modelo, criado = repo_catalogo.achar_ou_criar_customizado(
        marca_id, entrada.nome, usuario.id
    )
    resposta.status_code = 201 if criado else 200
    return modelo_publico(modelo)
