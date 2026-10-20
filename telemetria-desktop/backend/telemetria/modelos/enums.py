"""
Os nomes fixos do dominio e a leitura do bitmask do firmware. BITS_VALID
tem de espelhar o firmware - mexe aqui quem acrescentar campo ou evento.
"""

from enum import Enum


class StatusSessao(str, Enum):
    """Se a sessao ainda esta gravando ou ja foi fechada."""

    ATIVA = "ATIVA"
    ENCERRADA = "ENCERRADA"


class TipoEvento(str, Enum):
    """O que o detector sabe registrar.

    INICIO_SESSAO e FIM_SESSAO sao rotina e existem em toda gravacao; so
    os outros contam como evento nas telas.
    """

    INICIO_SESSAO = "INICIO_SESSAO"
    FIM_SESSAO = "FIM_SESSAO"
    SHIFT_LIGHT = "SHIFT_LIGHT"
    RPM_ALTO = "RPM_ALTO"
    TEMP_ALTA = "TEMP_ALTA"
    BATERIA_BAIXA = "BATERIA_BAIXA"
    PERDA_CONEXAO = "PERDA_CONEXAO"
    LEITURA_INCOMPLETA = "LEITURA_INCOMPLETA"


class PapelUsuario(str, Enum):
    """Como a conta usa o app.

    E **preferencia de interface, nao fronteira de seguranca**: as duas
    veem so os proprios dados, e o papel decide o que a tela mostra. Quem
    separa conta de conta e o dono do registro, nao o papel.
    """

    PROFISSIONAL = "PROFISSIONAL"   # atende carros de clientes
    PARTICULAR = "PARTICULAR"       # cuida do proprio carro


class Combustivel(str, Enum):
    """O combustivel do carro. So cadastro e exibicao."""

    GASOLINA = "GASOLINA"
    ETANOL = "ETANOL"
    FLEX = "FLEX"
    DIESEL = "DIESEL"
    GNV = "GNV"
    HIBRIDO = "HIBRIDO"


class Cambio(str, Enum):
    """O cambio do carro. So cadastro e exibicao - nao ha tabela de
    relacoes, entao a marcha continua fora (ver "Limitacoes conhecidas")."""

    MANUAL = "MANUAL"
    AUTOMATICO = "AUTOMATICO"
    AUTOMATIZADO = "AUTOMATIZADO"
    CVT = "CVT"


class PerfilEcu(str, Enum):
    """Que central o carro tem. O protocolo e consequencia do perfil, nao
    um campo separado.

    A fonte de dados continua decidida na linha de comando (`--sim` ou BLE
    no `E36-DS2`), e o unico hardware que o projeto le e a Siemens MS41 por
    DS2. Com o BLE, carro de outro perfil nao grava - a regra e
    `servicos/leitor.compatibilidade_do_perfil()`.
    """

    OBD2_GENERICO = "OBD2_GENERICO"
    SIEMENS_MS41_DS2 = "SIEMENS_MS41_DS2"


class EstadoLeitor(str, Enum):
    """Em que pe esta a ligacao com o adaptador BLE."""

    DESLIGADO = "DESLIGADO"
    PROCURANDO = "PROCURANDO"
    CONECTADO = "CONECTADO"
    ERRO = "ERRO"


# Bitmask publicado pelo firmware no campo "valid": o bit e a posicao do
# parametro na tabela kParams do firmware.
#
# Estes sete sao o NUCLEO - os que o firmware le desde o inicio. Sao eles
# que decidem se a leitura esta completa, a integridade e o detector.
BITS_VALID: dict[str, int] = {
    "ect": 0x01,
    "rpm": 0x02,
    "tps": 0x04,
    "vanos": 0x08,
    "vbat": 0x10,
    "iat": 0x20,
    "vss": 0x40,
}
VALID_COMPLETO = 0x7F

# Os parametros que o firmware da MS41 passou a ler depois (bits 7 a 17).
# Sao leitura a mais, nao entram em `completa()`: firmware antigo nao manda
# nenhum deles, e isso nao e leitura incompleta.
BITS_EXTRAS: dict[str, int] = {
    "load": 1 << 7,
    "maf": 1 << 8,
    "mafv": 1 << 9,
    "knock": 1 << 10,
    "ign": 1 << 11,
    "inj": 1 << 12,
    "iacv": 1 << 13,
    "lint1": 1 << 14,
    "lint2": 1 << 15,
    "lam1": 1 << 16,
    "lam2": 1 << 17,
}
CAMPOS_EXTRAS = tuple(BITS_EXTRAS)

# Todos os parametros, nucleo e extras: e o que diz se UM campo respondeu.
BITS_PARAMETROS: dict[str, int] = {**BITS_VALID, **BITS_EXTRAS}


def campos_invalidos(valid: int) -> list[str]:
    """Os campos do nucleo que a central NAO respondeu naquela leitura.

    O firmware repete o numero anterior quando falha, entao sem esta lista
    o dado velho passaria por medicao nova.
    """
    return [nome for nome, bit in BITS_VALID.items() if not valid & bit]


def campos_sem_resposta(valid: int) -> list[str]:
    """Como `campos_invalidos`, mas de todos os parametros, extras inclusos.

    E o que a tela ao vivo usa para apagar cada card. Nao serve para
    integridade: com firmware antigo, todo extra sai daqui.
    """
    return [nome for nome, bit in BITS_PARAMETROS.items() if not valid & bit]
