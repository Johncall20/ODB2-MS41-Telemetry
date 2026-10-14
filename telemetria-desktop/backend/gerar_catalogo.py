"""
Gera `catalogo_veiculos.json` a partir da tabela FIPE, com a faixa de anos
de cada modelo. Roda a mao:

    set FIPE_TOKEN=...                      (opcional; ver adiante)
    .venv\\Scripts\\python.exe gerar_catalogo.py

Consulta a API da parallelum: a lista de marcas, a de modelos de cada
marca e, por modelo, `/models/{modelo}/years` - umas 7.500 requisicoes. A
coleta completa de 2026-10-08 rodou numa execucao so (7.496 requisicoes,
sem nenhum 429). A API documenta COTA DIARIA (500 sem token, 1.000 com o
token gratuito, no header `X-Subscription-Token`); se ela for aplicada, o
script para e retoma de onde parou na execucao seguinte:

- O progresso vai para `catalogo_progresso.json`, gravado a cada
  `SALVAR_A_CADA` requisicoes, ao fim de cada marca e ao parar. Rodar de
  novo retoma de onde parou: so pede o que ainda nao esta la. O arquivo
  so existe durante uma coleta (esta no .gitignore): quando ela termina,
  pode ser apagado - o resultado ja esta no `catalogo_veiculos.json`.
  Apagado, a proxima execucao recomeca do zero.
- Para de forma limpa no 429 (cota esgotada, diz quando ela volta), numa
  requisicao que falha `TENTATIVAS` vezes seguidas e no Ctrl+C - sempre
  salvando antes.
- Toda rodada, completa ou nao, reescreve o `catalogo_veiculos.json` com
  o que ja se sabe e diz quantos modelos tem faixa. Marca cuja lista de
  modelos ainda nao veio fica com os modelos do JSON anterior, sem faixa:
  o catalogo nunca encolhe por uma coleta pela metade.
- Ordem: as marcas mais comuns no Brasil primeiro (`PRIORIDADE`), depois
  as outras em ordem alfabetica - uma coleta parcial ja cobre quase todo
  carro cadastrado.

Depois, `executar.py --carregar-catalogo` leva as faixas ao banco. O app
le SO do JSON, nunca da rede - nem a migration, nem a recarga.

Anos: o `code` de cada item e "ANO-COMBUSTIVEL" ("1997-1"); o mesmo ano
repete por combustivel. O "zero km" vem como ano 32000, e vira o ano que
vem. A faixa e so o primeiro e o ultimo ano: a FIPE tem buracos (o 320i
tem 1991-1993 e 2006-2007), e o formulario aceita o intervalo inteiro.

Nao importa nada de `telemetria/` alem do normalizador de texto: e um
script de dados, nao parte do app.

Modelo FIPE e VERSAO ("325iA 2.5 24V Protection"), nao familia. E o que a
API entrega, e o catalogo guarda assim.
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

from telemetria.normalizacao import texto_curto

BASE = "https://fipe.parallelum.com.br/api/v2/cars/brands"
RAIZ = Path(__file__).resolve().parent
DESTINO = RAIZ / "catalogo_veiculos.json"
PROGRESSO = RAIZ / "catalogo_progresso.json"

# Pausa entre requisicoes e tentativas por requisicao. Nao vale queimar a
# cota com rajada.
PAUSA_S = 1.0
TENTATIVAS = 3
SALVAR_A_CADA = 25

# O ano que a FIPE usa para "zero km".
ANO_ZERO_KM = 32000

# As marcas mais comuns no Brasil, pelo nome FIPE, nesta ordem. As outras
# vem depois, em ordem alfabetica.
PRIORIDADE = [
    "VW - VolksWagen",
    "GM - Chevrolet",
    "Fiat",
    "Ford",
    "Toyota",
    "Honda",
    "Hyundai",
    "Renault",
    "BMW",
]

# A FIPE escreve algumas marcas com o prefixo da sigla ("VW - VolksWagen").
# Ninguem procura o carro assim, e o cadastro antigo tinha "Volkswagen". A
# renomeacao e EXPLICITA, marca a marca: uma regra generica ("tira o que
# vem antes do hifen") renomearia em silencio a proxima marca que a FIPE
# inventar. Fora daqui, a grafia e a da FIPE.
RENOMEAR_MARCAS = {
    "VW - VolksWagen": "Volkswagen",
    "GM - Chevrolet": "Chevrolet",
}

# Marca para o carro cuja marca nao esta na FIPE. Nao tem modelo de
# catalogo: tudo nela e customizado por conta.
MARCA_OUTRA = "Outra"


class Parada(Exception):
    """A rodada termina aqui: o progresso e salvo e o JSON reescrito."""

    def __init__(self, motivo: str, codigo: int = 0):
        super().__init__(motivo)
        self.codigo = codigo


# --- Rede -----------------------------------------------------------------


class Fipe:
    """As requisicoes, contadas. 404 devolve None (modelo sem anos)."""

    def __init__(self, token: str | None, limite: int | None):
        self.token = token
        self.limite = limite
        self.feitas = 0

    def pegar(self, url: str):
        if self.limite is not None and self.feitas >= self.limite:
            raise Parada(f"limite desta rodada ({self.limite} requisicoes)")
        cabecalhos = {"User-Agent": "telemetria-tcc/1.0"}
        if self.token:
            cabecalhos["X-Subscription-Token"] = self.token
        ultima = None
        for tentativa in range(TENTATIVAS):
            time.sleep(PAUSA_S * (tentativa + 1))
            self.feitas += 1
            try:
                req = urllib.request.Request(url, headers=cabecalhos)
                with urllib.request.urlopen(req, timeout=30) as r:
                    return json.loads(r.read().decode("utf-8"))
            except urllib.error.HTTPError as erro:
                if erro.code == 429:
                    raise Parada(_cota_esgotada(erro.headers))
                if erro.code == 404:
                    return None
                if erro.code in (401, 403):
                    raise Parada(f"a API recusou o acesso ({erro.code}): confira o FIPE_TOKEN", 1)
                ultima = erro
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as erro:
                ultima = erro
        raise Parada(f"falhou {TENTATIVAS} vezes seguidas: {url}: {ultima}", 1)


def _cota_esgotada(cabecalhos) -> str:
    """A frase do 429, com quando a cota volta se a API disser."""
    for nome in ("x-ratelimit-reset", "retry-after"):
        valor = cabecalhos.get(nome) if cabecalhos else None
        if valor and str(valor).isdigit():
            horas = int(valor) / 3600
            return f"cota diaria esgotada (429); volta em cerca de {horas:.1f} h"
    return "cota diaria esgotada (429); tente de novo amanha"


# --- Anos -----------------------------------------------------------------


def faixa_de_anos(anos: list[dict] | None, ano_atual: int | None = None) -> list[int] | None:
    """`[ano_min, ano_max]` a partir da resposta de `/years`, ou None.

    O ano e o comeco do `code` ("1997-1"); 32000 e "zero km" e vira o ano
    que vem. Lista vazia ou 404 (None) e modelo sem faixa.
    """
    ano_atual = ano_atual or date.today().year
    valores = []
    for item in anos or []:
        inicio = str(item.get("code", "")).split("-")[0]
        if not inicio.isdigit():
            continue
        ano = int(inicio)
        valores.append(ano_atual + 1 if ano == ANO_ZERO_KM else ano)
    if not valores:
        return None
    return [min(valores), max(valores)]


def _juntar(a: list[int] | None, b: list[int] | None) -> list[int] | None:
    """Duas faixas do mesmo nome (dois codigos FIPE que normalizam igual)."""
    if a is None or b is None:
        return a or b
    return [min(a[0], b[0]), max(a[1], b[1])]


# --- Progresso ------------------------------------------------------------


def _vazio() -> dict:
    return {"marcas": None, "modelos": {}, "anos": {}}


def ler_progresso(caminho: Path) -> dict:
    if not caminho.exists():
        return _vazio()
    return {**_vazio(), **json.loads(caminho.read_text(encoding="utf-8"))}


def _gravar(caminho: Path, dados) -> None:
    """Grava num temporario e troca: parar no meio nunca deixa o arquivo
    pela metade."""
    temporario = caminho.with_suffix(caminho.suffix + ".tmp")
    temporario.write_text(_json_por_linha(dados) + "\n", encoding="utf-8")
    os.replace(temporario, caminho)


def _json_por_linha(valor, nivel: int = 0) -> str:
    """JSON com uma folha por linha: lista ou objeto so de valores simples
    sai inteiro numa linha. Sao milhares de modelos - assim o diff entre
    duas coletas mostra o modelo que mudou, e nao um mar de colchetes."""
    simples = (str, int, float, bool, type(None))
    if isinstance(valor, dict):
        itens = valor.items()
    elif isinstance(valor, list):
        itens = None
    else:
        return json.dumps(valor, ensure_ascii=False)
    filhos = valor.values() if itens is not None else valor
    if all(isinstance(f, simples) for f in filhos):
        return json.dumps(valor, ensure_ascii=False)
    recuo = " " * (nivel + 1)
    if itens is not None:
        partes = [
            f"{recuo}{json.dumps(k, ensure_ascii=False)}: {_json_por_linha(v, nivel + 1)}"
            for k, v in itens
        ]
        return "{\n" + ",\n".join(partes) + "\n" + " " * nivel + "}"
    partes = [f"{recuo}{_json_por_linha(v, nivel + 1)}" for v in valor]
    return "[\n" + ",\n".join(partes) + "\n" + " " * nivel + "]"


# --- Coleta ---------------------------------------------------------------


def _nome_da_marca(nome_fipe: str) -> str:
    return texto_curto(RENOMEAR_MARCAS.get(nome_fipe, nome_fipe))


def ordem_das_marcas(marcas: list[dict]) -> list[dict]:
    """As de `PRIORIDADE` na ordem dela, depois o resto por nome."""

    def chave(m):
        nome = m["name"]
        if nome in PRIORIDADE:
            return (0, PRIORIDADE.index(nome), "")
        return (1, 0, _nome_da_marca(nome).lower())

    return sorted(marcas, key=chave)


def coletar(fipe: Fipe, progresso: dict, salvar) -> None:
    """Pede o que falta, marca a marca. Levanta `Parada` ao parar antes."""
    desde_salvo = 0

    def contou():
        nonlocal desde_salvo
        desde_salvo += 1
        if desde_salvo >= SALVAR_A_CADA:
            salvar()
            desde_salvo = 0

    if progresso["marcas"] is None:
        progresso["marcas"] = [
            {"code": str(m["code"]), "name": m["name"]} for m in fipe.pegar(BASE) or []
        ]
        contou()
        print(f"[catalogo] {len(progresso['marcas'])} marcas na FIPE")

    for marca in ordem_das_marcas(progresso["marcas"]):
        codigo = marca["code"]
        if codigo not in progresso["modelos"]:
            modelos = fipe.pegar(f"{BASE}/{codigo}/models") or []
            progresso["modelos"][codigo] = [[str(m["code"]), m["name"]] for m in modelos]
            contou()
        faltam = [
            m for m, _ in progresso["modelos"][codigo] if f"{codigo}/{m}" not in progresso["anos"]
        ]
        for modelo in faltam:
            anos = fipe.pegar(f"{BASE}/{codigo}/models/{modelo}/years")
            progresso["anos"][f"{codigo}/{modelo}"] = faixa_de_anos(anos)
            contou()
        if faltam:
            salvar()
            desde_salvo = 0
            print(
                f"[catalogo] {_nome_da_marca(marca['name'])}: "
                f"{len(progresso['modelos'][codigo])} modelos, faixa completa"
            )


# --- O JSON do catalogo ---------------------------------------------------


def _modelos_do_json_anterior(caminho: Path) -> dict[str, list[dict]]:
    """Os modelos de cada marca no JSON que ja existe, nos dois formatos
    (so nome, ou objeto com faixa). Para a marca ainda nao coletada."""
    if not caminho.exists():
        return {}
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    anteriores = {}
    for marca in dados.get("marcas", []):
        modelos = []
        for m in marca.get("modelos", []):
            m = {"nome": m} if isinstance(m, str) else m
            modelos.append(
                {"nome": m["nome"], "ano_min": m.get("ano_min"), "ano_max": m.get("ano_max")}
            )
        anteriores[marca["nome"].lower()] = modelos
    return anteriores


def montar_catalogo(progresso: dict, anteriores: dict[str, list[dict]]) -> dict:
    """O `catalogo_veiculos.json` a partir do progresso, completo ou nao.

    Nomes normalizados e sem repetir (sem diferenciar maiusculas; o
    primeiro vence a grafia, as faixas se juntam), ordenados para o diff
    entre duas geracoes ser legivel.
    """
    marcas: dict[str, dict] = {}
    for marca in progresso["marcas"] or []:
        nome = _nome_da_marca(marca["name"])
        # Duas marcas FIPE que virassem o mesmo nome (por renomeacao)
        # juntam os modelos, em vez de uma apagar a outra.
        destino = marcas.setdefault(nome.lower(), {"nome": nome, "modelos": {}})
        coletados = progresso["modelos"].get(marca["code"])
        if coletados is None:
            pares = [
                (m["nome"], [m["ano_min"], m["ano_max"]] if m["ano_min"] is not None else None)
                for m in anteriores.get(nome.lower(), [])
            ]
        else:
            pares = [
                (n, progresso["anos"].get(f"{marca['code']}/{c}")) for c, n in coletados
            ]
        for bruto, faixa in pares:
            nome_modelo = texto_curto(bruto)
            if not nome_modelo:
                continue
            atual = destino["modelos"].get(nome_modelo.lower())
            if atual is None:
                destino["modelos"][nome_modelo.lower()] = {"nome": nome_modelo, "faixa": faixa}
            else:
                atual["faixa"] = _juntar(atual["faixa"], faixa)

    marcas.setdefault(MARCA_OUTRA.lower(), {"nome": MARCA_OUTRA, "modelos": {}})
    lista = []
    for m in sorted(marcas.values(), key=lambda m: m["nome"].lower()):
        modelos = sorted(m["modelos"].values(), key=lambda x: x["nome"].lower())
        lista.append(
            {
                "nome": m["nome"],
                "modelos": [
                    {
                        "nome": x["nome"],
                        "ano_min": x["faixa"][0] if x["faixa"] else None,
                        "ano_max": x["faixa"][1] if x["faixa"] else None,
                    }
                    for x in modelos
                ],
            }
        )
    return {
        "fonte": BASE,
        "gerado_em": date.today().isoformat(),
        "marcas_renomeadas": RENOMEAR_MARCAS,
        "marcas": lista,
    }


def contar(catalogo: dict) -> tuple[int, int]:
    """(modelos com faixa, modelos)."""
    modelos = [x for m in catalogo["marcas"] for x in m["modelos"]]
    return sum(1 for x in modelos if x["ano_min"] is not None), len(modelos)


def pendentes(progresso: dict) -> tuple[int, int]:
    """(marcas sem a lista de modelos, modelos ainda nao consultados).
    Modelo consultado sem anos (404, lista vazia) nao e pendencia: a FIPE
    respondeu, e ele fica sem faixa."""
    marcas = [m["code"] for m in progresso["marcas"] or []]
    sem_lista = sum(1 for c in marcas if c not in progresso["modelos"])
    sem_anos = sum(
        1
        for c in marcas
        for m, _ in progresso["modelos"].get(c, [])
        if f"{c}/{m}" not in progresso["anos"]
    )
    return sem_lista, sem_anos


def main() -> None:
    p = argparse.ArgumentParser(description="Gera o catalogo de veiculos a partir da FIPE")
    p.add_argument("--saida", type=Path, default=DESTINO)
    p.add_argument("--progresso", type=Path, default=PROGRESSO)
    p.add_argument(
        "--limite", type=int, default=None, help="no maximo N requisicoes nesta rodada"
    )
    args = p.parse_args()

    token = os.environ.get("FIPE_TOKEN") or None
    print(f"[catalogo] {'com' if token else 'sem'} token (FIPE_TOKEN)")
    progresso = ler_progresso(args.progresso)
    anteriores = _modelos_do_json_anterior(args.saida)
    fipe = Fipe(token, args.limite)

    codigo, motivo = 0, "coleta completa"
    try:
        coletar(fipe, progresso, lambda: _gravar(args.progresso, progresso))
    except Parada as parada:
        codigo, motivo = parada.codigo, str(parada)
    except KeyboardInterrupt:
        codigo, motivo = 130, "interrompido (Ctrl+C)"

    _gravar(args.progresso, progresso)
    print(f"[catalogo] {motivo}; {fipe.feitas} requisicoes nesta rodada")
    if progresso["marcas"] is None:
        sys.exit(codigo or 1)

    catalogo = montar_catalogo(progresso, anteriores)
    _gravar(args.saida, catalogo)
    com_faixa, total = contar(catalogo)
    print(
        f"[catalogo] {len(catalogo['marcas'])} marcas, {total} modelos, "
        f"{com_faixa} com faixa de anos -> {args.saida}"
    )
    sem_lista, sem_anos = pendentes(progresso)
    if sem_lista or sem_anos:
        print(
            f"[catalogo] falta consultar {sem_anos} modelo(s) e a lista de {sem_lista} "
            "marca(s): rode de novo (amanha, se a cota acabou)"
        )
    print("[catalogo] para levar ao banco: executar.py --carregar-catalogo")
    sys.exit(codigo)


if __name__ == "__main__":
    main()
