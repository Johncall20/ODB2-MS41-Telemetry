#!/usr/bin/env python3
"""
Enche um banco de MENTIRA para ver as telas com meses de uso.

    python semear.py            # cria ~/.telemetria-ds2/seed.db
    python semear.py --recriar   # apaga o seed.db e refaz

Escreve num banco SEPARADO e recusa mexer no `dados.db`, mesmo que a
TELEMETRIA_DB aponte para ele - perder gravacao de verdade por causa de um
script de desenvolvimento nao e um risco que vale correr.

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
from pathlib import Path

PADRAO_SEED = Path.home() / ".telemetria-ds2" / "seed.db"

# Definido antes de importar telemetria.banco: e na importacao que ele le a
# TELEMETRIA_DB e monta a engine.
if not os.environ.get("TELEMETRIA_DB"):
    os.environ["TELEMETRIA_DB"] = str(PADRAO_SEED)

ALVO = Path(os.environ["TELEMETRIA_DB"])


def _conferir_alvo(recriar: bool) -> None:
    """Recusa escrever onde nao deve. Roda ANTES de abrir o banco."""
    if ALVO.name == "dados.db":
        sys.exit(
            f"[semear] recusando escrever em {ALVO}\n"
            "         'dados.db' e o banco de uso real. Aponte a TELEMETRIA_DB\n"
            "         para outro arquivo, ou nao defina a variavel para usar\n"
            f"         o padrao ({PADRAO_SEED})."
        )
    if ALVO.exists():
        if not recriar:
            sys.exit(
                f"[semear] {ALVO} ja existe.\n"
                "         Rode com --recriar para apagar e refazer, ou apague\n"
                f"         a mao:  rm \"{ALVO}\""
            )
        ALVO.unlink()
        print(f"[semear] {ALVO.name} apagado (--recriar)")


_conferir_alvo("--recriar" in sys.argv)

from telemetria.banco import criar_tabelas, sessao_db  # noqa: E402
from telemetria.modelos import (  # noqa: E402
    VALID_COMPLETO,
    Amostra,
    Evento,
    LimitesVeiculo,
    Sessao,
    TipoEvento,
    Veiculo,
)
from telemetria.repositorios import amostras as repo_amostras  # noqa: E402
from telemetria.repositorios import limites as repo_limites  # noqa: E402
from telemetria.repositorios import sessoes as repo_sessoes  # noqa: E402
from telemetria.repositorios import veiculos as repo_veiculos  # noqa: E402
from telemetria.servicos.detector import DetectorEventos  # noqa: E402

# ------------------------------------------------------------ os veiculos

# `temperamento` e o que diferencia as series: cada um exercita um canto
# diferente das telas. `sessoes` e desigual de proposito - a tela de
# veiculos precisa ter carro cheio de historico e carro quase vazio para a
# ordenacao por "ultima sessao" e o filtro "nunca usado" dizerem algo.
PERFIS = [
    {
        "veiculo": dict(marca="BMW", modelo="325i", ano=1995, placa="ABC1234",
                        motor="M50B25", cliente="Leonardo Caloni", quilometragem=248_500),
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
        "veiculo": dict(marca="BMW", modelo="320i", ano=1997, placa="DEF5678",
                        motor="M52B20", cliente="Oficina Zampieri", quilometragem=312_000),
        "sessoes": 14,
        "temperamento": "passeio",
        "limites": None,          # fica com os sugeridos
    },
    {
        "veiculo": dict(marca="Volkswagen", modelo="Gol GTI", ano=1994, placa="GHI9012",
                        motor="AP2000 16v", cliente="Marcos Pereira", quilometragem=189_300),
        "sessoes": 11,
        "temperamento": "bateria-fraca",
        "limites": dict(shift_light_rpm=6000, rpm_alto=6600, temp_alta_c=100,
                        vbat_baixa=12.2, rpm_marcha_lenta=1100, ect_operacao_c=90),
    },
    {
        "veiculo": dict(marca="Fiat", modelo="Uno Turbo", ano=1996, placa="JKL3456",
                        motor="1.4 Turbo", cliente="Preparadora Baixada", quilometragem=97_800),
        "sessoes": 9,
        "temperamento": "superaquece",
        "limites": dict(shift_light_rpm=6400, rpm_alto=7000, temp_alta_c=98,
                        vbat_baixa=11.5, rpm_marcha_lenta=1200, ect_operacao_c=80),
    },
    # Sem placa: exercita o nome de arquivo em kebab-case e a tela que
    # mostra "sem placa".
    {
        "veiculo": dict(marca="Chevrolet", modelo="Opala Diplomata", ano=1988, placa="",
                        motor="250-S", cliente="Antonio Nogueira", quilometragem=421_000),
        "sessoes": 2,
        "temperamento": "passeio",
        "limites": dict(shift_light_rpm=4800, rpm_alto=5200, temp_alta_c=100,
                        vbat_baixa=11.8, rpm_marcha_lenta=800, ect_operacao_c=85),
    },
    # Arquivado: tem de sair das listas mas manter o historico acessivel.
    {
        "veiculo": dict(marca="Ford", modelo="Escort XR3", ano=1992, placa="MNO7890",
                        motor="1.8i", cliente="Cliente antigo", quilometragem=203_400),
        "sessoes": 4,
        "temperamento": "passeio",
        "limites": None,
        "arquivar": True,
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
        sessao.iniciada_em = inicio.astimezone(timezone.utc).replace(tzinfo=None)
        sessao.encerrada_em = fim.astimezone(timezone.utc).replace(tzinfo=None)
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

    # Os limites vao para a Sessao como snapshot, exatamente como o
    # Gravador faz ao iniciar - e o que a tela de analise le depois.
    if limites_da_epoca is None:
        limites = repo_limites.efetivos_do_veiculo(veiculo_id)
    else:
        limites = LimitesVeiculo(veiculo_id=veiculo_id, **limites_da_epoca)
    sessao = repo_sessoes.criar(veiculo_id, snapshot=repo_limites.para_snapshot(limites))

    amostras = [Amostra(sessao_id=sessao.id, **linha) for linha in linhas]

    # O detector roda ANTES de gravar: o commit do gravar_lote desanexa os
    # objetos da Session, e ler `a.valid` num objeto desanexado estoura
    # DetachedInstanceError. No app isso nao acontece porque o Gravador
    # avalia cada amostra assim que ela chega, antes de ir para o buffer -
    # aqui a ordem so reproduz a mesma coisa em lote.
    detector = DetectorEventos(limites=limites)
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
    criar_tabelas()
    print(f"[semear] banco: {ALVO}")

    agora = datetime.now(timezone.utc)
    total_sessoes = 0
    total_amostras = 0

    for perfil in PERFIS:
        veiculo = repo_veiculos.criar(Veiculo(**perfil["veiculo"]))
        if perfil["limites"] is not None:
            repo_limites.gravar_do_veiculo(veiculo.id, perfil["limites"])
        perfil["limites_efetivos"] = repo_limites.do_veiculo(veiculo.id)

        etiqueta = perfil["veiculo"]["placa"] or f"{perfil['veiculo']['marca']} {perfil['veiculo']['modelo']}"
        for _ in range(perfil["sessoes"]):
            # Espalhadas nos ultimos 6 meses, em hora plausivel de oficina.
            inicio = agora - timedelta(
                days=random.uniform(0.5, DIAS_DE_HISTORICO),
                hours=random.uniform(-4, 4),
            )
            inicio = inicio.replace(minute=random.randrange(60), second=random.randrange(60))
            duracao = random.randint(2 * 60, 40 * 60)
            # Sessao anterior ao ajuste leva os limites da epoca.
            idade_dias = (agora - inicio).total_seconds() / 86400
            da_epoca = (
                perfil["limites_antes"]
                if perfil.get("limites_antes") and idade_dias > perfil["dias_do_ajuste"]
                else None
            )
            total_amostras += _gravar_sessao(
                perfil, veiculo.id, inicio, duracao, da_epoca
            )
            total_sessoes += 1

        if perfil.get("arquivar"):
            repo_veiculos.arquivar(veiculo.id)
            etiqueta += " (arquivado)"
        print(f"[semear]   {etiqueta}: {perfil['sessoes']} sessao(oes)")

    from collections import Counter

    from sqlmodel import select

    with sessao_db() as db:
        tipos = Counter(e.tipo.value for e in db.exec(select(Evento)))

    print()
    print(f"[semear] {len(PERFIS)} veiculos, {total_sessoes} sessoes, {total_amostras} amostras")
    print("[semear] eventos por tipo:")
    for tipo, quantos in sorted(tipos.items(), key=lambda par: -par[1]):
        print(f"[semear]   {tipo}: {quantos}")
    # PERDA_CONEXAO nao aparece de proposito: quem o cria e o Gravador,
    # quando o link BLE cai, e nao o DetectorEventos. Forja-lo aqui seria
    # inventar evento na mao.
    print()
    print("[semear] para subir o app com este banco:")
    if os.name == "nt":
        print(f'[semear]   set TELEMETRIA_DB={ALVO}')
        print("[semear]   .venv\\Scripts\\python.exe executar.py --sim")
    else:
        print(f'[semear]   TELEMETRIA_DB="{ALVO}" python executar.py --sim')


if __name__ == "__main__":
    main()
