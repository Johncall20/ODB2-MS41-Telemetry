"""
Consultas do catalogo de marca e modelo.

O que e da conta aqui sao os modelos CUSTOMIZADOS: `usuario_id` e
parametro obrigatorio em toda funcao que os toca, como no resto dos
repositorios. Marca e modelo de catalogo (`usuario_id` nulo) sao de todos.

Nome repetido e comparado sem diferenciar maiusculas, que e o que os
indices unicos em `lower(nome)` garantem no banco.
"""

from typing import Optional

from sqlalchemy import func, or_, text
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from ..banco import sessao_db
from ..modelos import Marca, Modelo


def _visivel_para(usuario_id: Optional[int]):
    """Catalogo mais os customizados da conta. `None` nao ve customizado
    de ninguem - nao ha uso fora da web que precise."""
    return or_(Modelo.usuario_id == None, Modelo.usuario_id == usuario_id)  # noqa: E711


def listar_marcas() -> list[Marca]:
    """Todas as marcas, por nome."""
    with sessao_db() as db:
        return list(db.exec(select(Marca).order_by(func.lower(Marca.nome))))


def buscar_marca(marca_id: int) -> Optional[Marca]:
    with sessao_db() as db:
        return db.get(Marca, marca_id)


def marca_por_nome(nome: str) -> Optional[Marca]:
    """A marca pelo nome, sem diferenciar maiusculas."""
    with sessao_db() as db:
        return db.exec(select(Marca).where(func.lower(Marca.nome) == nome.lower())).first()


def listar_modelos(marca_id: int, usuario_id: Optional[int]) -> list[Modelo]:
    """Os modelos da marca que a conta enxerga: catalogo + os dela."""
    with sessao_db() as db:
        return list(
            db.exec(
                select(Modelo)
                .where(Modelo.marca_id == marca_id, _visivel_para(usuario_id))
                .order_by(func.lower(Modelo.nome), Modelo.id)
            )
        )


def modelo_visivel(modelo_id: int, usuario_id: Optional[int]) -> Optional[Modelo]:
    """O modelo, se for de catalogo ou desta conta. Customizado de outra
    conta responde None, igual a inexistente."""
    with sessao_db() as db:
        return db.exec(
            select(Modelo).where(Modelo.id == modelo_id, _visivel_para(usuario_id))
        ).first()


def achar_por_nome(marca_id: int, nome: str, usuario_id: Optional[int]) -> Optional[Modelo]:
    """O modelo da marca com esse nome, sem diferenciar maiusculas. O do
    catalogo vence o customizado: e ele que a conta deveria ter escolhido."""
    with sessao_db() as db:
        return db.exec(
            select(Modelo)
            .where(
                Modelo.marca_id == marca_id,
                func.lower(Modelo.nome) == nome.lower(),
                _visivel_para(usuario_id),
            )
            .order_by(Modelo.usuario_id.asc().nulls_first())
        ).first()


def achar_ou_criar_customizado(marca_id: int, nome: str, usuario_id: int) -> tuple[Modelo, bool]:
    """O modelo com esse nome (catalogo ou da conta) ou um customizado
    novo. Devolve `(modelo, criado)`.

    Devolver o existente, em vez de duplicar, e o que impede o "Nao
    encontrei meu modelo" de criar "325i" ao lado do 325i do catalogo. A
    corrida entre a busca e o INSERT esbarra no indice unico, e a busca e
    refeita.
    """
    existente = achar_por_nome(marca_id, nome, usuario_id)
    if existente is not None:
        return existente, False
    try:
        with sessao_db() as db:
            modelo = Modelo(marca_id=marca_id, nome=nome, usuario_id=usuario_id)
            db.add(modelo)
            db.commit()
            db.refresh(modelo)
            return modelo, True
    except IntegrityError:
        return achar_por_nome(marca_id, nome, usuario_id), False


def modelo_por_nomes(marca: str, modelo: str, usuario_id: Optional[int]) -> Optional[Modelo]:
    """O modelo pelo nome da marca e dele, sem diferenciar maiusculas.
    Para quem tem o texto e nao o id (o `semear.py`)."""
    with sessao_db() as db:
        return db.exec(
            select(Modelo)
            .join(Marca, Marca.id == Modelo.marca_id)
            .where(
                func.lower(Marca.nome) == marca.lower(),
                func.lower(Modelo.nome) == modelo.lower(),
                _visivel_para(usuario_id),
            )
            .order_by(Modelo.usuario_id.asc().nulls_first())
        ).first()


def gravar_catalogo(marcas: list[dict]) -> dict:
    """Carga idempotente do catalogo: insere o que falta, por nome.

    `marcas` e `[{"nome": ..., "modelos": [{"nome", "ano_min", "ano_max"}]}]`.
    Nome que ja existe (sem diferenciar maiusculas) fica, e tem a grafia e
    a faixa de anos atualizadas. **Nunca apaga**: um modelo que saiu da
    FIPE pode estar no carro de alguem, e faixa nula no arquivo nao apaga a
    que o banco ja tem (`COALESCE`) - nulo ali e "ainda nao consultado".
    Tudo numa transacao - catalogo pela metade nao serve a ninguem.
    """
    novas = novos = faixas = 0
    with sessao_db() as db:
        for marca in marcas:
            linha = db.execute(
                text(
                    "INSERT INTO marca (nome) VALUES (:nome) "
                    "ON CONFLICT (lower(nome)) DO UPDATE SET nome = EXCLUDED.nome "
                    "RETURNING id, (xmax = 0) AS inserida"
                ),
                {"nome": marca["nome"]},
            ).one()
            novas += int(linha.inserida)
            for modelo in marca["modelos"]:
                gravado = db.execute(
                    text(
                        "INSERT INTO modelo (marca_id, nome, ano_min, ano_max) "
                        "VALUES (:m, :n, :de, :ate) "
                        "ON CONFLICT (marca_id, lower(nome)) WHERE usuario_id IS NULL "
                        "DO UPDATE SET nome = EXCLUDED.nome, "
                        "ano_min = COALESCE(EXCLUDED.ano_min, modelo.ano_min), "
                        "ano_max = COALESCE(EXCLUDED.ano_max, modelo.ano_max) "
                        "RETURNING (xmax = 0) AS inserido"
                    ),
                    {
                        "m": linha.id,
                        "n": modelo["nome"],
                        "de": modelo.get("ano_min"),
                        "ate": modelo.get("ano_max"),
                    },
                ).one()
                novos += int(gravado.inserido)
                faixas += int(modelo.get("ano_min") is not None)
        db.commit()
    return {"marcas_novas": novas, "modelos_novos": novos, "com_faixa": faixas}


def contar() -> dict:
    """Quantas marcas e modelos de catalogo o banco tem."""
    with sessao_db() as db:
        return {
            "marcas": db.exec(select(func.count(Marca.id))).one(),
            "modelos": db.exec(
                select(func.count(Modelo.id)).where(Modelo.usuario_id == None)  # noqa: E711
            ).one(),
            "com_faixa": db.exec(
                select(func.count(Modelo.id)).where(Modelo.ano_min != None)  # noqa: E711
            ).one(),
        }
