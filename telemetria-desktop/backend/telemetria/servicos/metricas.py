"""
Metricas da serie de uma sessao: desempenho, motor, saude e qualidade.
Funcao pura, nao toca no banco. Toda metrica ignora amostra com `valid`
apagado, e sem leitura devolve None - nunca zero.
"""

from __future__ import annotations

import statistics
from typing import Iterable, Optional

from ..modelos import BITS_VALID, Amostra

# Acima disto o intervalo nao e atribuido a ninguem: a 1 Hz nominal, tres
# segundos ja sao dois ciclos perdidos.
DT_MAXIMO_S = 3.0

# Faixas de rpm do histograma e da atuacao do VANOS. O topo aberto e None.
FAIXAS_RPM = ((0, 2000), (2000, 4000), (4000, 6000), (6000, None))

RPM_MOTOR_RODANDO = 400      # abaixo disto o motor esta parado, nao em marcha lenta
RPM_MARCHA_LENTA = 1100      # teto de marcha lenta num M50 quente
TPS_ABERTO = 90.0            # "pe no fundo"
TPS_SEM_CARGA = 10.0
TPS_COM_CARGA = 50.0
ECT_AQUECIDO = 80.0          # alvo do termostato do E36
VSS_ARRANCADA = 100          # km/h do 0-100

# Marcha estimada: a razao vss/rpm e praticamente constante dentro de uma
# marcha engatada. Amostra com giro ou velocidade baixa demais fica fora -
# embreagem pisada e saida do ponto dao razao que nao descreve marcha
# nenhuma.
RPM_MIN_MARCHA = 900
VSS_MIN_MARCHA = 5
TOLERANCIA_MARCHA = 0.08       # +-8% em torno da media do trecho
DURACAO_MINIMA_MARCHA_S = 3.0  # engate que nao se sustenta e troca, nao marcha
# Para PROVAR que existe uma marcha, a razao tem de se manter enquanto o
# giro anda de verdade. Trecho quase parado tem razao estavel por acidente:
# duas grandezas que mal se mexem sempre parecem proporcionais.
VARIACAO_MINIMA_RPM = 400
# Duas marchas vizinhas de um cambio de producao nunca ficam a menos de
# ~20% uma da outra (num E36 o salto e de 25% a 70%). Candidatas mais
# proximas que isso sao a mesma marcha vista duas vezes, com o ruido do
# arredondamento de vss no meio - nao duas marchas.
SEPARACAO_MINIMA_MARCHA = 0.20
MAXIMO_MARCHAS = 7             # cambio manual nao passa disso; mais que isso
                               # quer dizer que a serie nao tem cara de cambio


def _dt(atual: Amostra, seguinte: Amostra) -> Optional[float]:
    """Segundos entre duas amostras; None se o intervalo nao serve.

    Nao-positivo e a volta do millis do ESP32; longo demais e ciclo
    perdido, e atribuir esses segundos inventaria dado.
    """
    delta = (seguinte.t_ms - atual.t_ms) / 1000.0
    if delta <= 0 or delta > DT_MAXIMO_S:
        return None
    return delta


def _intervalos(amostras: list[Amostra]) -> Iterable[tuple[Amostra, float]]:
    """(amostra, dt) por amostra. O intervalo pertence a quem o abre."""
    for atual, seguinte in zip(amostras, amostras[1:]):
        delta = _dt(atual, seguinte)
        if delta is not None:
            yield atual, delta


def _tempo_onde(amostras, condicao, *campos) -> float:
    """Segundos em que a condicao vale, exigindo `campos` validos."""
    total = 0.0
    for a, dt in _intervalos(amostras):
        if all(a.valido(c) for c in campos) and condicao(a):
            total += dt
    return total


def _media_ponderada(amostras, valor, condicao, *campos) -> Optional[float]:
    """Media de `valor` ponderada pelo tempo, so onde a condicao vale."""
    soma = 0.0
    tempo = 0.0
    for a, dt in _intervalos(amostras):
        if all(a.valido(c) for c in campos) and condicao(a):
            soma += valor(a) * dt
            tempo += dt
    return soma / tempo if tempo > 0 else None


def _faixa_de(rpm: float) -> Optional[int]:
    for i, (baixo, alto) in enumerate(FAIXAS_RPM):
        if rpm >= baixo and (alto is None or rpm < alto):
            return i
    return None


def _rotulo_faixa(baixo, alto) -> str:
    return f"{baixo}-{alto}" if alto is not None else f"acima de {baixo}"


# ------------------------------------------------------------- desempenho


def _desempenho(amostras: list[Amostra]) -> dict:
    """Distancia, aceleracao, velocidade em movimento e o 0-100.

    A aceleracao exige vss valido em DUAS amostras vizinhas - sem as duas
    nao ha delta. A ~1 Hz a resolucao e grossa.
    """
    metros = 0.0
    tempo_com_vss = 0.0
    aceleracoes = []

    for atual, seguinte in zip(amostras, amostras[1:]):
        dt = _dt(atual, seguinte)
        if dt is None or not atual.valido("vss"):
            continue
        metros += (atual.vss / 3.6) * dt
        tempo_com_vss += dt
        if seguinte.valido("vss"):
            a = ((seguinte.vss - atual.vss) / 3.6) / dt
            if a > 0:
                aceleracoes.append(a)

    return {
        "distancia_km": round(metros / 1000, 3) if tempo_com_vss > 0 else None,
        # So as aceleracoes positivas entram na media: misturar frenagem
        # puxaria o numero para perto de zero e ele deixaria de descrever
        # como o carro anda.
        "aceleracao_maxima_ms2": round(max(aceleracoes), 2) if aceleracoes else None,
        "aceleracao_media_ms2": (
            round(statistics.fmean(aceleracoes), 2) if aceleracoes else None
        ),
        "velocidade_media_movimento": _arredonda(
            _media_ponderada(amostras, lambda a: a.vss, lambda a: a.vss > 0, "vss"), 1
        ),
        "tempo_movimento_s": round(
            _tempo_onde(amostras, lambda a: a.vss > 0, "vss"), 1
        ),
        "zero_a_100_s": _zero_a_cem(amostras),
    }


def _zero_a_cem(amostras: list[Amostra]) -> Optional[float]:
    """Menor tempo entre parado e 100 km/h, ou None.

    Nao interpola. Buraco de leitura no meio invalida a arrancada: nao da
    para afirmar que o carro nao parou num trecho que ninguem leu.
    """
    melhor = None
    inicio = None
    for a in amostras:
        if not a.valido("vss"):
            inicio = None          # buraco na leitura: a janela nao vale mais
            continue
        if a.vss == 0:
            inicio = a
            continue
        if inicio is None:
            continue
        if a.vss >= VSS_ARRANCADA:
            dt = (a.t_ms - inicio.t_ms) / 1000.0
            if dt > 0 and (melhor is None or dt < melhor):
                melhor = dt
            inicio = None
    return round(melhor, 1) if melhor is not None else None


# ----------------------------------------------------------- uso do motor


def _motor(amostras: list[Amostra]) -> dict:
    """Histograma de rpm, pe no fundo, marcha lenta e marcha estimada."""
    histograma = []
    for i, (baixo, alto) in enumerate(FAIXAS_RPM):
        segundos = _tempo_onde(amostras, lambda a, i=i: _faixa_de(a.rpm) == i, "rpm")
        histograma.append(
            {"faixa": _rotulo_faixa(baixo, alto), "de": baixo, "ate": alto, "segundos": round(segundos, 1)}
        )

    return {
        "tempo_por_faixa_rpm": histograma,
        "tempo_tps_acima_90_s": round(
            _tempo_onde(amostras, lambda a: a.tps > TPS_ABERTO, "tps"), 1
        ),
        # Marcha lenta = motor girando e carro parado. Nao entra TPS na
        # definicao de proposito: exigir um terceiro campo valido na mesma
        # amostra derrubaria a cobertura sem mudar o que se quer medir.
        "tempo_marcha_lenta_s": round(
            _tempo_onde(
                amostras,
                lambda a: RPM_MOTOR_RODANDO < a.rpm < RPM_MARCHA_LENTA and a.vss == 0,
                "rpm",
                "vss",
            ),
            1,
        ),
        **_marchas(amostras),
    }


def _trechos_de_marcha(amostras: list[Amostra]) -> list[list[tuple[float, float]]]:
    """Trechos CONSECUTIVOS com razao vss/rpm estavel.

    Estavel no TEMPO, nao no conjunto: fatiar todas as razoes por
    proximidade acharia marcha ate sem cambio nenhum.
    """
    trechos: list[list[tuple[float, float]]] = []
    atual: list[tuple[float, float]] = []

    for i, a in enumerate(amostras):
        seguinte = amostras[i + 1] if i + 1 < len(amostras) else None
        dt = _dt(a, seguinte) if seguinte is not None else None
        serve = (
            dt is not None
            and a.valido("rpm")
            and a.valido("vss")
            and a.rpm >= RPM_MIN_MARCHA
            and a.vss >= VSS_MIN_MARCHA
        )
        if not serve:
            if atual:
                trechos.append(atual)
                atual = []
            continue

        razao = a.vss / a.rpm * 1000.0
        if atual:
            media = sum(r for r, _, _ in atual) / len(atual)
            if abs(razao - media) > media * TOLERANCIA_MARCHA:
                trechos.append(atual)
                atual = []
        atual.append((razao, dt, a.rpm))

    if atual:
        trechos.append(atual)
    return trechos


def _marchas(amostras: list[Amostra]) -> dict:
    """Marcha ESTIMADA pela razao vss/rpm, sem tabela de relacoes.

    LIMITE: sem cambio na serie (o simulador) ainda saem uma ou duas
    marchas falsas. Primeira metrica a conferir no hardware real.
    """
    vazio = {"marchas": [], "trocas_de_marcha": None}

    trechos = [
        t for t in _trechos_de_marcha(amostras)
        if sum(dt for _, dt, _ in t) >= DURACAO_MINIMA_MARCHA_S
    ]
    if not trechos:
        return vazio

    medias = [sum(r for r, _, _ in t) / len(t) for t in trechos]
    percurso = [max(g for _, _, g in t) - min(g for _, _, g in t) for t in trechos]

    # So os trechos em que o giro percorreu uma faixa larga definem as
    # marchas. Cruzeiro a giro constante nao prova proporcionalidade
    # nenhuma - mas depois e encaixado numa das marchas ja descobertas,
    # entao o tempo dele nao se perde.
    sementes = [i for i in range(len(trechos)) if percurso[i] >= VARIACAO_MINIMA_RPM]
    if not sementes:
        return vazio

    sementes.sort(key=lambda i: medias[i])
    grupos: list[list[int]] = [[sementes[0]]]
    for indice in sementes[1:]:
        referencia = sum(medias[i] for i in grupos[-1]) / len(grupos[-1])
        # Separacao de cambio, e nao a tolerancia do trecho: o que decide
        # se sao DUAS marchas e a distancia entre relacoes reais.
        if abs(medias[indice] - referencia) <= referencia * SEPARACAO_MINIMA_MARCHA:
            grupos[-1].append(indice)
        else:
            grupos.append([indice])

    if len(grupos) > MAXIMO_MARCHAS:
        # Mais "marchas" que qualquer cambio manual: o que a serie mostra
        # nao e troca de marcha, e nao ha o que estimar.
        return vazio

    razoes = [sum(medias[i] for i in g) / len(g) for g in grupos]

    # Encaixa TODO trecho estavel na marcha mais proxima, semente ou nao.
    # Trecho que nao cai perto de nenhuma fica de fora - e o que sobra de
    # embreagem no meio do caminho.
    marcha_do_trecho = {}
    for indice in range(len(trechos)):
        melhor, distancia = None, None
        for numero, razao in enumerate(razoes, start=1):
            desvio = abs(medias[indice] - razao) / razao
            if desvio <= SEPARACAO_MINIMA_MARCHA / 2 and (
                distancia is None or desvio < distancia
            ):
                melhor, distancia = numero, desvio
        if melhor is not None:
            marcha_do_trecho[indice] = melhor

    marchas = [
        {
            "marcha": numero,
            "razao_kmh_por_1000rpm": round(razoes[numero - 1], 1),
            "segundos": round(
                sum(
                    dt
                    for indice, atribuida in marcha_do_trecho.items()
                    if atribuida == numero
                    for _, dt, _ in trechos[indice]
                ),
                1,
            ),
        }
        for numero in range(1, len(razoes) + 1)
    ]

    # Trocas: mudancas de marcha entre trechos vizinhos NA ORDEM DO TEMPO.
    # Dois trechos seguidos da mesma marcha - separados por um buraco de
    # leitura, por exemplo - nao contam como troca.
    trocas = 0
    anterior = None
    for indice in range(len(trechos)):
        atual = marcha_do_trecho.get(indice)
        if atual is None:
            continue
        if anterior is not None and atual != anterior:
            trocas += 1
        anterior = atual

    return {"marchas": marchas, "trocas_de_marcha": trocas}


# ----------------------------------------------------------------- saude


def _saude(amostras: list[Amostra]) -> dict:
    """Aquecimento, estabilidade termica, tensao e atuacao do VANOS."""
    com_ect = [a for a in amostras if a.valido("ect")]

    aquecimento = None
    ect_inicial = com_ect[0].ect if com_ect else None
    if com_ect and com_ect[0].ect < ECT_AQUECIDO:
        for a in com_ect:
            if a.ect >= ECT_AQUECIDO:
                aquecimento = round((a.t_ms - com_ect[0].t_ms) / 1000.0, 1)
                break

    # Estabilizacao: so o trecho depois de a agua chegar aos 80 graus. Com
    # o motor frio a temperatura esta subindo por definicao, e incluir a
    # subida faria o desvio descrever o aquecimento, nao a estabilidade.
    depois = []
    aquecida = False
    for a in com_ect:
        if a.ect >= ECT_AQUECIDO:
            aquecida = True
        if aquecida:
            depois.append(a.ect)

    rodando = lambda a: a.rpm > RPM_MOTOR_RODANDO  # noqa: E731

    sem_carga = _media_ponderada(
        amostras, lambda a: a.vbat, lambda a: rodando(a) and a.tps <= TPS_SEM_CARGA,
        "vbat", "rpm", "tps",
    )
    com_carga = _media_ponderada(
        amostras, lambda a: a.vbat, lambda a: rodando(a) and a.tps > TPS_COM_CARGA,
        "vbat", "rpm", "tps",
    )

    return {
        "aquecimento_ate_80_s": aquecimento,
        "ect_inicial": ect_inicial,
        # Sem aquecimento medido o motor ja subiu quente; a tela usa isso
        # para explicar o travessao em vez de deixar o campo mudo.
        "ja_estava_quente": bool(com_ect) and com_ect[0].ect >= ECT_AQUECIDO,
        "ect_estabilizada": round(statistics.fmean(depois), 1) if depois else None,
        "ect_desvio": round(statistics.pstdev(depois), 2) if len(depois) > 1 else None,
        "vbat_media_rodando": _arredonda(
            _media_ponderada(amostras, lambda a: a.vbat, rodando, "vbat", "rpm"), 2
        ),
        "vbat_sem_carga": _arredonda(sem_carga, 2),
        "vbat_com_carga": _arredonda(com_carga, 2),
        # Queda sob carga: quanto a tensao cede entre pedal solto e pedal
        # fundo. None quando faltou um dos dois lados - a sessao pode nao
        # ter tido carga nenhuma.
        "queda_sob_carga_v": (
            round(sem_carga - com_carga, 2)
            if sem_carga is not None and com_carga is not None
            else None
        ),
        "vanos_por_faixa_rpm": _vanos_por_faixa(amostras),
    }


def _vanos_por_faixa(amostras: list[Amostra]) -> list[dict]:
    """Minimo, maximo e media do VANOS por faixa de rpm.

    Exige rpm e vanos validos na MESMA amostra.
    """
    baldes = {i: [] for i in range(len(FAIXAS_RPM))}
    for a in amostras:
        if not (a.valido("rpm") and a.valido("vanos")):
            continue
        faixa = _faixa_de(a.rpm)
        if faixa is not None:
            baldes[faixa].append(a.vanos)

    saida = []
    for i, (baixo, alto) in enumerate(FAIXAS_RPM):
        valores = baldes[i]
        saida.append(
            {
                "faixa": _rotulo_faixa(baixo, alto),
                "de": baixo,
                "ate": alto,
                "amostras": len(valores),
                "minimo": round(min(valores), 1) if valores else None,
                "maximo": round(max(valores), 1) if valores else None,
                "media": round(statistics.fmean(valores), 1) if valores else None,
            }
        )
    return saida


# -------------------------------------------------------------- qualidade


def _qualidade(amostras: list[Amostra], duracao_s: Optional[float]) -> dict:
    """Taxa real de amostragem e integridade campo a campo.

    A taxa conta os buracos: e a que a sessao entregou, nao a que teria
    entregado sem falha.
    """
    total = len(amostras)
    span = (amostras[-1].t_ms - amostras[0].t_ms) / 1000.0 if total > 1 else 0.0

    return {
        "amostras": total,
        "taxa_hz": round((total - 1) / span, 2) if span > 0 else None,
        "duracao_s": round(duracao_s, 1) if duracao_s is not None else None,
        "integridade_por_campo": [
            {
                "campo": campo,
                "validas": sum(1 for a in amostras if a.valido(campo)),
                "pct": (
                    round(100 * sum(1 for a in amostras if a.valido(campo)) / total, 1)
                    if total
                    else None
                ),
            }
            for campo in BITS_VALID
        ],
    }


def _cobertura(amostras: list[Amostra]) -> dict:
    """Quanto do tempo da sessao entrou nas contas.

    O descartado fica exposto para explicar o histograma que soma menos
    que a duracao.
    """
    considerado = sum(dt for _, dt in _intervalos(amostras))
    span = (amostras[-1].t_ms - amostras[0].t_ms) / 1000.0 if len(amostras) > 1 else 0.0
    return {
        "tempo_considerado_s": round(considerado, 1),
        "tempo_da_serie_s": round(span, 1),
        "tempo_descartado_s": round(max(span - considerado, 0.0), 1),
    }


def _arredonda(valor: Optional[float], casas: int) -> Optional[float]:
    return round(valor, casas) if valor is not None else None


# Linhas da comparacao entre duas sessoes, na ordem em que a tela mostra.
# Cada uma diz onde buscar o valor: "resumo" ou uma categoria de metricas.
COMPARAVEIS = (
    ("resumo", "duracao_s", "Duração", "s", 1),
    ("resumo", "amostras", "Amostras", "", 0),
    ("resumo", "integridade_pct", "Integridade", "%", 1),
    ("resumo", "rpm_pico", "RPM máximo", "", 0),
    ("resumo", "vss_pico", "Velocidade máxima", "km/h", 0),
    ("resumo", "ect_pico", "Temperatura máxima", "°C", 0),
    ("resumo", "vbat_min", "Tensão mínima", "V", 2),
    ("resumo", "eventos", "Eventos", "", 0),
    ("desempenho", "distancia_km", "Distância", "km", 2),
    ("desempenho", "zero_a_100_s", "0 a 100 km/h", "s", 1),
    ("desempenho", "aceleracao_maxima_ms2", "Aceleração máxima", "m/s²", 2),
    ("desempenho", "velocidade_media_movimento", "Velocidade média", "km/h", 1),
    ("motor", "tempo_marcha_lenta_s", "Tempo em marcha lenta", "s", 1),
    ("motor", "tempo_tps_acima_90_s", "Tempo acima de 90% de borboleta", "s", 1),
    ("motor", "trocas_de_marcha", "Trocas de marcha", "", 0),
    ("saude", "aquecimento_ate_80_s", "Aquecimento até 80 °C", "s", 1),
    ("saude", "ect_estabilizada", "Temperatura estabilizada", "°C", 1),
    ("saude", "vbat_media_rodando", "Tensão média rodando", "V", 2),
    ("saude", "queda_sob_carga_v", "Queda de tensão sob carga", "V", 2),
    ("qualidade", "taxa_hz", "Taxa de amostragem", "Hz", 2),
)


def comparar(lado_a: dict, lado_b: dict) -> list[dict]:
    """Duas sessoes campo a campo, com a diferenca (B menos A) pronta.

    Diferenca None quando falta um dos lados - zero ali diria "andaram
    igual", que e outra afirmacao.
    """
    def valor(lado, origem, campo):
        raiz = lado.get("resumo") if origem == "resumo" else (
            lado.get("metricas", {}).get(origem, {})
        )
        return (raiz or {}).get(campo)

    linhas = []
    for origem, campo, rotulo, unidade, casas in COMPARAVEIS:
        a = valor(lado_a, origem, campo)
        b = valor(lado_b, origem, campo)
        if a is None and b is None:
            continue          # nenhuma das duas mediu: a linha nao diz nada
        diferenca = None
        if a is not None and b is not None:
            diferenca = round(b - a, casas) if casas else b - a
        linhas.append(
            {
                "campo": campo,
                "grupo": origem,
                "rotulo": rotulo,
                "unidade": unidade,
                "casas": casas,
                "a": a,
                "b": b,
                "diferenca": diferenca,
            }
        )
    return linhas


def calcular(amostras: list[Amostra], duracao_s: Optional[float] = None) -> dict:
    """Todas as metricas, agrupadas por categoria.

    Serie vazia devolve a mesma forma com tudo em None, para a tela nao
    precisar de um caminho separado.
    """
    if not amostras:
        return {
            "desempenho": {},
            "motor": {},
            "saude": {},
            "qualidade": _qualidade([], duracao_s),
            "cobertura": {"tempo_considerado_s": 0.0, "tempo_da_serie_s": 0.0, "tempo_descartado_s": 0.0},
        }

    return {
        "desempenho": _desempenho(amostras),
        "motor": _motor(amostras),
        "saude": _saude(amostras),
        "qualidade": _qualidade(amostras, duracao_s),
        "cobertura": _cobertura(amostras),
    }
