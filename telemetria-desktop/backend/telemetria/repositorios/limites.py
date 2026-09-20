"""Os limites de alerta de cada carro.

Nao ha limite global nem heranca: todo veiculo tem uma linha com os seis
valores preenchidos. Por isso aqui nao existe mescla - o que esta gravado
na linha e o que vale.

Mexe aqui quem mudar como um limite chega ao detector ou as metricas.
"""

from typing import Optional

from sqlmodel import select

from ..banco import sessao_db
from ..modelos import CAMPOS_LIMITE, LIMITES_SUGERIDOS, LimitesVeiculo, Sessao


def _solta(linha: LimitesVeiculo) -> LimitesVeiculo:
    """Copia desanexada da linha.

    Solta porque o objeto do ORM morre com a Session, e o detector leva
    esses valores pela sessao inteira.
    """
    return LimitesVeiculo(
        veiculo_id=linha.veiculo_id,
        **{campo: getattr(linha, campo) for campo in CAMPOS_LIMITE},
    )


def como_dict(limites) -> dict:
    """So os seis campos. E o formato que sai pelas rotas."""
    return {campo: getattr(limites, campo) for campo in CAMPOS_LIMITE}


def sugeridos() -> dict:
    """O ponto de partida que a tela oferece. Copia, nao a constante."""
    return dict(LIMITES_SUGERIDOS)


def nova_linha(veiculo_id: int) -> LimitesVeiculo:
    """Linha de limites de um carro novo, com os sugeridos. Nao grava.

    Quem grava e `repositorios/veiculos.criar()`, na mesma transacao do
    veiculo - e o que garante que nao exista carro sem limites nem por um
    instante.
    """
    return LimitesVeiculo(veiculo_id=veiculo_id, **LIMITES_SUGERIDOS)


def _buscar(db, veiculo_id: int) -> Optional[LimitesVeiculo]:
    return db.exec(
        select(LimitesVeiculo).where(LimitesVeiculo.veiculo_id == veiculo_id)
    ).first()


def do_veiculo(veiculo_id: int) -> dict:
    """Os seis limites do carro.

    Carro sem linha nao deveria existir - `repositorios/veiculos.criar()`
    grava uma na mesma transacao, e a migration de dados cobre o resto -,
    mas se aparecer, os sugeridos respondem em vez de estourar: a tela de
    limites e justamente onde isso se conserta.
    """
    with sessao_db() as db:
        linha = _buscar(db, veiculo_id)
        return como_dict(linha) if linha is not None else sugeridos()


def gravar_do_veiculo(veiculo_id: int, valores: dict) -> dict:
    """Grava os seis limites do carro. Cria a linha se ela faltar."""
    with sessao_db() as db:
        linha = _buscar(db, veiculo_id)
        if linha is None:
            linha = LimitesVeiculo(veiculo_id=veiculo_id)
        for campo in CAMPOS_LIMITE:
            setattr(linha, campo, valores[campo])
        db.add(linha)
        db.commit()
        db.refresh(linha)
        return como_dict(linha)


def efetivos_do_veiculo(veiculo_id: int) -> LimitesVeiculo:
    """O que o carro usa - o que o gravador leva para o detector."""
    with sessao_db() as db:
        linha = _buscar(db, veiculo_id)
        if linha is None:
            return LimitesVeiculo(veiculo_id=veiculo_id, **LIMITES_SUGERIDOS)
        return _solta(linha)


def efetivos_da_sessao(sessao: Sessao) -> dict:
    """Os limites que valeram NAQUELA gravacao.

    Sessao gravada antes das colunas de snapshot existirem tem tudo nulo:
    cai nos valores SUGERIDOS, que sao um palpite e nao o que valeu na
    epoca - o valor daquele dia nunca foi guardado. `do_snapshot` diz qual
    dos dois casos e, para a tela poder avisar.
    """
    gravados = {campo: getattr(sessao, f"limite_{campo}", None) for campo in CAMPOS_LIMITE}
    if all(valor is None for valor in gravados.values()):
        return {**sugeridos(), "do_snapshot": False}
    base = sugeridos()
    return {
        **{campo: (gravados[campo] if gravados[campo] is not None else base[campo])
           for campo in CAMPOS_LIMITE},
        "do_snapshot": True,
    }


def para_snapshot(limites) -> dict:
    """Os seis campos com o prefixo `limite_`, como a Sessao os guarda."""
    return {f"limite_{campo}": getattr(limites, campo) for campo in CAMPOS_LIMITE}
