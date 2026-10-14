"""
Os seis limites que o detector usa para decidir o que vira evento, e que
as metricas usam como referencia do motor.

**Os limites sao da SESSAO, e so dela.** Nao ha limite global nem limite
do carro: quem inicia a gravacao escolhe os seis valores (os da ultima
sessao do carro, os sugeridos ou personalizados), e eles ficam gravados
nas colunas `limite_*` da `Sessao`, sem edicao depois. O que mora aqui e a
lista dos campos, os valores SUGERIDOS e o objeto que o detector recebe.
"""

from dataclasses import dataclass

# Os seis campos, na ordem em que a tela os mostra. Serve a quem precisa
# percorrer os limites sem repetir a lista: rota, repositorio e o
# snapshot da sessao.
CAMPOS_LIMITE = (
    "shift_light_rpm",
    "rpm_alto",
    "temp_alta_c",
    "vbat_baixa",
    "rpm_marcha_lenta",
    "ect_operacao_c",
)

# Ponto de partida, nao padrao: ninguem herda daqui. Sao os numeros do M50
# do E36, o carro do TCC. Entram em dois lugares - na opcao "Sugeridos" ao
# iniciar uma sessao (`GET /api/veiculos/{id}/inicio-sessao` e
# `GET /api/limites/sugeridos`), e como fallback de sessao antiga sem
# snapshot.
#
# Mudar um valor aqui NAO mexe em sessao gravada: o snapshot e o que
# valeu, e e de proposito - limite de alerta mudando sozinho debaixo de
# uma gravacao seria reescrever por que um evento disparou.
LIMITES_SUGERIDOS = {
    "shift_light_rpm": 6200,
    "rpm_alto": 6800,
    "temp_alta_c": 105,
    "vbat_baixa": 11.8,
    "rpm_marcha_lenta": 1100,
    "ect_operacao_c": 80,
}


@dataclass(frozen=True)
class Limites:
    """Os seis limites de UMA gravacao, como o detector os le.

    Nao e tabela: o lugar deles no banco sao as colunas `limite_*` da
    Sessao. Imutavel porque a sessao nao muda de limite depois de iniciada.
    """

    shift_light_rpm: int
    rpm_alto: int
    temp_alta_c: int
    vbat_baixa: float
    rpm_marcha_lenta: int
    ect_operacao_c: int

    @classmethod
    def de(cls, valores: dict) -> "Limites":
        """Dos seis campos de um dicionario; o resto e ignorado."""
        return cls(**{campo: valores[campo] for campo in CAMPOS_LIMITE})
