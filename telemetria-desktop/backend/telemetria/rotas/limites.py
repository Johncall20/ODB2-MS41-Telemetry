"""
Os valores SUGERIDOS de limite - o ponto de partida que a tela oferece.

Nao ha mais limite global editavel: os limites sao por veiculo e moram em
`GET/PUT /api/veiculos/{id}/limites`, em `rotas/veiculos.py`. O que sobra
aqui e a leitura da constante, para o botao "Usar valores sugeridos" nao
precisar repetir os numeros no frontend.
"""

from fastapi import APIRouter

from ..repositorios import limites as repo_limites

router = APIRouter(prefix="/api/limites", tags=["limites"])


@router.get("/sugeridos")
def ler_sugeridos():
    """O ponto de partida de um carro novo. Nao e o limite de ninguem.

    Quem consome e o botao da tela de limites do veiculo: ele so preenche
    o formulario, e salvar continua sendo um ato separado.
    """
    return repo_limites.sugeridos()
