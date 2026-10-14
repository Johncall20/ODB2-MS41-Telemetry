"""Ciclo de vida da sessao: abrir, fechar, descartar, e os eventos dela.
Mexe aqui quem mudar o que acontece ao iniciar ou encerrar uma gravacao.
Os limites saem de `repositorios/limites.py`; aqui eles so entram gravados,
como o snapshot que `criar()` recebe.

**As leituras de tela filtram pelo dono**, atravessando
`sessao -> veiculo -> cliente -> usuario`. `usuario_id` e obrigatorio nelas
(`None` nao filtra, e e o que o seed e o `--recalcular` passam). As
funcoes de ESCRITA - encerrar, descartar, gravar_agregados - continuam por
id: quem chama ja autorizou a sessao numa leitura filtrada antes.
"""

from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import Float, case, func, or_
from sqlmodel import select

from ..banco import sessao_db
from ..modelos import (
    Evento,
    Sessao,
    Veiculo,
    StatusSessao,
    TipoEvento,
    agora,
)

# INICIO_SESSAO e FIM_SESSAO existem em toda sessao. Contar os dois na
# coluna "eventos" faria toda sessao parecer ter dois eventos.
EVENTOS_DE_ROTINA = (TipoEvento.INICIO_SESSAO, TipoEvento.FIM_SESSAO)

PERIODOS = {"7d": 7, "30d": 30, "90d": 90, "tudo": None}
ORDENACOES = ("data", "duracao", "rpm_maximo", "eventos")
DIRECOES = ("asc", "desc")


def _do_usuario(consulta, usuario_id: Optional[int]):
    """Recorta para as sessoes dos carros de uma conta.

    Um salto: a sessao pertence ao veiculo, e o veiculo guarda o dono. A
    sessao nao ganhou `usuario_id` proprio de proposito - ela nao tem
    indice que precise dele, e um terceiro lugar guardando o mesmo dono
    sairia do ar dos outros dois no primeiro carro que trocasse de mao.
    """
    if usuario_id is None:
        return consulta
    return consulta.join(Veiculo, Veiculo.id == Sessao.veiculo_id).where(
        Veiculo.usuario_id == usuario_id
    )


def _colunas_derivadas():
    """Colunas derivadas para filtrar e ordenar a lista de sessoes.

    Saem das colunas gravadas, entao sessao sem agregado vem NULL e cai
    fora dos filtros. Espelham exportador.resumo(): mexeu aqui, mexa la.
    """
    eventos = (
        select(func.count(Evento.id))
        .where(Evento.sessao_id == Sessao.id, Evento.tipo.notin_(EVENTOS_DE_ROTINA))
        .scalar_subquery()
    )
    integridade = case(
        (
            Sessao.total_amostras > 0,
            func.cast(Sessao.amostras_completas, Float)
            * 100.0
            / func.cast(Sessao.total_amostras, Float),
        ),
        else_=None,
    )
    # Sessao aberta conta ate agora. EXTRACT(EPOCH FROM ...) ja devolve
    # segundos - o julianday do SQLite dava dias e pedia um * 86400.
    duracao = func.extract(
        "epoch", func.coalesce(Sessao.encerrada_em, agora()) - Sessao.iniciada_em
    )

    return {
        "duracao": duracao,
        "rpm_maximo": Sessao.rpm_pico,
        "eventos": eventos,
        "integridade": integridade,
    }


def listar_para_tela(
    usuario_id: Optional[int],
    veiculo_id: Optional[int] = None,
    periodo: str = "tudo",
    data_inicio: Optional[datetime] = None,
    data_fim: Optional[datetime] = None,
    tipos_evento: Optional[list[str]] = None,
    sem_eventos: bool = False,
    duracao_minima_s: Optional[float] = None,
    integridade_minima: Optional[float] = None,
    ordenar_por: str = "data",
    direcao: str = "desc",
) -> list[Sessao]:
    """Sessoes da tela, ja filtradas e ordenadas pelo banco.

    Tipos de evento e `sem_eventos` somam com OR, nao intersectam. Evento
    de rotina nao conta para `sem_eventos` - existe em toda sessao.
    """
    d = _colunas_derivadas()
    consulta = _do_usuario(select(Sessao), usuario_id)

    if veiculo_id is not None:
        consulta = consulta.where(Sessao.veiculo_id == veiculo_id)

    # Intervalo explicito manda; periodo e o atalho.
    if data_inicio is not None or data_fim is not None:
        if data_inicio is not None:
            consulta = consulta.where(Sessao.iniciada_em >= data_inicio)
        if data_fim is not None:
            consulta = consulta.where(Sessao.iniciada_em <= data_fim)
    else:
        dias = PERIODOS.get(periodo)
        if dias is not None:
            consulta = consulta.where(Sessao.iniciada_em >= agora() - timedelta(days=dias))

    recortes = []
    if tipos_evento:
        recortes.append(
            select(Evento.id)
            .where(Evento.sessao_id == Sessao.id, Evento.tipo.in_(tipos_evento))
            .exists()
        )
    if sem_eventos:
        recortes.append(
            ~select(Evento.id)
            .where(Evento.sessao_id == Sessao.id, Evento.tipo.notin_(EVENTOS_DE_ROTINA))
            .exists()
        )
    if recortes:
        consulta = consulta.where(or_(*recortes))

    if duracao_minima_s is not None:
        consulta = consulta.where(d["duracao"] >= duracao_minima_s)

    if integridade_minima is not None:
        consulta = consulta.where(d["integridade"] >= integridade_minima)

    coluna = {
        "data": Sessao.iniciada_em,
        "duracao": d["duracao"],
        "rpm_maximo": d["rpm_maximo"],
        "eventos": d["eventos"],
    }.get(ordenar_por, Sessao.iniciada_em)
    alvo = coluna.desc() if direcao == "desc" else coluna.asc()

    if ordenar_por == "rpm_maximo":
        # Sessao sem nenhuma leitura de rpm valida nao tem pico; vai para
        # o fim nos dois sentidos, como "nunca gravou" na tela de veiculos.
        consulta = consulta.order_by(case((d["rpm_maximo"].is_(None), 1), else_=0), alvo)
    else:
        consulta = consulta.order_by(alvo)

    with sessao_db() as db:
        return list(db.exec(consulta))


def buscar(sessao_id: int, usuario_id: Optional[int]) -> Optional[Sessao]:
    """A sessao pelo id, ou None. Volta desanexada da Session.

    Sessao de outra conta responde None, como sessao inexistente: a rota
    devolve 404, e nao 403, para nao confirmar que o id existe.
    """
    with sessao_db() as db:
        return db.exec(
            _do_usuario(select(Sessao).where(Sessao.id == sessao_id), usuario_id)
        ).first()


def listar(usuario_id: Optional[int], veiculo_id: Optional[int] = None) -> list[Sessao]:
    """Sessoes, opcionalmente so as de um veiculo, da mais recente para a
    mais antiga. Sessao de veiculo arquivado continua aparecendo: arquivar
    o carro nao esconde o que ele gravou."""
    with sessao_db() as db:
        consulta = _do_usuario(select(Sessao), usuario_id)
        if veiculo_id is not None:
            consulta = consulta.where(Sessao.veiculo_id == veiculo_id)
        return list(db.exec(consulta.order_by(Sessao.iniciada_em.desc())))


def criar(
    veiculo_id: int,
    observacao: Optional[str] = None,
    snapshot: Optional[dict] = None,
    km: Optional[int] = None,
) -> Sessao:
    """Abre a sessao e registra o evento de inicio.

    Sao dois commits, como antes: o primeiro precisa fechar para a sessao
    ganhar id, que o evento referencia.

    `snapshot` sao as colunas `limite_*` ja resolvidas - quem busca o
    efetivo do carro e o gravador, para a decisao de qual limite vale
    ficar num lugar so.

    `km` fica SO na sessao: a quilometragem do carro nao e tocada aqui. Ela
    so recebe o km quando a sessao for encerrada (`encerrar()`), e por isso
    uma sessao descartada por curta demais nunca chega a mexer no carro.
    """
    with sessao_db() as db:
        sessao = Sessao(
            veiculo_id=veiculo_id, observacao=observacao, km=km, **(snapshot or {})
        )
        db.add(sessao)
        db.commit()
        db.refresh(sessao)
        db.add(
            Evento(
                sessao_id=sessao.id,
                tipo=TipoEvento.INICIO_SESSAO,
                mensagem="gravação iniciada",
            )
        )
        db.commit()
        db.refresh(sessao)
        return sessao


def _e_a_mais_recente(db, sessao: Sessao) -> bool:
    """Nenhuma outra sessao do carro comecou depois desta.

    Empate de `iniciada_em` desempata pelo id, como a ordem das listas.
    """
    depois = db.exec(
        select(func.count(Sessao.id)).where(
            Sessao.veiculo_id == sessao.veiculo_id,
            Sessao.id != sessao.id,
            or_(
                Sessao.iniciada_em > sessao.iniciada_em,
                (Sessao.iniciada_em == sessao.iniciada_em) & (Sessao.id > sessao.id),
            ),
        )
    ).one()
    return depois == 0


def _levar_km_ao_carro(db, sessao: Sessao) -> bool:
    """Copia o km da sessao para `veiculo.quilometragem`, se for o caso.

    Tres condicoes, todas necessarias:

    - a sessao tem km (nulo nao apaga o do carro);
    - esta ENCERRADA - ATIVA ainda pode ser descartada por curta demais, e
      o carro ficaria com o km de uma gravacao que nao existe;
    - e a mais recente do carro - corrigir o km de uma sessao antiga nao
      volta o painel do carro para tras.

    Km menor que o atual do carro e aceito (troca de painel, correcao): o
    aviso e da tela. Roda na Session de quem chama, entao entra na mesma
    transacao. Devolve se atualizou.
    """
    if sessao.km is None or sessao.status != StatusSessao.ENCERRADA:
        return False
    if not _e_a_mais_recente(db, sessao):
        return False
    veiculo = db.get(Veiculo, sessao.veiculo_id)
    if veiculo is None:
        return False
    veiculo.quilometragem = sessao.km
    db.add(veiculo)
    return True


def e_a_mais_recente(sessao_id: int) -> bool:
    """Se a sessao e a mais recente do carro - a que, com km, mexe na
    quilometragem dele. A tela de sessao usa para decidir se pede a
    confirmacao de km menor."""
    with sessao_db() as db:
        sessao = db.get(Sessao, sessao_id)
        return sessao is not None and _e_a_mais_recente(db, sessao)


def editar(sessao_id: int, campos: dict) -> Optional[Sessao]:
    """Grava notas e/ou km de uma sessao, em qualquer status.

    So por id: a rota ja conferiu a posse. `campos` traz so o que veio no
    corpo (o que nao veio nao muda). Mudar o km de uma sessao ENCERRADA e
    mais recente leva o valor ao carro na mesma transacao; ATIVA, so na
    sessao - o carro recebe no `encerrar()`.
    """
    with sessao_db() as db:
        sessao = db.get(Sessao, sessao_id)
        if sessao is None:
            return None
        for campo in ("observacao", "km"):
            if campo in campos:
                setattr(sessao, campo, campos[campo])
        db.add(sessao)
        if "km" in campos:
            _levar_km_ao_carro(db, sessao)
        db.commit()
        db.refresh(sessao)
        return sessao


def encerrar(
    sessao_id: int,
    agregados: Optional[dict] = None,
    quando: Optional[datetime] = None,
    mensagem: str = "gravação encerrada",
) -> None:
    """Fecha a sessao, grava os agregados e registra o evento de fim.

    `quando` e `mensagem` sao da sessao interrompida (servidor reiniciado
    no meio da gravacao): ela fecha na hora da ultima amostra, e o evento
    de fim diz o motivo. No encerramento normal, agora e "gravação
    encerrada".

    Status e agregados na MESMA transacao: em dois commits haveria uma
    janela com a sessao encerrada e sem agregado, e a tela mostraria zero.
    O km da sessao vai para o carro tambem aqui, na mesma transacao - e o
    unico momento em que uma sessao recem-gravada mexe no carro, porque a
    descartada nunca chega ao `encerrar()`.
    """
    with sessao_db() as db:
        sessao = db.get(Sessao, sessao_id)
        if sessao is None:
            return
        sessao.status = StatusSessao.ENCERRADA
        # Nunca antes do inicio (o CHECK do banco recusaria).
        sessao.encerrada_em = max(quando, sessao.iniciada_em) if quando else agora()
        for campo, valor in (agregados or {}).items():
            setattr(sessao, campo, valor)
        db.add(sessao)
        _levar_km_ao_carro(db, sessao)
        db.add(
            Evento(
                sessao_id=sessao_id,
                tipo=TipoEvento.FIM_SESSAO,
                mensagem=mensagem,
                criado_em=sessao.encerrada_em,
            )
        )
        db.commit()


def descartar(sessao_id: int) -> None:
    """Apaga a sessao inteira.

    Delete do ORM de proposito: o cascade leva amostras e eventos junto.
    """
    with sessao_db() as db:
        sessao = db.get(Sessao, sessao_id)
        if sessao is None:
            return
        db.delete(sessao)
        db.commit()


def registrar_eventos(eventos: list[Evento]) -> list[Evento]:
    """Grava os eventos e devolve com id e criado_em preenchidos, para o
    gravador poder anuncia-los no websocket."""
    if not eventos:
        return []
    with sessao_db() as db:
        for e in eventos:
            db.add(e)
        db.commit()
        for e in eventos:
            db.refresh(e)
        return eventos


def listar_eventos(sessao_id: int) -> list[Evento]:
    """Eventos da sessao na ordem em que foram gravados. A ordem e do SQL
    e nao do chamador: e ela que define qual anomalia a tela mostra
    primeiro no "+N" de eventos_notaveis()."""
    with sessao_db() as db:
        return list(
            db.exec(select(Evento).where(Evento.sessao_id == sessao_id).order_by(Evento.id))
        )


def gravar_agregados(sessao_id: int, agregados: dict) -> bool:
    """Grava agregados numa sessao ja encerrada (so o --recalcular usa;
    no fluxo normal quem grava e encerrar()). False se a sessao sumiu."""
    with sessao_db() as db:
        sessao = db.get(Sessao, sessao_id)
        if sessao is None:
            return False
        for campo, valor in agregados.items():
            setattr(sessao, campo, valor)
        db.add(sessao)
        db.commit()
        return True


def ids_sem_agregados() -> list[int]:
    """Sessoes encerradas ainda sem agregado - o alvo do --recalcular.

    Enquanto estiverem aqui, ficam de fora dos filtros por pico e
    integridade.
    """
    with sessao_db() as db:
        return list(
            db.exec(
                select(Sessao.id)
                .where(
                    Sessao.status == StatusSessao.ENCERRADA,
                    Sessao.total_amostras == None,  # noqa: E711
                )
                .order_by(Sessao.id)
            )
        )


def ativas() -> list[tuple[int, int]]:
    """As sessoes ATIVA no banco, com o dono do carro: (sessao_id, usuario_id).

    So o `encerrar_orfas()` usa, ao subir o processo - nessa hora o
    gravador ainda nao abriu sessao nenhuma, entao toda ATIVA e de uma
    gravacao que o processo anterior deixou no meio.
    """
    with sessao_db() as db:
        return list(
            db.exec(
                select(Sessao.id, Veiculo.usuario_id)
                .join(Veiculo, Veiculo.id == Sessao.veiculo_id)
                .where(Sessao.status == StatusSessao.ATIVA)
                .order_by(Sessao.id)
            )
        )


def ids_encerradas() -> list[int]:
    """Toda sessao encerrada, com agregado ou sem. E o alvo do
    `--recalcular tudo`, para quando a regra de calculo mudar."""
    with sessao_db() as db:
        return list(
            db.exec(
                select(Sessao.id)
                .where(Sessao.status == StatusSessao.ENCERRADA)
                .order_by(Sessao.id)
            )
        )


def contar_eventos(sessao_id: int) -> int:
    """Quantos eventos a sessao tem, os de rotina inclusive - e o numero
    que o resumo() sempre reportou. COUNT no banco: quem chama quer o
    total, nao os objetos."""
    with sessao_db() as db:
        return db.exec(
            select(func.count(Evento.id)).where(Evento.sessao_id == sessao_id)
        ).one()


def eventos_por_sessao(ids: list[int]) -> dict[int, list[Evento]]:
    """Eventos de varias sessoes de uma vez, agrupados por sessao_id.

    Uma consulta para a pagina inteira, em vez de uma por linha.
    """
    if not ids:
        return {}
    agrupados: dict[int, list[Evento]] = {}
    with sessao_db() as db:
        consulta = select(Evento).where(Evento.sessao_id.in_(ids)).order_by(Evento.id)
        for evento in db.exec(consulta):
            agrupados.setdefault(evento.sessao_id, []).append(evento)
    return agrupados
