"""
Leitura e gravacao dos limites do detector (tela de Ajustes). Unica rota
que ainda fala com o banco pela dependencia `obter_db`.
"""

from fastapi import APIRouter, Depends
from sqlmodel import Session

from ..contexto import obter_db
from ..modelos import Limites

router = APIRouter(prefix="/api/limites", tags=["limites"])


@router.get("")
def ler(db: Session = Depends(obter_db)):
    """Os limites em vigor. Devolve os padroes se ninguem gravou ainda."""
    return db.get(Limites, 1) or Limites()


@router.put("")
def gravar(novos: Limites, db: Session = Depends(obter_db)):
    """Grava os limites.

    Nao afeta a gravacao em curso: o detector recebeu uma copia no inicio
    da sessao, de proposito.
    """
    atual = db.get(Limites, 1)
    if atual is None:
        atual = Limites(id=1)
    for campo in ("shift_light_rpm", "rpm_alto", "temp_alta_c", "vbat_baixa"):
        setattr(atual, campo, getattr(novos, campo))
    db.add(atual)
    db.commit()
    db.refresh(atual)
    return atual
