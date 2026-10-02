"""
Os seis limites que o detector usa para decidir o que vira evento, e que
as metricas usam como referencia do motor.

Nao existe limite global: **cada carro tem os seis valores, sempre
preenchidos**, em `limites_veiculo.py`. O que mora aqui e a lista dos
campos e os valores SUGERIDOS - o ponto de partida de um carro novo e o
que a tela oferece no botao "Usar valores sugeridos".
"""

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
# do E36, o carro do TCC. Entram em tres lugares - ao cadastrar um carro,
# como fallback de sessao antiga sem snapshot, e em
# `GET /api/limites/sugeridos`, que alimenta o botao da tela.
#
# Mudar um valor aqui NAO mexe em carro ja cadastrado: quem quiser o
# numero novo aperta "Usar valores sugeridos" e salva. E de proposito -
# limite de alerta mudando sozinho debaixo de uma gravacao gravada seria
# o mesmo problema que o snapshot da sessao existe para evitar.
LIMITES_SUGERIDOS = {
    "shift_light_rpm": 6200,
    "rpm_alto": 6800,
    "temp_alta_c": 105,
    "vbat_baixa": 11.8,
    "rpm_marcha_lenta": 1100,
    "ect_operacao_c": 80,
}

