"""Os limites de alerta de cada carro.

Nao ha limite global nem heranca: todo veiculo tem uma linha com os seis
valores preenchidos. Por isso aqui nao existe mescla - o que esta gravado
na linha e o que vale.

Mexe aqui quem mudar como um limite chega ao detector ou as metricas.
"""

from typing import Optional

from sqlmodel import select

from ..banco import sessao_db
from ..modelos import CAMPOS_LIMITE, LIMITES_SUGERIDOS, LimitesVeiculo, Sessao, Veiculo


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

    Carro sem linha nao deveria existir - `criar()` grava uma e o backfill
    cobre os antigos -, mas se aparecer, os sugeridos respondem em vez de
    estourar: a tela de limites e justamente onde isso se conserta.
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


def garantir_linhas() -> int:
    """Da limites a todo carro que ainda nao tem, e preenche campo nulo.

    Roda no `criar_tabelas()`. Duas situacoes, as duas de banco antigo:
    veiculo cadastrado antes de a linha de limites existir, e linha criada
    quando os campos eram anulaveis (nulo queria dizer "herda o padrao", e
    nao ha mais padrao de quem herdar).

    **Nunca sobrescreve valor ja gravado** - so preenche o que falta.
    Um carro com shift light proprio em 5000 continua em 5000.

    Devolve quantas linhas mexeu; idempotente, entao a segunda execucao
    devolve zero.
    """
    tabela = LimitesVeiculo.__table__
    colunas = [getattr(LimitesVeiculo, campo) for campo in CAMPOS_LIMITE]
    mexidas = 0

    with sessao_db() as db:
        # Seleciona COLUNAS, nao o modelo: a linha antiga pode ter nulo
        # onde o modelo agora exige int, e montar o objeto estouraria na
        # validacao - justamente na linha que se quer consertar. Por isso o
        # insert e o update tambem vao pela tabela, e nao pelo ORM.
        existentes = {
            linha[0]: dict(zip(CAMPOS_LIMITE, linha[1:]))
            for linha in db.exec(select(LimitesVeiculo.veiculo_id, *colunas))
        }

        for veiculo_id in db.exec(select(Veiculo.id)):
            gravados = existentes.get(veiculo_id)

            if gravados is None:
                db.execute(tabela.insert().values(veiculo_id=veiculo_id, **LIMITES_SUGERIDOS))
                mexidas += 1
                continue

            faltando = {c: LIMITES_SUGERIDOS[c] for c in CAMPOS_LIMITE if gravados[c] is None}
            if faltando:
                db.execute(
                    tabela.update()
                    .where(tabela.c.veiculo_id == veiculo_id)
                    .values(**faltando)
                )
                mexidas += 1

        if mexidas:
            db.commit()
    return mexidas


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
