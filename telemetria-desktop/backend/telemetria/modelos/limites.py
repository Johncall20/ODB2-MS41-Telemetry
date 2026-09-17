"""
Os seis limites que o detector usa para decidir o que vira evento, e que
as metricas usam como referencia do motor.

Nao existe limite global: **cada carro tem os seis valores, sempre
preenchidos**, em `limites_veiculo.py`. O que mora aqui e a lista dos
campos e os valores SUGERIDOS - o ponto de partida de um carro novo e o
que a tela oferece no botao "Usar valores sugeridos".
"""

from typing import Optional

from sqlmodel import Field, SQLModel

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


class Limites(SQLModel, table=True):
    """VESTIGIAL. Era o limite global, de onde os carros herdavam.

    Ninguem le nem escreve esta tabela: os limites sao por veiculo. A
    classe continua declarada porque o `banco.py` so sabe ACRESCENTAR
    coluna e tabela, nunca remover - tirando-a daqui, um banco novo
    deixaria de ter a tabela enquanto todo banco migrado continuaria com
    ela, e o esquema dos dois divergiria. A linha gravada fica onde esta,
    sem ser consultada.
    """

    id: Optional[int] = Field(default=1, primary_key=True)
    shift_light_rpm: int = 6200
    rpm_alto: int = 6800
    temp_alta_c: int = 105
    vbat_baixa: float = 11.8
    rpm_marcha_lenta: int = 1100
    ect_operacao_c: int = 80
