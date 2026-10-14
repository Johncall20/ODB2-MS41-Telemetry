"""
Como o texto vindo do usuario e guardado. Um lugar so, para cadastro,
edicao e perfil nao terem cada um a sua regra - duas regras sairiam do ar
uma da outra.

Funcoes puras, sem Pydantic nem banco: o modelo usa `normalizar_placa`, e
`rotas/esquemas.py` embrulha o resto nos tipos de entrada.
"""

import re
from typing import Optional

# Padrao antigo (ABC1234) e Mercosul (ABC1D23) numa expressao so: a quinta
# posicao e a unica que muda, digito no antigo e letra ou digito no
# Mercosul. Vale DEPOIS de normalizar. A migration 0008 tem a mesma
# expressao como literal, no CHECK - congelada, de proposito.
PLACA_VALIDA = re.compile(r"^[A-Z]{3}[0-9][A-Z0-9][0-9]{2}$")

# Piso do ano do carro. O teto e o ano corrente, e por isso fica so no
# backend: CHECK com data atual mudaria de significado sozinho.
ANO_MINIMO = 1950


def texto_curto(bruto: Optional[str]) -> str:
    """Sem espaco nas pontas e sem espaco repetido no meio.

    "  Joao   Silva " vira "Joao Silva". Tab e quebra de linha contam como
    espaco: campo curto nao tem linha.
    """
    return " ".join((bruto or "").split())


def texto_opcional(bruto: Optional[str]) -> Optional[str]:
    """Como `texto_curto`, mas vazio vira None.

    Campo opcional nao preenchido e NULL no banco, nunca string vazia - sao
    duas formas de dizer a mesma coisa, e o indice unico da placa tratava
    a segunda como um valor igual entre carros diferentes.
    """
    return texto_curto(bruto) or None


def texto_longo(bruto: Optional[str]) -> Optional[str]:
    """Texto de varias linhas (as notas da sessao): sem espaco nas pontas,
    quebras de linha PRESERVADAS, vazio vira None.

    Ao contrario do `texto_curto`, nao colapsa espaco no meio: numa nota,
    a quebra de linha e o recuo sao do texto. So unifica o fim de linha do
    Windows (`\\r\\n`) para `\\n`, senao a mesma nota teria dois tamanhos.
    """
    texto = (bruto or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    return texto or None


def normalizar_email(bruto: str) -> str:
    """Minusculo e sem espaco nas pontas.

    Sem isto, "Leo@x.com" e "leo@x.com" viram duas contas e a pessoa nao
    entende por que o login falha. O banco confere o mesmo com um CHECK.
    """
    return (bruto or "").strip().lower()


def normalizar_placa(bruta: Optional[str]) -> str:
    """Placa como ela e guardada: maiuscula e sem separador.

    "abc-1234", "ABC 1234" e "abc.1234" tem de dar a mesma linha. O hifen
    volta so na exibicao. Nao valida: quem confere o formato e a entrada.
    """
    return "".join(c for c in (bruta or "").upper() if c.isalnum())
