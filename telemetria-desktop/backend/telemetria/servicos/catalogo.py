"""
Recarga do catalogo de marca e modelo a partir do `catalogo_veiculos.json`.

Le SO do arquivo, nunca da rede: quem fala com a FIPE e o
`gerar_catalogo.py`, rodado a mao. A primeira carga de um banco vazio vem
da migration 0009 (de um snapshot congelado); isto aqui e para depois de
regerar o JSON - `executar.py --carregar-catalogo`.

Idempotente: rodar duas vezes nao duplica nada, e nada e apagado.
"""

import json
from pathlib import Path

from ..normalizacao import ANO_MINIMO, texto_curto
from ..repositorios import catalogo as repo_catalogo

ARQUIVO_PADRAO = Path(__file__).resolve().parents[2] / "catalogo_veiculos.json"


def _modelo(bruto) -> dict | None:
    """Um modelo do arquivo, nos dois formatos: so o nome (o JSON de antes
    da faixa de anos) ou `{"nome", "ano_min", "ano_max"}`. Faixa so vale
    inteira e em ordem; o resto vira "sem faixa", e nao um erro de carga."""
    if isinstance(bruto, str):
        bruto = {"nome": bruto}
    nome = texto_curto(bruto.get("nome"))
    if not nome:
        return None
    de, ate = bruto.get("ano_min"), bruto.get("ano_max")
    if not (isinstance(de, int) and isinstance(ate, int) and ANO_MINIMO <= de <= ate):
        de = ate = None
    return {"nome": nome, "ano_min": de, "ano_max": ate}


def ler(caminho: Path = ARQUIVO_PADRAO) -> list[dict]:
    """As marcas do arquivo, com os nomes normalizados como a entrada faz.

    O gerador ja normaliza; repetir aqui protege de um JSON editado a mao.
    """
    dados = json.loads(Path(caminho).read_text(encoding="utf-8"))
    marcas = []
    for marca in dados["marcas"]:
        nome = texto_curto(marca["nome"])
        if not nome:
            continue
        modelos = [_modelo(m) for m in marca.get("modelos", [])]
        marcas.append({"nome": nome, "modelos": [m for m in modelos if m]})
    return marcas


def carregar(caminho: Path = ARQUIVO_PADRAO) -> dict:
    """Grava no banco o que o arquivo tem e o banco nao. Devolve contagens."""
    return repo_catalogo.gravar_catalogo(ler(caminho))
