"""
Peca compartilhada pelas tabelas. Fora de enums.py por nao ser enum, e
fora do __init__ porque os modelos importam daqui (seria circular).
"""

from datetime import datetime, timezone


def agora() -> datetime:
    """O instante presente, sempre em UTC.

    Toda data gravada passa por aqui, entao o banco so tem UTC. Quem
    exibe converte; quem compara nao precisa saber de fuso.
    """
    return datetime.now(timezone.utc)
