"""
Metricas da serie de uma sessao: desempenho, motor, saude e qualidade.
Funcao pura, nao toca no banco. Toda metrica ignora amostra com `valid`
apagado, e sem leitura devolve None - nunca zero.

Toda metrica aqui e CALCULO DIRETO sobre o que o firmware mediu. Nada de
heuristica nem suposicao sobre o carro: o que nao sai da medicao nao entra
neste modulo (ver "Limitacoes conhecidas" no CLAUDE.md).

Os limiares que dependem do motor - marcha lenta, temperatura de operacao,
shift light, giro alto, temperatura alta, tensao baixa - vem dos limites da
sessao, nao de constante. O cadastro aceita qualquer carro.
"""

from __future__ import annotations

import statistics
from typing import Iterable, Optional

from ..modelos import BITS_VALID, CAMPOS_LIMITE, LIMITES_SUGERIDOS, Amostra

# Acima disto o intervalo nao e atribuido a ninguem: a 1 Hz nominal, tres
# segundos ja sao dois ciclos perdidos.
DT_MAXIMO_S = 3.0

# Faixas de rpm do histograma e da atuacao do VANOS. O topo aberto e None.
FAIXAS_RPM = ((0, 2000), (2000, 4000), (4000, 6000), (6000, None))

RPM_MOTOR_RODANDO = 400      # abaixo disto o motor esta parado, nao em marcha lenta
TPS_ABERTO = 90.0            # "pe no fundo"
TPS_SEM_CARGA = 10.0
TPS_COM_CARGA = 50.0
VSS_ARRANCADA = 100          # km/h do 0-100
VSS_RETOMADA = (80, 120)     # a janela de retomada, em km/h

# Giro a partir do qual exigir do motor frio castiga: nao e limite de
# alerta (isso e o shift light), e o ponto onde o desgaste comeca a
# importar com o oleo ainda grosso. Constante porque nao depende do
# preparo do carro - depende do oleo.
RPM_ESFORCO_FRIO = 3000


def _limites_efetivos(limites: Optional[dict]) -> dict:
    """Os seis limites como dict, com os SUGERIDOS no que faltar.

    Aceita o dicionario que `repositorios/limites.efetivos_da_sessao()`
    devolve (que traz `do_snapshot` junto - ignorado aqui). O fallback
    existe so para quem chama sem limites; no app as tres chamadas passam
    os da sessao.
    """
    valores = dict(LIMITES_SUGERIDOS)
    for campo in CAMPOS_LIMITE:
        vindo = (limites or {}).get(campo)
        if vindo is not None:
            valores[campo] = vindo
    return valores


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


def _motor_rodando(a: Amostra) -> bool:
    """Motor girando. Exige rpm valido em quem chama."""
    return a.rpm > RPM_MOTOR_RODANDO


# ------------------------------------------------------------- desempenho


def _desempenho(amostras: list[Amostra], lim: dict) -> dict:
    """Distancia, aceleracao, velocidade e as janelas de arrancada.

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

    # Media do percurso inteiro, parado incluso. Atencao: a distancia sai
    # das amostras com vss valido e o tempo das amostras com rpm valido -
    # sao coberturas diferentes, e num link ruim o quociente fica torto.
    # E o preco da definicao "distancia por tempo de motor ligado"; o
    # numero honesto de comparar entre sessoes e a media em movimento.
    tempo_ligado = _tempo_onde(amostras, _motor_rodando, "rpm")
    media_total = None
    if tempo_com_vss > 0 and tempo_ligado > 0:
        media_total = (metros / 1000.0) / (tempo_ligado / 3600.0)

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
        "velocidade_media_total": _arredonda(media_total, 1),
        "tempo_movimento_s": round(
            _tempo_onde(amostras, lambda a: a.vss > 0, "vss"), 1
        ),
        "zero_a_100_s": _janela_velocidade(amostras, 0, VSS_ARRANCADA),
        "retomada_80_120_s": _janela_velocidade(amostras, *VSS_RETOMADA),
    }


def _janela_velocidade(amostras: list[Amostra], de: int, para: int) -> Optional[float]:
    """Menor tempo entre `de` km/h ou menos e `para` km/h ou mais.

    Nao interpola. Buraco de leitura no meio invalida a janela: nao da
    para afirmar que o carro nao desacelerou num trecho que ninguem leu.

    Serve o 0-100 (de=0, e como vss nunca e negativo `<= 0` e `== 0`) e a
    retomada 80-120. E a mesma regra com outros limiares - duplicar
    significaria corrigir o tratamento do buraco em dois lugares.
    """
    melhor = None
    inicio = None
    for a in amostras:
        if not a.valido("vss"):
            inicio = None          # buraco na leitura: a janela nao vale mais
            continue
        if a.vss <= de:
            inicio = a
            continue
        if inicio is None:
            continue
        if a.vss >= para:
            dt = (a.t_ms - inicio.t_ms) / 1000.0
            if dt > 0 and (melhor is None or dt < melhor):
                melhor = dt
            inicio = None
    return round(melhor, 1) if melhor is not None else None


# ----------------------------------------------------------- uso do motor


def _motor(amostras: list[Amostra], lim: dict) -> dict:
    """Histograma de rpm, pe no fundo, marcha lenta e tempo nas faixas de
    alerta - estas ultimas contra os limites DA SESSAO."""
    histograma = []
    for i, (baixo, alto) in enumerate(FAIXAS_RPM):
        segundos = _tempo_onde(amostras, lambda a, i=i: _faixa_de(a.rpm) == i, "rpm")
        histograma.append(
            {"faixa": _rotulo_faixa(baixo, alto), "de": baixo, "ate": alto, "segundos": round(segundos, 1)}
        )

    return {
        "tempo_por_faixa_rpm": histograma,
        "tempo_motor_ligado_s": round(_tempo_onde(amostras, _motor_rodando, "rpm"), 1),
        "tempo_tps_acima_90_s": round(
            _tempo_onde(amostras, lambda a: a.tps > TPS_ABERTO, "tps"), 1
        ),
        # Marcha lenta = motor girando e carro parado. Nao entra TPS na
        # definicao de proposito: exigir um terceiro campo valido na mesma
        # amostra derrubaria a cobertura sem mudar o que se quer medir.
        "tempo_marcha_lenta_s": round(
            _tempo_onde(
                amostras,
                lambda a: _motor_rodando(a) and a.rpm < lim["rpm_marcha_lenta"] and a.vss == 0,
                "rpm",
                "vss",
            ),
            1,
        ),
        # Os mesmos limiares que o detector usou para criar evento, entao
        # "3 eventos de shift light" e "40 s acima do shift light" falam do
        # mesmo numero. `>=` como no detector.
        "tempo_acima_shift_light_s": round(
            _tempo_onde(amostras, lambda a: a.rpm >= lim["shift_light_rpm"], "rpm"), 1
        ),
        "tempo_acima_rpm_alto_s": round(
            _tempo_onde(amostras, lambda a: a.rpm >= lim["rpm_alto"], "rpm"), 1
        ),
        # Giro alto com o motor ainda frio: exige rpm E ect validos na
        # mesma amostra - sem os dois nao da para afirmar as duas coisas.
        "tempo_giro_alto_motor_frio_s": round(
            _tempo_onde(
                amostras,
                lambda a: a.rpm >= RPM_ESFORCO_FRIO and a.ect < lim["ect_operacao_c"],
                "rpm",
                "ect",
            ),
            1,
        ),
        "tps_medio_movimento": _arredonda(
            _media_ponderada(amostras, lambda a: a.tps, lambda a: a.vss > 0, "tps", "vss"), 1
        ),
    }


# ----------------------------------------------------------------- saude


def _saude(amostras: list[Amostra], lim: dict) -> dict:
    """Aquecimento, estabilidade termica, tensao, ar admitido e VANOS."""
    com_ect = [a for a in amostras if a.valido("ect")]
    alvo = lim["ect_operacao_c"]

    aquecimento = None
    ect_inicial = com_ect[0].ect if com_ect else None
    if com_ect and com_ect[0].ect < alvo:
        for a in com_ect:
            if a.ect >= alvo:
                aquecimento = round((a.t_ms - com_ect[0].t_ms) / 1000.0, 1)
                break

    # Estabilizacao: so o trecho depois de a agua chegar a temperatura de
    # operacao. Com o motor frio a temperatura esta subindo por definicao,
    # e incluir a subida faria o desvio descrever o aquecimento, nao a
    # estabilidade.
    depois = []
    aquecida = False
    for a in com_ect:
        if a.ect >= alvo:
            aquecida = True
        if aquecida:
            depois.append(a.ect)

    sem_carga = _media_ponderada(
        amostras, lambda a: a.vbat, lambda a: _motor_rodando(a) and a.tps <= TPS_SEM_CARGA,
        "vbat", "rpm", "tps",
    )
    com_carga = _media_ponderada(
        amostras, lambda a: a.vbat, lambda a: _motor_rodando(a) and a.tps > TPS_COM_CARGA,
        "vbat", "rpm", "tps",
    )

    iats = [a.iat for a in amostras if a.valido("iat")]

    return {
        "aquecimento_s": aquecimento,
        # O alvo usado vai junto: ele varia por carro, entao o numero sem
        # ele nao diz ate onde a agua subiu.
        "ect_alvo_c": alvo,
        "ect_inicial": ect_inicial,
        # Sem aquecimento medido o motor ja subiu quente; a tela usa isso
        # para explicar o travessao em vez de deixar o campo mudo.
        "ja_estava_quente": bool(com_ect) and com_ect[0].ect >= alvo,
        "ect_estabilizada": round(statistics.fmean(depois), 1) if depois else None,
        "ect_desvio": round(statistics.pstdev(depois), 2) if len(depois) > 1 else None,
        "tempo_temp_alta_s": round(
            _tempo_onde(amostras, lambda a: a.ect >= lim["temp_alta_c"], "ect"), 1
        ),
        "vbat_media_rodando": _arredonda(
            _media_ponderada(amostras, lambda a: a.vbat, _motor_rodando, "vbat", "rpm"), 2
        ),
        "vbat_sem_carga": _arredonda(sem_carga, 2),
        "vbat_com_carga": _arredonda(com_carga, 2),
        # Tensao em marcha lenta: a mesma definicao de marcha lenta do
        # bloco do motor, e nao so "motor ligado e parado" - senao o carro
        # parado a 4000 rpm entraria na media da marcha lenta.
        "vbat_marcha_lenta": _arredonda(
            _media_ponderada(
                amostras,
                lambda a: a.vbat,
                lambda a: _motor_rodando(a) and a.rpm < lim["rpm_marcha_lenta"] and a.vss == 0,
                "vbat",
                "rpm",
                "vss",
            ),
            2,
        ),
        # `<=` como no detector, que dispara BATERIA_BAIXA na descida.
        "tempo_vbat_baixa_rodando_s": round(
            _tempo_onde(
                amostras,
                lambda a: a.vbat <= lim["vbat_baixa"] and _motor_rodando(a),
                "vbat",
                "rpm",
            ),
            1,
        ),
        # Queda sob carga: quanto a tensao cede entre pedal solto e pedal
        # fundo. None quando faltou um dos dois lados - a sessao pode nao
        # ter tido carga nenhuma.
        "queda_sob_carga_v": (
            round(sem_carga - com_carga, 2)
            if sem_carga is not None and com_carga is not None
            else None
        ),
        # Ar admitido. A elevacao e sobre a PRIMEIRA leitura valida, nao
        # sobre a minima: o que interessa e quanto o ar esquentou desde o
        # comeco da gravacao, e a minima poderia cair no meio dela.
        "iat_media": _arredonda(
            _media_ponderada(amostras, lambda a: a.iat, lambda a: True, "iat"), 1
        ),
        "iat_max": max(iats) if iats else None,
        "iat_elevacao": (max(iats) - iats[0]) if iats else None,
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
# Cada uma diz onde buscar o valor ("resumo" ou uma categoria de metricas)
# e, no ultimo campo, de QUAL limite ela depende - None quando nao depende
# de nenhum. Ver comparar() para o que o limite muda.
COMPARAVEIS = (
    ("resumo", "duracao_s", "Duração", "s", 1, None),
    ("resumo", "amostras", "Amostras", "", 0, None),
    ("resumo", "integridade_pct", "Integridade", "%", 1, None),
    ("resumo", "rpm_pico", "RPM máximo", "", 0, None),
    ("resumo", "vss_pico", "Velocidade máxima", "km/h", 0, None),
    ("resumo", "ect_pico", "Temperatura máxima", "°C", 0, None),
    ("resumo", "vbat_min", "Tensão mínima", "V", 2, None),
    ("resumo", "eventos", "Eventos", "", 0, None),
    ("desempenho", "distancia_km", "Distância", "km", 2, None),
    ("desempenho", "zero_a_100_s", "0 a 100 km/h", "s", 1, None),
    ("desempenho", "retomada_80_120_s", "Retomada de 80 a 120 km/h", "s", 1, None),
    ("desempenho", "aceleracao_maxima_ms2", "Aceleração máxima", "m/s²", 2, None),
    ("desempenho", "velocidade_media_movimento", "Velocidade média em movimento", "km/h", 1, None),
    ("desempenho", "velocidade_media_total", "Velocidade média total", "km/h", 1, None),
    ("motor", "tempo_marcha_lenta_s", "Tempo em marcha lenta", "s", 1, "rpm_marcha_lenta"),
    ("motor", "tempo_tps_acima_90_s", "Tempo acima de 90% de borboleta", "s", 1, None),
    ("motor", "tempo_acima_shift_light_s", "Tempo acima do shift light", "s", 1, "shift_light_rpm"),
    ("motor", "tempo_acima_rpm_alto_s", "Tempo acima do giro alto", "s", 1, "rpm_alto"),
    ("motor", "tempo_giro_alto_motor_frio_s", "Giro alto com motor frio", "s", 1, "ect_operacao_c"),
    ("saude", "aquecimento_s", "Tempo de aquecimento", "s", 1, "ect_operacao_c"),
    ("saude", "ect_estabilizada", "Temperatura estabilizada", "°C", 1, "ect_operacao_c"),
    ("saude", "tempo_temp_alta_s", "Tempo com temperatura alta", "s", 1, "temp_alta_c"),
    ("saude", "vbat_media_rodando", "Tensão média rodando", "V", 2, None),
    ("saude", "vbat_marcha_lenta", "Tensão em marcha lenta", "V", 2, "rpm_marcha_lenta"),
    ("saude", "queda_sob_carga_v", "Queda de tensão sob carga", "V", 2, None),
    ("saude", "iat_max", "Temperatura máxima do ar", "°C", 0, None),
    ("qualidade", "taxa_hz", "Taxa de amostragem", "Hz", 2, None),
)


def comparar(lado_a: dict, lado_b: dict) -> list[dict]:
    """Duas sessoes campo a campo, com a diferenca (B menos A) pronta.

    Duas regras decidem quando a diferenca NAO e calculada:

    1. Falta um dos lados - zero ali diria "andaram igual", que e outra
       afirmacao.
    2. A metrica depende de um limite e os limites das duas sessoes sao
       diferentes. Subtrair "40 s acima do shift light" com o shift light
       em 5000 de um lado e 6200 do outro produz um numero que nao mede
       nada: os dois lados responderam perguntas diferentes. A linha
       continua aparecendo com os dois valores, `diferenca` None e o
       limite de cada lado, para a tela poder dizer por que.
    """
    def valor(lado, origem, campo):
        raiz = lado.get("resumo") if origem == "resumo" else (
            lado.get("metricas", {}).get(origem, {})
        )
        return (raiz or {}).get(campo)

    def limite(lado, campo):
        return (lado.get("limites") or {}).get(campo)

    linhas = []
    for origem, campo, rotulo, unidade, casas, dependencia in COMPARAVEIS:
        a = valor(lado_a, origem, campo)
        b = valor(lado_b, origem, campo)
        if a is None and b is None:
            continue          # nenhuma das duas mediu: a linha nao diz nada

        limite_a = limite(lado_a, dependencia) if dependencia else None
        limite_b = limite(lado_b, dependencia) if dependencia else None
        divergem = bool(dependencia) and limite_a != limite_b

        diferenca = None
        if a is not None and b is not None and not divergem:
            diferenca = round(b - a, casas) if casas else b - a

        linha = {
            "campo": campo,
            "grupo": origem,
            "rotulo": rotulo,
            "unidade": unidade,
            "casas": casas,
            "a": a,
            "b": b,
            "diferenca": diferenca,
        }
        if dependencia:
            linha.update(
                {
                    "limite_campo": dependencia,
                    "limite_a": limite_a,
                    "limite_b": limite_b,
                    "limites_diferentes": divergem,
                }
            )
        linhas.append(linha)
    return linhas


def calcular(
    amostras: list[Amostra],
    duracao_s: Optional[float] = None,
    limites: Optional[dict] = None,
) -> dict:
    """Todas as metricas, agrupadas por categoria.

    `limites` sao os da SESSAO (o snapshot gravado nela, ou o padrao atual
    quando ela e antiga demais para ter snapshot) - e o que faz o tempo
    acima do shift light responder pelo mesmo numero que criou os eventos.
    Sem eles, cai no padrao de fabrica.

    Serie vazia devolve a mesma forma com tudo em None, para a tela nao
    precisar de um caminho separado.
    """
    lim = _limites_efetivos(limites)

    if not amostras:
        return {
            "desempenho": {},
            "motor": {},
            "saude": {},
            "qualidade": _qualidade([], duracao_s),
            "cobertura": {"tempo_considerado_s": 0.0, "tempo_da_serie_s": 0.0, "tempo_descartado_s": 0.0},
            "limites": lim,
        }

    return {
        "desempenho": _desempenho(amostras, lim),
        "motor": _motor(amostras, lim),
        "saude": _saude(amostras, lim),
        "qualidade": _qualidade(amostras, duracao_s),
        "cobertura": _cobertura(amostras),
        # Os limites que estas metricas usaram, junto do resultado: sem
        # eles a tela nao tem como escrever "acima de 5000 rpm".
        "limites": lim,
    }
