"""
Os limites que o detector usa para decidir o que vira evento. Uma linha
so na tabela, editavel na tela de Ajustes.
"""

from typing import Optional

from sqlmodel import Field, SQLModel


class Limites(SQLModel, table=True):
    id: Optional[int] = Field(default=1, primary_key=True)
    shift_light_rpm: int = 6200
    rpm_alto: int = 6800
    temp_alta_c: int = 105
    vbat_baixa: float = 11.8
