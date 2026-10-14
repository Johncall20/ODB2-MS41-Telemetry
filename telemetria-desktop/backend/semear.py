#!/usr/bin/env python3
"""
Enche um banco de MENTIRA para ver as telas com meses de uso.

    python semear.py             # semeia a base `telemetria_seed`
    python semear.py --recriar   # apaga o que houver la e refaz

Escreve numa base SEPARADA: por padrao troca o nome da base da
`DATABASE_URL` por `telemetria_seed`. Recusa escrever na base de uso real
mesmo que a `DATABASE_URL` aponte direto para ela - perder gravacao de
verdade por causa de um script de desenvolvimento nao e um risco que vale
correr.

A base de seed precisa existir e estar migrada antes. Ver "Banco de
demonstracao" no README.

Tudo passa pelos repositorios, pelos modelos e pelo DetectorEventos de
verdade: nao ha INSERT solto aqui. Se o modelo mudar, este script quebra e
e corrigido junto - que e o ponto.
"""

from __future__ import annotations

import argparse
import math
import os
import random
import sys
from datetime import datetime, timedelta, timezone

BASE_SEED = "telemetria_seed"

# O padrao do proprio seed, e nao o do app. NAO importe `telemetria.banco`
# para reaproveitar o URL_PADRAO dele: aquele modulo cria a engine no
# import, e a engine congela a DATABASE_URL que existir NAQUELE instante.
# Importa-lo antes da troca abaixo faria a seed escrever na base de
# producao com a guarda dizendo que estava tudo bem - foi exatamente o que
# aconteceu quando este arquivo importava de la.
URL_SEED_PADRAO = f"postgresql+psycopg://telemetria:telemetria@localhost:5432/{BASE_SEED}"


def _url_do_seed() -> str:
    """A DATABASE_URL apontando para a base de seed.

    Com DATABASE_URL definida, troca so o nome da base e preserva usuario,
    senha, host e porta: o seed mora no MESMO servidor Postgres que o app,
    em outra base. Sem ela, cai no padrao de desenvolvimento.
    """
    url = os.environ.get("DATABASE_URL")
    if not url:
        return URL_SEED_PADRAO
    base, _, _ = url.rpartition("/")
    return f"{base}/{BASE_SEED}"


def _resolver_alvo() -> str:
    """Decide em que base escrever, e recusa a de uso real.

    `SEMEAR_URL` manda, para quem quiser apontar o seed a outro servidor.
    Sem ela, a base e a de seed derivada da DATABASE_URL. Nos dois casos, a
    ultima palavra e a guarda: base chamada `telemetria` e a de uso real e
    nao recebe dado de mentira, nem com --recriar.
    """
    url = os.environ.get("SEMEAR_URL") or _url_do_seed()
    nome = url.rpartition("/")[2].split("?")[0]
    if nome != BASE_SEED:
        sys.exit(
            f"[semear] recusando escrever na base '{nome}'.\n"
            f"         A seed so escreve em '{BASE_SEED}'. Se quiser outro\n"
            "         destino, aponte a SEMEAR_URL para uma base com esse nome."
        )
    return url


# Definido ANTES de importar telemetria.banco: e na importacao que ele le a
# DATABASE_URL e monta a engine.
os.environ["DATABASE_URL"] = _resolver_alvo()
ALVO = os.environ["DATABASE_URL"]

from telemetria.banco import engine, sessao_db  # noqa: E402

# Cinto e suspensorio: se algum import acima acabar puxando telemetria.banco
# antes desta linha, a engine apontaria para outra base e a guarda de cima
# teria aprovado o destino errado. Melhor morrer aqui do que semear na base
# de producao.
assert str(engine.url).endswith(BASE_SEED), (
    f"engine aponta para {engine.url}, nao para {BASE_SEED} - "
    "telemetria.banco foi importado antes da troca da DATABASE_URL"
)
from telemetria.modelos import (  # noqa: E402
    VALID_COMPLETO,
    PapelUsuario,
    Usuario,
    Amostra,
    Evento,
    Limites,
    Sessao,
    TipoEvento,
    Veiculo,
)
from telemetria.repositorios import amostras as repo_amostras  # noqa: E402
from telemetria.repositorios import catalogo as repo_catalogo  # noqa: E402
from telemetria.repositorios import clientes as repo_clientes  # noqa: E402
from telemetria.repositorios import usuarios as repo_usuarios  # noqa: E402
from telemetria.repositorios import limites as repo_limites  # noqa: E402
from telemetria.repositorios import sessoes as repo_sessoes  # noqa: E402
from telemetria.repositorios import veiculos as repo_veiculos  # noqa: E402
from telemetria.servicos.detector import DetectorEventos  # noqa: E402
from telemetria.servicos import autenticacao  # noqa: E402

# ------------------------------------------------------------ as notas

# O que um mecanico escreve numa sessao. Uma tem varias linhas, para a
# tela e o PDF mostrarem que a quebra de linha fica.
NOTAS = [
    "Troca de velas antes da sessão.",
    "Cliente reclamou de falha em alta; rodei para reproduzir.",
    "Depois da troca do sensor de temperatura.",
    "Pista molhada, poucas arrancadas.",
    "Revisão dos 10 mil:\n- óleo e filtro\n- filtro de ar\n- correia conferida",
    "Bateria nova instalada na véspera.",
]

# ------------------------------------------------------------ os veiculos

# `temperamento` e o que diferencia as series: cada um exercita um canto
# diferente das telas. `sessoes` e desigual de proposito - a tela de
# veiculos precisa ter carro cheio de historico e carro quase vazio para a
# ordenacao por "ultima sessao" e o filtro "nunca usado" dizerem algo.
PERFIS = [
    {
        "veiculo": dict(marca="BMW", modelo="325i", ano_modelo=1995, ano_fabricacao=1995,
                        placa="ABC1234", motor="M50B25", quilometragem=248_500,
                        combustivel="GASOLINA", cambio="MANUAL",
                        perfil_ecu="SIEMENS_MS41_DS2"),
        "cliente": "Leonardo Caloni",
        "sessoes": 22,
        "temperamento": "pista",
        "limites": dict(shift_light_rpm=5800, rpm_alto=6500, temp_alta_c=103,
                        vbat_baixa=11.8, rpm_marcha_lenta=1000, ect_operacao_c=85),
        # Este carro teve os limites MUDADOS no meio do historico: sessao
        # com mais de 90 dias leva o snapshot antigo. Sem isso as sessoes
        # de um mesmo carro teriam todas os mesmos limites e a regra de
        # "limites divergentes" da comparacao nunca apareceria - comparar
        # exige o mesmo veiculo, entao a divergencia so pode vir do tempo.
        "limites_antes": dict(shift_light_rpm=6200, rpm_alto=6800, temp_alta_c=105,
                              vbat_baixa=11.8, rpm_marcha_lenta=1100, ect_operacao_c=80),
        "dias_do_ajuste": 90,
    },
    {
        "veiculo": dict(marca="BMW", modelo="320i", ano_modelo=1997, ano_fabricacao=1996,
                        placa="DEF5678", motor="M52B20", quilometragem=312_000,
                        combustivel="GASOLINA", cambio="AUTOMATICO",
                        perfil_ecu="SIEMENS_MS41_DS2"),
        "cliente": "Oficina Zampieri",
        "sessoes": 14,
        "temperamento": "passeio",
        "limites": None,          # fica com os sugeridos
    },
    {
        "veiculo": dict(marca="Volkswagen", modelo="Gol GTi 2.0", ano_modelo=1994,
                        ano_fabricacao=1994, placa="GHI9012", motor="AP2000 16v",
                        quilometragem=189_300, combustivel="GASOLINA", cambio="MANUAL"),
        "cliente": "Marcos Pereira",
        "sessoes": 11,
        "temperamento": "bateria-fraca",
        "limites": dict(shift_light_rpm=6000, rpm_alto=6600, temp_alta_c=100,
                        vbat_baixa=12.2, rpm_marcha_lenta=1100, ect_operacao_c=90),
    },
    {
        "veiculo": dict(marca="Fiat", modelo="Uno Turbo 1.4 i.e. 2p", ano_modelo=1996,
                        ano_fabricacao=1996, placa="JKL3E56", motor="1.4 Turbo",
                        quilometragem=97_800, combustivel="GASOLINA", cambio="MANUAL"),
        "cliente": "Preparadora Baixada",
        "sessoes": 9,
        "temperamento": "superaquece",
        "limites": dict(shift_light_rpm=6400, rpm_alto=7000, temp_alta_c=98,
                        vbat_baixa=11.5, rpm_marcha_lenta=1200, ect_operacao_c=80),
    },
    # Sem placa: exercita o nome de arquivo em kebab-case e a tela que
    # mostra "sem placa".
    {
        # Modelo CUSTOMIZADO: a FIPE so tem "Opala Diplomata/Diplom.
        # SLE/SE 4.1/2.5", e o dono escreveu do jeito dele. Exercita o
        # "Nao encontrei meu modelo" e a marca do customizado nas telas.
        "veiculo": dict(marca="Chevrolet", modelo="Opala Diplomata 4.1", ano_modelo=1988,
                        ano_fabricacao=1988, placa=None, motor="250-S",
                        quilometragem=421_000, combustivel="ETANOL", cambio="AUTOMATICO"),
        "modelo_customizado": True,
        "cliente": "Antonio Nogueira",
        "sessoes": 2,
        "temperamento": "passeio",
        "limites": dict(shift_light_rpm=4800, rpm_alto=5200, temp_alta_c=100,
                        vbat_baixa=11.8, rpm_marcha_lenta=800, ect_operacao_c=85),
    },
    # Arquivado: tem de sair das listas mas manter o historico acessivel.
    {
        # Sem quilometragem cadastrada (NULL, "não informado") - e por isso
        # as sessoes dele tambem nao tem km.
        "veiculo": dict(marca="Ford", modelo="Escort XR3 2.0i", ano_modelo=1993,
                        ano_fabricacao=1993, placa="MNO7890", motor="2.0i",
                        quilometragem=None, combustivel="GASOLINA", cambio="MANUAL"),
        "cliente": "Cliente antigo",
        "sessoes": 4,
        "temperamento": "passeio",
        "limites": None,
        "arquivar": True,
    },
]

# As duas contas da seed. A senha e a mesma e esta aqui em texto de
# proposito: e banco de mentira, e o ponto e poder entrar sem procurar.
SENHA_DA_SEED = "telemetria123"

CONTAS = [
    {
        "nome": "Oficina Zampieri",
        "email": "profissional@exemplo.com",
        "papel": PapelUsuario.PROFISSIONAL,
        # Fica com os quatro primeiros carros, cada um de um cliente
        # diferente - e o que da a tela de Clientes algo para mostrar.
        "perfis": (0, 4),
    },
    {
        "nome": "Leonardo Caloni",
        "email": "particular@exemplo.com",
        "papel": PapelUsuario.PARTICULAR,
        # Os dois ultimos, no cliente implicito: a conta PARTICULAR nao ve
        # a palavra "cliente" em lugar nenhum.
        "perfis": (4, 6),
    },
]

DIAS_DE_HISTORICO = 180
HZ = 1.0


# -------------------------------------------------------------- a simulacao


def _fases(duracao_s: int, temperamento: str) -> list[tuple[str, int]]:
    """A receita da sessao: (fase, segundos), somando a duracao.

    Sempre comeca em marcha lenta - o motor e ligado parado, e e isso que
    da tempo de marcha lenta e o inicio do aquecimento.
    """
    restante = duracao_s
    fases: list[tuple[str, int]] = []

    lenta = min(restante, random.randint(35, 100))
    fases.append(("lenta", lenta))
    restante -= lenta

    # Na pista as arrancadas sao mais longas e frequentes; no passeio
    # predomina cruzeiro.
    pesos = {
        "pista": [("acelera", 4), ("cruzeiro", 3), ("freia", 3), ("lenta", 1)],
        "passeio": [("acelera", 2), ("cruzeiro", 5), ("freia", 2), ("lenta", 2)],
        "bateria-fraca": [("acelera", 3), ("cruzeiro", 4), ("freia", 2), ("lenta", 2)],
        "superaquece": [("acelera", 3), ("cruzeiro", 4), ("freia", 2), ("lenta", 2)],
    }[temperamento]
    nomes = [n for n, p in pesos for _ in range(p)]

    while restante > 0:
        fase = random.choice(nomes)
        limite = {"acelera": (8, 22), "cruzeiro": (25, 120), "freia": (6, 16), "lenta": (15, 60)}[fase]
        duracao = min(restante, random.randint(*limite))
        fases.append((fase, duracao))
        restante -= duracao
    return fases


def _serie(perfil: dict, duracao_s: int, inicio: datetime) -> list[dict]:
    """Uma sessao inteira de leituras plausiveis, a 1 Hz.

    Devolve dicionarios; quem monta a Amostra e quem grava. `valid` sai
    completo aqui - as falhas sao aplicadas depois, em rajada.
    """
    temperamento = perfil["temperamento"]
    lim = perfil["limites_da_serie"]
    alvo_ect = lim["ect_operacao_c"]
    lenta = lim["rpm_marcha_lenta"]

    # Motor frio: a agua parte da temperatura ambiente e sobe. Sessao
    # sorteada como "ja quente" comeca perto do alvo - e o que faz
    # `ja_estava_quente` aparecer em parte das sessoes.
    ambiente = random.uniform(18, 33)
    ja_quente = random.random() < 0.35
    # Ja quente comeca ACIMA do alvo, nunca um grau abaixo: partir de 84
    # com alvo 85 daria um 'aquecimento' de 14 s, que nao descreve nada.
    ect = alvo_ect + random.uniform(0.5, 3.0) if ja_quente else ambiente

    # Quem superaquece passa do limite quando roda muito; o teto da agua
    # fica acima do temp_alta_c para o evento TEMP_ALTA nascer de verdade.
    teto_ect = lim["temp_alta_c"] + random.uniform(2, 7) if temperamento == "superaquece" else alvo_ect + 4

    # Alguns carros nao chegam a 100 km/h na sessao: o 0-100 tem de ficar
    # em None as vezes, senao a metrica nunca mostra o travessao.
    vss_maximo = random.choice([65, 80, 95, 118, 135, 145]) if temperamento != "pista" else random.choice([110, 135, 160])

    rpm = lenta * random.uniform(0.75, 0.95)
    vss = 0.0
    tps = 0.0
    # Bateria fraca: alternador cansado, tensao base baixa e queda funda
    # sob carga - e assim que BATERIA_BAIXA aparece sem ser forjado.
    vbat_base = random.uniform(11.9, 12.4) if temperamento == "bateria-fraca" else random.uniform(13.7, 14.1)

    linhas: list[dict] = []
    t = 0
    for fase, segundos in _fases(duracao_s, temperamento):
        for _ in range(segundos):
            if fase == "lenta":
                rpm += (lenta * 0.82 - rpm) * 0.35 + random.uniform(-25, 25)
                vss += (0 - vss) * 0.6
                tps += (random.uniform(0, 3) - tps) * 0.4
            elif fase == "acelera":
                alvo_rpm = min(lim["rpm_alto"] * random.uniform(0.92, 1.03), 7000)
                rpm += (alvo_rpm - rpm) * random.uniform(0.10, 0.22) + random.uniform(-40, 40)
                vss += (vss_maximo - vss) * random.uniform(0.07, 0.16)
                tps += (random.uniform(75, 100) - tps) * 0.45
            elif fase == "cruzeiro":
                alvo_vss = vss_maximo * random.uniform(0.45, 0.85)
                vss += (alvo_vss - vss) * 0.08
                # Cruzeiro: o giro acompanha a velocidade, sem tabela de
                # relacoes - so uma proporcao plausivel mais ruido.
                rpm += (900 + vss * 26 - rpm) * 0.25 + random.uniform(-45, 45)
                tps += (random.uniform(12, 32) - tps) * 0.3
            else:  # freia
                vss += (0 - vss) * random.uniform(0.12, 0.28)
                rpm += (max(lenta * 0.9, 800 + vss * 22) - rpm) * 0.3 + random.uniform(-40, 40)
                tps += (0 - tps) * 0.5

            rpm = max(lenta * 0.6, min(7000.0, rpm))
            vss = max(0.0, min(float(vss_maximo) + 5, vss))
            tps = max(0.0, min(100.0, tps))

            # A agua sobe enquanto esta abaixo do teto; depois oscila em
            # torno dele. Carga alta esquenta um pouco mais rapido.
            if ect < teto_ect:
                ect += (teto_ect - ect) * (0.006 + tps / 12000) + random.uniform(-0.12, 0.2)
            else:
                ect += (teto_ect - ect) * 0.05 + random.uniform(-0.35, 0.35)

            # VANOS: fechado em marcha lenta, abre com o giro.
            vanos = 8.0 if rpm < 1500 else min(96.0, 8 + (rpm - 1500) / 52.0)
            vanos += random.uniform(-1.5, 1.5)

            # Tensao cede sob carga e recupera em cruzeiro leve.
            carga = tps / 100.0
            vbat = vbat_base - carga * random.uniform(0.35, 0.8) - (0.25 if rpm < lenta else 0.0)
            vbat += random.uniform(-0.05, 0.05)

            iat = ambiente + 6 * math.sin(t / 240.0) + carga * 4 + random.uniform(-0.8, 0.8)

            linhas.append(
                {
                    "t_ms": int(t * 1000 / HZ),
                    "recebida_em": inicio + timedelta(seconds=t / HZ),
                    "rpm": int(rpm),
                    "ect": int(round(ect)),
                    "iat": int(round(iat)),
                    "vbat": round(max(9.5, vbat), 2),
                    "tps": round(tps, 1),
                    "vanos": round(max(0.0, vanos), 1),
                    "vss": int(vss),
                    "valid": VALID_COMPLETO,
                }
            )
            t += 1
    return linhas


def _apagar_bits(linhas: list[dict], fracao: float) -> int:
    """Apaga bits de `valid` em RAJADAS, nao um a um.

    Em rajada porque e assim que o link K-line falha de verdade: a central
    para de responder um campo por alguns ciclos. E rajada de 5 ou mais e o
    que faz nascer LEITURA_INCOMPLETA, que o detector so registra depois de
    cinco ciclos seguidos incompletos - por isso a maioria das rajadas e
    curta: com todas longas, LEITURA_INCOMPLETA afogaria os outros tipos
    na tela de Relatorios.
    """
    from telemetria.modelos import BITS_VALID

    alvo = int(len(linhas) * fracao)
    atingidas = 0
    while atingidas < alvo and len(linhas) > 12:
        tamanho = random.choice([2, 2, 3, 3, 3, 4, 4, 5, 6, 7])
        comeco = random.randrange(0, max(1, len(linhas) - tamanho))
        # Um ou dois campos por rajada; mais que isso derrubaria a
        # integridade de todos os campos ao mesmo tempo.
        campos = random.sample(list(BITS_VALID), random.choice([1, 1, 2]))
        for i in range(comeco, min(comeco + tamanho, len(linhas))):
            for campo in campos:
                linhas[i]["valid"] &= ~BITS_VALID[campo]
        atingidas += tamanho
    return sum(1 for linha in linhas if linha["valid"] != VALID_COMPLETO)


# ----------------------------------------------------------- as guardas


def _conferir_esquema() -> None:
    """A base de seed precisa existir e estar migrada.

    Antes o script criava as tabelas sozinho; agora quem cria esquema e o
    Alembic, e a base de seed e migrada como qualquer outra. Erro claro
    aqui vale mais que um `UndefinedTable` no meio da geracao.
    """
    from sqlalchemy import inspect

    try:
        tabelas = set(inspect(engine).get_table_names())
    except Exception as erro:
        sys.exit(
            f"[semear] nao consegui falar com {ALVO}\n"
            f"         {erro}\n"
            "         O Postgres esta no ar? (docker compose up -d postgres)"
        )
    faltando = {"veiculo", "sessao", "amostra", "evento", "marca", "modelo"} - tabelas
    if faltando:
        sys.exit(
            f"[semear] a base de seed nao esta migrada (faltam: {', '.join(sorted(faltando))}).\n"
            "         Crie e migre antes:\n"
            f'           createdb -h localhost -U telemetria {BASE_SEED}\n'
            f'           DATABASE_URL="{ALVO}" alembic upgrade head'
        )


def _conferir_vazio(recriar: bool) -> None:
    """Recusa semear por cima de dado que ja esta la.

    Com `--recriar`, esvazia as tabelas em vez de apagar arquivo - nao ha
    mais arquivo para apagar.

    **O catalogo fica.** Por isso nao e mais um `TRUNCATE ... CASCADE` de
    tudo: `modelo` aponta para `usuario` (o customizado tem dono), e o
    cascade a partir de `usuario` esvaziaria a tabela `modelo` inteira -
    as 7 mil linhas da FIPE junto com os customizados, e o banco ficaria
    sem catalogo ate alguem rodar `--carregar-catalogo`. Entao: TRUNCATE
    so na arvore da sessao (que nada de fora referencia), DELETE na ordem
    das FKs do resto, e o customizado sai pelo dono, como na exclusao de
    conta.
    """
    from sqlalchemy import text

    with engine.begin() as con:
        quantos = con.execute(text("SELECT count(*) FROM veiculo")).scalar_one()
        if quantos and not recriar:
            sys.exit(
                f"[semear] a base {BASE_SEED} ja tem {quantos} veiculo(s).\n"
                "         Rode com --recriar para esvaziar e refazer."
            )
        if recriar:
            con.execute(text("TRUNCATE amostra, evento, sessao RESTART IDENTITY"))
            for comando in (
                "DELETE FROM veiculo",
                "DELETE FROM modelo WHERE usuario_id IS NOT NULL",
                "DELETE FROM cliente",
                "DELETE FROM tokenacesso",
                "DELETE FROM usuario",
            ):
                con.execute(text(comando))
            # Os ids recomecam, como o RESTART IDENTITY fazia: a mesma
            # semente tem de dar o mesmo banco. A sequencia de `modelo` nao:
            # o catalogo continua la.
            for tabela in ("veiculo", "cliente", "tokenacesso", "usuario"):
                con.execute(text(f"ALTER SEQUENCE {tabela}_id_seq RESTART"))
            if quantos:
                print(f"[semear] base esvaziada ({quantos} veiculo(s) removidos)")


# ---------------------------------------------------------- o catalogo


def _modelo_do_catalogo(marca: str, modelo: str, usuario_id: int, perfil: dict) -> int:
    """O id do modelo, pelo catalogo de verdade - carregado pela migration.

    Do catalogo, o modelo TEM de existir: se a FIPE renomear a versao, a
    seed quebra aqui e e corrigida, em vez de criar em silencio um
    customizado que pareceria escolha do dono. Customizado so quando o
    perfil pede (`modelo_customizado`), e entra pelo mesmo caminho do
    "Nao encontrei meu modelo".
    """
    if perfil.get("modelo_customizado"):
        marca_obj = repo_catalogo.marca_por_nome(marca)
        if marca_obj is None:
            sys.exit(f"[semear] marca '{marca}' fora do catalogo - a base esta migrada?")
        criado, _ = repo_catalogo.achar_ou_criar_customizado(marca_obj.id, modelo, usuario_id)
        return criado.id
    achado = repo_catalogo.modelo_por_nomes(marca, modelo, None)
    if achado is None:
        sys.exit(f"[semear] '{marca} {modelo}' nao esta no catalogo - a base esta migrada?")
    return achado.id


# ---------------------------------------------------------- gravar a sessao


def _recuar_datas(sessao_id: int, inicio: datetime, fim: datetime) -> None:
    """Poe a sessao no passado.

    A UNICA coisa aqui que nao passa por um repositorio: nenhum deles
    expoe "grave com data de tres meses atras", e `encerrar()` carimba
    agora() de proposito. Acrescentar um parametro de data ao repositorio
    seria codigo do app existindo para servir um script de
    desenvolvimento, entao o ajuste fica deste lado.

    As amostras nao entram aqui: o `recebida_em` delas ja nasceu recuado, e
    por isso os eventos do detector - que herdam a hora da amostra - saem
    com a data certa pelo caminho normal. So os dois eventos de rotina,
    criados por criar() e encerrar(), precisam de conserto.
    """
    with sessao_db() as db:
        sessao = db.get(Sessao, sessao_id)
        # Com fuso: as colunas sao TIMESTAMP WITH TIME ZONE. Antes o fuso
        # era removido porque o SQLite nao tinha o tipo e guardava UTC
        # ingenuo - agora tirar o fuso e que estragaria a data.
        sessao.iniciada_em = inicio.astimezone(timezone.utc)
        sessao.encerrada_em = fim.astimezone(timezone.utc)
        db.add(sessao)

        from sqlmodel import select

        for evento in db.exec(select(Evento).where(Evento.sessao_id == sessao_id)):
            if evento.tipo == TipoEvento.INICIO_SESSAO:
                evento.criado_em = sessao.iniciada_em
                db.add(evento)
            elif evento.tipo == TipoEvento.FIM_SESSAO:
                evento.criado_em = sessao.encerrada_em
                db.add(evento)
        db.commit()


def _gravar_sessao(
    perfil: dict,
    veiculo_id: int,
    inicio: datetime,
    duracao_s: int,
    limites_da_epoca: dict | None = None,
    km: int | None = None,
    observacao: str | None = None,
) -> int:
    """Uma sessao completa, pelo mesmo caminho que o Gravador faz.

    `limites_da_epoca` reproduz um carro cujos limites mudaram depois: a
    serie, o detector e o snapshot usam os valores daquela data, e nao os de
    hoje. Devolve quantas amostras gravou.
    """
    perfil["limites_da_serie"] = limites_da_epoca or perfil["limites_efetivos"]
    linhas = _serie(perfil, duracao_s, inicio)
    # A taxa de falha varia por sessao: link bom num dia, ruim no outro.
    # Com a taxa fixa toda sessao ficaria na mesma integridade, e o filtro
    # por "integridade minima" nao separaria nada na tela de Sessoes.
    _apagar_bits(linhas, fracao=random.choice([0.004, 0.01, 0.02, 0.04, 0.08, 0.08, 0.12, 0.18]))

    # Os limites vao para a Sessao como snapshot, exatamente como a rota
    # de iniciar faz com o que a tela escolheu. Nao ha limite do carro: a
    # sessao e a unica fonte, e a seed so decide QUAIS valores escolher -
    # os do perfil hoje, ou os da epoca para as sessoes antigas.
    # Gravador faz ao iniciar - e o que a tela de analise le depois.
    limites = limites_da_epoca or perfil["limites_efetivos"]
    sessao = repo_sessoes.criar(
        veiculo_id, observacao, snapshot=repo_limites.para_snapshot(limites), km=km
    )

    amostras = [Amostra(sessao_id=sessao.id, **linha) for linha in linhas]

    # O detector roda ANTES de gravar: o commit do gravar_lote desanexa os
    # objetos da Session, e ler `a.valid` num objeto desanexado estoura
    # DetachedInstanceError. No app isso nao acontece porque o Gravador
    # avalia cada amostra assim que ela chega, antes de ir para o buffer -
    # aqui a ordem so reproduz a mesma coisa em lote.
    detector = DetectorEventos(limites=Limites.de(limites))
    eventos: list[Evento] = []
    for amostra in amostras:
        eventos.extend(detector.avaliar(amostra))

    for i in range(0, len(amostras), 500):
        repo_amostras.gravar_lote(amostras[i : i + 500])
    # Nenhum evento e escrito a mao: o que nao nascer da serie nao existe.
    repo_sessoes.registrar_eventos(eventos)

    # Mesma chamada do Gravador ao encerrar: agregados na mesma transacao.
    repo_sessoes.encerrar(sessao.id, repo_amostras.agregados(sessao.id))
    _recuar_datas(sessao.id, inicio, inicio + timedelta(seconds=len(linhas) / HZ))
    return len(amostras)


# ------------------------------------------------------------------- main


def main() -> None:
    p = argparse.ArgumentParser(
        description="Enche um banco de mentira para ver as telas com meses de uso."
    )
    p.add_argument("--recriar", action="store_true",
                   help="apaga o banco de seed antes de gerar")
    p.add_argument("--semente", type=int, default=20260917,
                   help="semente do random; a mesma semente da o mesmo banco")
    args = p.parse_args()

    random.seed(args.semente)
    _conferir_esquema()
    _conferir_vazio(args.recriar)
    print(f"[semear] banco: {ALVO}")

    agora = datetime.now(timezone.utc)
    total_sessoes = 0
    total_amostras = 0

    # As contas primeiro: sem dono nao ha cliente, e sem cliente nao ha
    # carro - a cadeia veiculo -> cliente -> usuario vale tambem aqui.
    donos = {}
    for conta in CONTAS:
        usuario = repo_usuarios.criar(
            Usuario(
                nome=conta["nome"],
                email=conta["email"],
                senha_hash=autenticacao.cifrar_senha(SENHA_DA_SEED),
                papel=conta["papel"],
            )
        )
        donos[conta["email"]] = usuario
        print(f"[semear] conta {usuario.email} ({usuario.papel.value})")
        for indice in range(*conta["perfis"]):
            PERFIS[indice]["usuario"] = usuario

    for perfil in PERFIS:
        usuario = perfil["usuario"]
        if usuario.papel == PapelUsuario.PARTICULAR:
            # A conta PARTICULAR nao tem clientes: tudo vai para o
            # implicito, que e ela mesma.
            cliente = repo_clientes.implicito_de(usuario.id, usuario.nome)
        else:
            cliente = repo_clientes.criar(usuario.id, perfil["cliente"])
        campos = dict(perfil["veiculo"])
        marca, modelo = campos.pop("marca"), campos.pop("modelo")
        veiculo = repo_veiculos.criar(
            # Os dois campos de dono, concordando - o mesmo invariante
            # que `rotas/veiculos.py` garante no app.
            Veiculo(
                usuario_id=usuario.id,
                cliente_id=cliente.id,
                modelo_id=_modelo_do_catalogo(marca, modelo, usuario.id, perfil),
                **campos,
            )
        )
        # Os limites que este carro "escolhe" ao iniciar cada sessao: os do
        # perfil, ou os sugeridos - o mesmo que a opcao "Sugeridos" do Ao
        # vivo manda.
        perfil["limites_efetivos"] = perfil["limites"] or repo_limites.sugeridos()

        etiqueta = perfil["veiculo"]["placa"] or veiculo.descricao()
        # Espalhadas nos ultimos 6 meses, em hora plausivel de oficina - e
        # gravadas EM ORDEM de data. A ordem importa por causa do km: o
        # `encerrar()` leva o km da sessao ao carro quando ela e a mais
        # recente, e na hora do encerramento a sessao ainda esta com a data
        # de agora (o recuo vem depois). Gravando da mais antiga para a mais
        # nova, o carro termina com o km da ultima, como na vida real.
        inicios = []
        for _ in range(perfil["sessoes"]):
            inicio = agora - timedelta(
                days=random.uniform(0.5, DIAS_DE_HISTORICO),
                hours=random.uniform(-4, 4),
            )
            inicios.append(
                inicio.replace(minute=random.randrange(60), second=random.randrange(60))
            )
        inicios.sort()
        km_por_dia = random.uniform(15, 60)
        km_final = perfil["veiculo"]["quilometragem"]

        for inicio in inicios:
            duracao = random.randint(2 * 60, 40 * 60)
            # O km do painel no dia: cresce com o tempo ate o km atual do
            # carro na ultima sessao. Carro sem quilometragem cadastrada nao
            # tem km nenhum; e uma em cada cinco sessoes fica sem km, como
            # quem esqueceu de olhar o painel.
            km = None
            if km_final is not None and random.random() > 0.2:
                dias_antes = (inicios[-1] - inicio).total_seconds() / 86400
                km = max(0, round(km_final - dias_antes * km_por_dia))
            if inicio == inicios[-1] and km_final is not None:
                km = km_final
            observacao = random.choice(NOTAS) if random.random() < 0.35 else None
            # Sessao anterior ao ajuste leva os limites da epoca.
            idade_dias = (agora - inicio).total_seconds() / 86400
            da_epoca = (
                perfil["limites_antes"]
                if perfil.get("limites_antes") and idade_dias > perfil["dias_do_ajuste"]
                else None
            )
            total_amostras += _gravar_sessao(
                perfil, veiculo.id, inicio, duracao, da_epoca, km, observacao
            )
            total_sessoes += 1

        if perfil.get("arquivar"):
            repo_veiculos.arquivar(veiculo.id, usuario.id)
            etiqueta += " (arquivado)"
        print(f"[semear]   {etiqueta}: {perfil['sessoes']} sessao(oes)")

    from collections import Counter

    from sqlmodel import select

    with sessao_db() as db:
        tipos = Counter(e.tipo.value for e in db.exec(select(Evento)))

    print()
    print(
        f"[semear] {len(CONTAS)} contas, {len(PERFIS)} veiculos, "
        f"{total_sessoes} sessoes, {total_amostras} amostras"
    )
    print(f"[semear] senha das duas contas: {SENHA_DA_SEED}")
    print("[semear] eventos por tipo:")
    for tipo, quantos in sorted(tipos.items(), key=lambda par: -par[1]):
        print(f"[semear]   {tipo}: {quantos}")
    # PERDA_CONEXAO nao aparece de proposito: quem o cria e o Gravador,
    # quando o link BLE cai, e nao o DetectorEventos. Forja-lo aqui seria
    # inventar evento na mao.
    print()
    print("[semear] para subir o app com este banco:")
    if os.name == "nt":
        print(f"[semear]   set DATABASE_URL={ALVO}")
        print("[semear]   .venv\\Scripts\\python.exe executar.py --sim")
    else:
        print(f'[semear]   DATABASE_URL="{ALVO}" python executar.py --sim')


if __name__ == "__main__":
    main()
