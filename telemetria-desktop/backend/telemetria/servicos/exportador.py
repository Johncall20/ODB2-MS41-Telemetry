"""
Resumo da sessao e as saidas: CSV, JSON e o PDF com graficos do matplotlib.
Mexe aqui quem mudar o que a exportacao contem ou como o relatorio parece.

**Este modulo nao filtra por dono**, e por isso passa `None` como
`usuario_id` aos repositorios. Quem chama ja autorizou: as rotas de
sessao conferem a posse com `_exigir_sessao()` antes de pedir qualquer
coisa daqui. Chamar estas funcoes sem essa checagem entrega dado de outra
conta.

Campo com o bit de `valid` apagado sai VAZIO, nunca com o ultimo valor.
"""

from __future__ import annotations

import csv
import io
import json
import re
import unicodedata
from typing import Sequence
from xml.sax.saxutils import escape

from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from ..modelos import CAMPOS_EXTRAS
from ..repositorios import amostras as repo_amostras
from ..repositorios import limites as repo_limites
from ..repositorios import sessoes as repo_sessoes
from ..repositorios import veiculos as repo_veiculos
from . import metricas

COLUNAS = ["rpm", "ect", "iat", "vbat", "tps", "vanos", "vss"]
# Os extras da MS41 entram so no CSV: na tabela do PDF, dezoito colunas nao
# cabem numa A4. Sessao gravada antes deles sai com as celulas vazias.
COLUNAS_CSV = COLUNAS + list(CAMPOS_EXTRAS)


# ------------------------------------------------------- nome do arquivo

# So estes caracteres entram no nome. Acento, espaco e pontuacao viram
# outra coisa: o arquivo atravessa Windows, Linux, e-mail e WhatsApp, e
# cada um deles estraga um caractere diferente.
_PERMITIDOS = re.compile(r"[^A-Za-z0-9_-]+")


def _sem_acento(texto: str) -> str:
    """"Citroën" -> "Citroen". Decompoe e joga fora o que e acento."""
    decomposto = unicodedata.normalize("NFKD", texto or "")
    return "".join(ch for ch in decomposto if not unicodedata.combining(ch))


def _kebab(texto: str) -> str:
    """"BMW 325i Sport" -> "bmw-325i-sport"."""
    limpo = _PERMITIDOS.sub("-", _sem_acento(texto).lower().replace("_", "-"))
    return re.sub(r"-{2,}", "-", limpo).strip("-")


def _identificador(sessao_id: int, veiculo) -> str:
    """Como o carro aparece no nome do arquivo.

    A placa manda: ela ja esta normalizada no banco (maiuscula, sem
    separador) e e o que o mecanico reconhece. Sem placa, marca e modelo
    em kebab-case; sem os dois, o numero da sessao - nunca um nome vazio,
    que deixaria dois sublinhados seguidos.
    """
    if veiculo is not None:
        placa = _PERMITIDOS.sub("", _sem_acento(veiculo.placa or ""))
        if placa:
            return placa
        carro = _kebab(veiculo.descricao())
        if carro:
            return carro
    # O id PEDIDO, nao o da sessao carregada: quando ela nao existe ainda
    # assim o nome diz o que foi pedido, em vez de um zero que nao aponta
    # para nada.
    return f"sessao{sessao_id}"


def _placa_exibida(placa: str | None) -> str | None:
    """A placa como gente le, na capa do PDF: "ABC-1234" no padrao antigo,
    "ABC1D23" no Mercosul, que se escreve sem separador. Gemea do
    `formatarPlaca()` do frontend - o nome do ARQUIVO continua com a
    placa normalizada, sem hifen."""
    if not placa:
        return None
    return f"{placa[:3]}-{placa[3:]}" if re.fullmatch(r"[A-Z]{3}[0-9]{4}", placa) else placa


def _momento_local(sessao) -> str:
    """O inicio da sessao em hora LOCAL, como "2026-09-17_14h32".

    A coluna e TIMESTAMP WITH TIME ZONE, entao o que chega ja vem com
    fuso e so precisa ser convertido. Hora local porque o nome do arquivo
    e lido por gente: "14h32" tem de casar com o que o relogio dizia.
    """
    return sessao.iniciada_em.astimezone().strftime("%Y-%m-%d_%Hh%M")


def nome_arquivo(sessao_id: int, extensao: str) -> str:
    """O nome do arquivo baixado: telemetria_{PLACA}_{AAAA-MM-DD}_{HH}h{MM}.

    Fonte UNICA do nome nas tres exportacoes. O frontend nao monta nome:
    o link de download nao usa o atributo `download`, justamente para o
    navegador obedecer ao Content-Disposition - se alguem puser o atributo
    la, passam a existir dois nomes e eles vao divergir.
    """
    sessao = repo_sessoes.buscar(sessao_id, None)
    veiculo = (
        repo_veiculos.buscar(sessao.veiculo_id, None, incluir_arquivados=True)
        if sessao is not None
        else None
    )
    ext = _PERMITIDOS.sub("", extensao).lower()

    partes = ["telemetria", _identificador(sessao_id, veiculo)]
    # Sessao inexistente nao tem data para carimbar; o resto do nome ainda
    # identifica o pedido, e a rota de PDF ja responde 404 nesse caso.
    if sessao is not None:
        partes.append(_momento_local(sessao))
    return f"{'_'.join(partes)}.{ext}"


def cabecalhos_anexo(sessao_id: int, extensao: str) -> dict:
    """O Content-Disposition pronto, para as tres rotas nao repetirem."""
    return {"Content-Disposition": f'attachment; filename="{nome_arquivo(sessao_id, extensao)}"'}


def _montar(sessao, total, completas, picos: dict, eventos: int) -> dict:
    """A forma do resumo, montada uma vez so.

    Os dois caminhos tem de devolver as MESMAS chaves, senao a tela muda
    conforme a sessao esteja consolidada ou nao.
    """
    return {
        "sessao_id": sessao.id,
        "status": sessao.status.value,
        "iniciada_em": sessao.iniciada_em,
        "encerrada_em": sessao.encerrada_em,
        "duracao_s": round(sessao.duracao_s(), 1),
        "amostras": total,
        "amostras_completas": completas,
        "integridade_pct": round(100 * completas / total, 1) if total else 0.0,
        "rpm_pico": picos["rpm"],
        "vss_pico": picos["vss"],
        "ect_pico": picos["ect"],
        "vbat_min": picos["vbat"],
        "eventos": eventos,
    }


def _resumo_gravado(sessao, eventos: int) -> dict:
    """Resumo lido da propria linha de Sessao. Nao abre a tabela de
    amostras - e por isso que a listagem pode chamar isto por linha."""
    return _montar(
        sessao,
        sessao.total_amostras or 0,
        sessao.amostras_completas or 0,
        {
            "rpm": sessao.rpm_pico,
            "vss": sessao.vss_pico,
            "ect": sessao.ect_pico,
            "vbat": sessao.vbat_min,
        },
        eventos,
    )


def _resumo_calculado(sessao, eventos: int) -> dict:
    """Resumo apurado sobre as amostras (sessao ATIVA ou antiga).

    Carrega a serie inteira: nao use em laco.
    """
    amostras = repo_amostras.listar(sessao.id)

    def pico(campo: str):
        vals = [getattr(a, campo) for a in amostras if a.valido(campo)]
        return max(vals) if vals else None

    return _montar(
        sessao,
        len(amostras),
        sum(1 for a in amostras if a.completa()),
        {
            "rpm": pico("rpm"),
            "vss": pico("vss"),
            "ect": pico("ect"),
            "vbat": min((a.vbat for a in amostras if a.valido("vbat")), default=None),
        },
        eventos,
    )


def resumo_de(sessao, eventos: Sequence) -> dict:
    """Resumo de uma sessao e eventos que quem chama ja carregou.

    Com a sessao consolidada nao sai consulta nenhuma daqui - e o que a
    listagem usa.
    """
    if sessao.consolidada():
        return _resumo_gravado(sessao, len(eventos))
    return _resumo_calculado(sessao, len(eventos))


def resumo(sessao_id: int) -> dict:
    """Resumo pelo id, para quem tem so o numero da sessao.

    Sessao encerrada e consolidada responde com os campos gravados no
    encerramento; ATIVA e apurada na hora, sobre as amostras.
    """
    sessao = repo_sessoes.buscar(sessao_id, None)
    if sessao is None:
        return {}
    eventos = repo_sessoes.contar_eventos(sessao_id)
    if sessao.consolidada():
        return _resumo_gravado(sessao, eventos)
    return _resumo_calculado(sessao, eventos)


def para_csv(sessao_id: int) -> str:
    """CSV da sessao, uma linha por amostra. Campo sem leitura sai vazio."""
    saida = io.StringIO()
    w = csv.writer(saida)
    w.writerow(["recebida_em", "t_ms"] + COLUNAS_CSV + ["valid"])
    for a in repo_amostras.listar(sessao_id):
        linha = [a.recebida_em.isoformat(timespec="milliseconds"), a.t_ms]
        for c in COLUNAS_CSV:
            linha.append(getattr(a, c) if a.valido(c) else "")
        linha.append(a.valid)
        w.writerow(linha)
    return saida.getvalue()


def para_json(sessao_id: int) -> str:
    """A sessao inteira em JSON: veiculo, resumo, metricas, serie e eventos.

    E o formato de quem vai reprocessar a gravacao fora do app, entao vai
    tudo - inclusive o `valid` cru de cada amostra.
    """
    sessao = repo_sessoes.buscar(sessao_id, None)
    amostras = repo_amostras.listar(sessao_id)
    eventos = repo_sessoes.listar_eventos(sessao_id)
    # Pelo id, e nao por sessao.veiculo: o objeto vem desanexado do
    # repositorio e relacao preguicosa nao carrega mais.
    veiculo = repo_veiculos.buscar(sessao.veiculo_id, None, incluir_arquivados=True) if sessao else None
    dados = resumo(sessao_id)
    pacote = {
        # Marca e modelo pelo NOME do catalogo, como a tela mostra: o id
        # sozinho nao diria nada a quem abre o arquivo fora do app. Os dois
        # continuam como dado (a marca pode ser "Outra"); `descricao` e o
        # nome como as telas escrevem.
        "veiculo": (
            {
                **veiculo.model_dump(),
                "marca": veiculo.nome_marca,
                "modelo": veiculo.nome_modelo,
                "descricao": veiculo.descricao(),
            }
            if veiculo
            else None
        ),
        "sessao": sessao.model_dump() if sessao else None,
        "resumo": dados,
        # A serie ja esta carregada, entao as metricas saem de graca.
        "metricas": metricas.calcular(
            amostras,
            dados.get("duracao_s"),
            repo_limites.efetivos_da_sessao(sessao) if sessao else None,
        ),
        "amostras": [a.model_dump() for a in amostras],
        "eventos": [e.model_dump() for e in eventos],
    }
    return json.dumps(pacote, default=str, ensure_ascii=False, indent=2)


# --------------------------------------------------------------------- pdf

SECOES_PADRAO = ("resumo", "graficos", "eventos")
SECOES_VALIDAS = ("resumo", "graficos", "eventos", "amostras")

# Series desenhadas no relatorio: campo do firmware, titulo e unidade.
SERIES_PDF = (
    ("rpm", "RPM", ""),
    ("vss", "Velocidade", "km/h"),
    ("ect", "Temperatura do motor", "°C"),
)

ROTULO_EVENTO_PDF = {
    "INICIO_SESSAO": "Início da sessão",
    "FIM_SESSAO": "Fim da sessão",
    "SHIFT_LIGHT": "Shift light",
    "RPM_ALTO": "Giro acima do limite",
    "TEMP_ALTA": "Temperatura alta",
    "BATERIA_BAIXA": "Bateria baixa",
    "PERDA_CONEXAO": "Perda de conexão",
    "LEITURA_INCOMPLETA": "Leitura incompleta",
}


def _mmss(segundos) -> str:
    if segundos is None:
        return "-"
    total = int(round(segundos))
    return f"{total // 60:02d}min {total % 60:02d}s"


def _num(valor, sufixo: str = "") -> str:
    """Numero para o relatorio. None vira travessao, nunca zero - zero
    seria inventar uma medicao que a central nao deu."""
    if valor is None:
        return "—"
    if isinstance(valor, float):
        texto = f"{valor:,.2f}".rstrip("0").rstrip(".")
    else:
        texto = f"{valor:,}"
    texto = texto.replace(",", ".")
    return f"{texto} {sufixo}".strip()


# Cores do relatorio. O PDF sai em papel branco, entao a paleta e a clara -
# nao os tokens escuros da tela.
LARANJA = "#D95C0F"
TINTA = "#1A1A1A"
CINZA = "#777777"
GRADE = "#DDDDDD"

# Renderiza acima do tamanho final e deixa o PDF reduzir, senao a linha
# sai serrilhada no zoom e na impressao.
DPI_GRAFICO = 200


def _mmss_curto(segundos: float) -> str:
    """mm:ss para os ticks do eixo de tempo. O _mmss() longo ("01min 30s")
    nao cabe repetido embaixo do grafico."""
    total = max(0, int(round(segundos)))
    return f"{total // 60:02d}:{total % 60:02d}"


def _serie_para_grafico(amostras, campo: str, inicio):
    """Tempo decorrido e valores de um campo, para desenhar.

    Amostra invalida entra como NaN, que interrompe a linha. X e tempo de
    verdade, nao indice de amostra.
    """
    xs, ys = [], []
    for a in amostras:
        xs.append((a.recebida_em - inicio).total_seconds())
        ys.append(getattr(a, campo) if a.valido(campo) else float("nan"))
    return xs, ys


def _png_da_serie(campo, titulo, unidade, amostras, inicio, largura_pt, altura_pt=132):
    """Uma serie como PNG, ou None se o campo nao teve leitura valida."""
    xs, ys = _serie_para_grafico(amostras, campo, inicio)
    validos = [v for v in ys if v == v]  # NaN != NaN
    if not validos:
        return None

    minimo, maximo = min(validos), max(validos)
    if maximo == minimo:
        # Serie constante: abre um respiro para a linha nao colar na borda.
        minimo -= 1
        maximo += 1

    # 1 pt = 1/72 pol; a figura nasce do tamanho que vai ocupar no PDF.
    figura = Figure(figsize=(largura_pt / 72, altura_pt / 72), dpi=DPI_GRAFICO)
    FigureCanvasAgg(figura)
    eixo = figura.add_subplot(111)

    eixo.plot(xs, ys, color=LARANJA, linewidth=1.1, solid_joinstyle="round")
    eixo.fill_between(xs, minimo, ys, color=LARANJA, alpha=0.12, linewidth=0)

    eixo.set_ylim(minimo, maximo)
    eixo.set_xlim(min(xs, default=0), max(xs, default=1))
    eixo.xaxis.set_major_formatter(FuncFormatter(lambda v, _: _mmss_curto(v)))
    eixo.tick_params(labelsize=6.5, colors=CINZA, length=2, width=0.4)
    eixo.grid(axis="y", color=GRADE, linewidth=0.4)
    eixo.set_axisbelow(True)
    for lado, visivel in (("left", True), ("bottom", True), ("top", False), ("right", False)):
        eixo.spines[lado].set_visible(visivel)
        if visivel:
            eixo.spines[lado].set_color(GRADE)
            eixo.spines[lado].set_linewidth(0.4)

    faixa = f"{_num(minimo)} – {_num(maximo, unidade)}"
    eixo.set_title(titulo, fontsize=8, color=TINTA, loc="left", pad=6)
    eixo.text(
        1.0, 1.0, faixa, transform=eixo.transAxes,
        ha="right", va="bottom", fontsize=7, color=CINZA,
    )

    figura.tight_layout(pad=0.4)
    saida = io.BytesIO()
    # Fundo transparente: a pagina do relatorio ja e branca, e assim a
    # imagem fica menor.
    figura.savefig(saida, format="png", dpi=DPI_GRAFICO, transparent=True)
    saida.seek(0)
    return saida


def para_pdf(sessao_id: int, secoes: Sequence[str] = SECOES_PADRAO) -> bytes:
    """Relatorio da sessao em PDF; `secoes` escolhe o que entra.

    A tabela de amostras e opcional: numa sessao longa vira dezenas de
    paginas. Nao ha secao de codigo de falha - o firmware nao le DTC.
    """
    escolhidas = [s for s in secoes if s in SECOES_VALIDAS] or list(SECOES_PADRAO)

    sessao = repo_sessoes.buscar(sessao_id, None)
    if sessao is None:
        raise ValueError(f"sessão {sessao_id} não encontrada")
    veiculo = repo_veiculos.buscar(sessao.veiculo_id, None, incluir_arquivados=True)
    amostras = repo_amostras.listar(sessao_id)
    eventos = sorted(repo_sessoes.listar_eventos(sessao_id), key=lambda e: e.id)
    dados = resumo(sessao_id)
    # Hora LOCAL, igual ao nome do arquivo: o relatorio e lido por gente, e
    # duas horas diferentes para a mesma sessao - uma na capa, outra no
    # nome - seria o tipo de divergencia que ninguem nota a tempo.
    inicio = sessao.iniciada_em.astimezone()
    identificacao = " · ".join(
        p
        for p in (
            _placa_exibida(veiculo.placa) if veiculo else None,
            f"{veiculo.descricao()} "
            f"{veiculo.ano_fabricacao}/{veiculo.ano_modelo}" if veiculo else None,
            inicio.strftime("%d/%m/%Y %H:%M"),
        )
        if p
    )

    saida = io.BytesIO()
    doc = SimpleDocTemplate(
        saida,
        pagesize=A4,
        leftMargin=42,
        rightMargin=42,
        topMargin=42,
        bottomMargin=42,
        title=f"Relatório da sessão {sessao_id}",
        author="Telemetria DS2/MS41",
    )
    estilos = getSampleStyleSheet()
    est_titulo = ParagraphStyle(
        "tituloRel", parent=estilos["Title"], fontSize=17, alignment=0, spaceAfter=2
    )
    est_legenda = ParagraphStyle(
        "legendaRel",
        parent=estilos["Normal"],
        fontSize=9.5,
        textColor=colors.HexColor("#666666"),
    )
    est_secao = ParagraphStyle(
        "secaoRel", parent=estilos["Heading2"], fontSize=12, spaceBefore=18, spaceAfter=6
    )
    est_secao_menor = ParagraphStyle(
        "secaoMenorRel", parent=estilos["Heading3"], fontSize=9.5, spaceBefore=8, spaceAfter=2
    )
    est_nota = ParagraphStyle(
        "notaRel",
        parent=estilos["Normal"],
        fontSize=8.5,
        textColor=colors.HexColor("#777777"),
        spaceBefore=6,
    )

    largura = doc.width
    partes = [Paragraph("Relatório de sessão", est_titulo), Paragraph(identificacao, est_legenda)]

    # Km e notas sao da sessao, nao de uma secao escolhivel: vao na capa,
    # e SO quando preenchidos - campo vazio no PDF seria ruido. As notas
    # mantem as quebras de linha; o texto e escapado porque o Paragraph do
    # reportlab le marcacao, e uma nota com "<" quebraria o relatorio.
    if sessao.km is not None:
        km = f"{sessao.km:,}".replace(",", ".")
        partes.append(Paragraph(f"Quilometragem: {km} km", est_legenda))
    if sessao.observacao:
        partes += [
            Paragraph("Notas", est_secao),
            Paragraph(escape(sessao.observacao).replace(chr(10), "<br/>"), estilos["Normal"]),
        ]

    if "resumo" in escolhidas:
        linhas = [
            ("Duração", _mmss(dados.get("duracao_s"))),
            ("RPM máximo", _num(dados.get("rpm_pico"))),
            ("Velocidade máxima", _num(dados.get("vss_pico"), "km/h")),
            ("Temperatura máxima", _num(dados.get("ect_pico"), "°C")),
            ("Tensão mínima", _num(dados.get("vbat_min"), "V")),
            ("Amostras", _num(dados.get("amostras"))),
            ("Amostras completas", _num(dados.get("amostras_completas"))),
            ("Integridade", _num(dados.get("integridade_pct"), "%")),
            ("Eventos", _num(dados.get("eventos"))),
        ]
        tabela = Table(linhas, colWidths=[largura * 0.55, largura * 0.45])
        tabela.setStyle(
            TableStyle(
                [
                    ("FONT", (0, 0), (0, -1), "Helvetica", 9.5),
                    ("FONT", (1, 0), (1, -1), "Courier", 9.5),
                    ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#555555")),
                    ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                    ("LINEBELOW", (0, 0), (-1, -2), 0.3, colors.HexColor("#DDDDDD")),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        partes += [
            Paragraph("Resumo", est_secao),
            tabela,
            Paragraph(
                "Integridade é a fração de amostras em que a central respondeu os sete "
                "campos. Onde a leitura falhou, o valor não foi estimado.",
                est_nota,
            ),
        ]

    if "graficos" in escolhidas:
        partes.append(Paragraph("Gráficos", est_secao))
        for campo, nome, unidade in SERIES_PDF:
            png = _png_da_serie(campo, nome, unidade, amostras, inicio, largura)
            if png is None:
                # Sem nenhuma leitura valida nao ha o que desenhar. A frase
                # e melhor que um eixo vazio: diz por que o grafico faltou.
                partes.append(Paragraph(nome, est_secao_menor))
                partes.append(
                    Paragraph(
                        "Nenhuma amostra desta sessão trouxe leitura válida deste campo.",
                        est_legenda,
                    )
                )
            else:
                px_largura, px_altura = ImageReader(png).getSize()
                # ImageReader consumiu o buffer; o Image le o mesmo BytesIO
                # de novo, entao volta para o inicio antes de entregar.
                png.seek(0)
                # A imagem entra com a largura do texto; a altura acompanha
                # a proporcao, senao o grafico sai esticado.
                partes.append(
                    Image(png, width=largura, height=largura * px_altura / px_largura)
                )
            partes.append(Spacer(1, 12))
        partes.append(
            Paragraph(
                "A linha é interrompida nos ciclos em que a central não respondeu aquele "
                "campo. Trecho vazio significa ausência de leitura, não valor constante.",
                est_nota,
            )
        )

    if "eventos" in escolhidas:
        partes.append(Paragraph("Eventos", est_secao))
        if not eventos:
            partes.append(Paragraph("Nenhum evento registrado nesta sessão.", est_legenda))
        else:
            linhas = [("Tempo", "Evento", "Detalhe")]
            for e in eventos:
                decorrido = (e.criado_em - inicio).total_seconds()
                linhas.append(
                    (
                        _mmss(max(decorrido, 0)),
                        ROTULO_EVENTO_PDF.get(e.tipo.value, e.tipo.value),
                        e.mensagem or "",
                    )
                )
            tabela = Table(
                linhas, colWidths=[largura * 0.16, largura * 0.32, largura * 0.52], repeatRows=1
            )
            tabela.setStyle(
                TableStyle(
                    [
                        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 9),
                        ("FONT", (0, 1), (0, -1), "Courier", 9),
                        ("FONT", (1, 1), (-1, -1), "Helvetica", 9),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#555555")),
                        ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#DDDDDD")),
                        ("TOPPADDING", (0, 0), (-1, -1), 4),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ]
                )
            )
            partes.append(tabela)

    if "amostras" in escolhidas:
        partes.append(Paragraph("Amostras", est_secao))
        cabecalho = ["t (ms)"] + COLUNAS
        linhas = [cabecalho]
        for a in amostras:
            # Mesma regra do CSV: campo com o bit apagado sai como celula vazia.
            linhas.append(
                [str(a.t_ms)] + [str(getattr(a, c)) if a.valido(c) else "" for c in COLUNAS]
            )
        tabela = Table(
            linhas, colWidths=[largura / len(cabecalho)] * len(cabecalho), repeatRows=1
        )
        tabela.setStyle(
            TableStyle(
                [
                    ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 7.5),
                    ("FONT", (0, 1), (-1, -1), "Courier", 7.5),
                    ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
                    ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#EEEEEE")),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ]
            )
        )
        partes += [
            tabela,
            Paragraph(
                "Célula vazia = a central não respondeu aquele campo naquele ciclo.", est_nota
            ),
        ]

    doc.build(partes)
    return saida.getvalue()
