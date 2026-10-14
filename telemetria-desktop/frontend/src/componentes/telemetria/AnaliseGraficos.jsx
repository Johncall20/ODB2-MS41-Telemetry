/*
  A Analise de uma sessao, montada: barra de leitura, o grafico em
  destaque com as trilhas dos outros sinais, o minimapa da sessao e o
  painel lateral (eventos por tipo, qualidade do dado e as notas).

  O estado que eles dividem mora aqui, uma vez so:
  - a JANELA de tempo (o zoom): todos os graficos recebem o mesmo dominio
    X, e quem a muda e o minimapa, o painel e o `?t=`;
  - o SINAL EM DESTAQUE (rpm, velocidade, temperatura, tensao);
  - o CURSOR (indice da serie sob o mouse) e o PONTO FIXADO (A), que a
    barra de leitura le e a camada por cima dos graficos desenha;
  - a SELECAO do painel: um evento do motor ou um trecho de qualidade.

  O cursor NAO passa pelo Recharts: os graficos sao `memo` e nao o
  recebem, e a linha vertical, o valor e a faixa entre A e B sao HTML
  posicionado pelo tempo, numa camada por cima de todos. Mover o mouse
  re-renderiza esta camada e a barra de leitura, nunca as milhares de
  amostras. Para isso todos os graficos tem a area de desenho nas mesmas
  calhas (`CALHA_ESQ`/`CALHA_DIR`, em GraficoSessao.jsx).

  Mexe aqui quem mudar o que se faz com os graficos da Analise.
*/
import { memo, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { X } from "lucide-react";
import { Area, AreaChart, Brush, ResponsiveContainer, XAxis } from "recharts";
import { cronometro } from "../../formato.js";
import {
  ALTURA_DESENHO,
  ALTURA_DESTAQUE,
  CALHA_DIR,
  CALHA_ESQ,
  GraficoDestaque,
  GraficoTrilha,
  TOPO_DESENHO,
} from "./GraficoSessao.jsx";
import {
  diferencaDoSinal,
  eixoRedondo,
  intervalo,
  marcasDeEvento,
  resumoDoEvento,
  SINAIS,
  SINAL,
  TIPOS_DE_TRECHO,
  TIPOS_DO_MOTOR,
  TIPOS_EVENTO,
  valorDoSinal,
  zonasDeLimite,
} from "./graficoApoio.js";
import { PainelAnalise, resumoDoTrecho } from "./PainelAnalise.jsx";
import c from "../../estilos/comum.module.css";
import s from "./AnaliseGraficos.module.css";

// Ir a um evento (ou trecho) mostra este tanto de cada lado dele.
const MARGEM_ZOOM_S = 30;
// Janela minima do zoom: menos que isto sao poucas amostras a 1 Hz.
const JANELA_MINIMA_S = 20;
// Clicar a ate isto (px) do ponto fixado solta o ponto, em vez de move-lo.
const TOLERANCIA_SOLTAR_PX = 6;
// `?t=` sem `?evento=` (link antigo): o evento mais perto, ate isto.
const TOLERANCIA_FOCO_S = 2;

const COR_SINAL = { rpm: s.rpm, vss: s.vss, ect: s.ect, vbat: s.vbat };

/** Indice da amostra mais proxima de `t` (a serie esta em ordem de tempo). */
function maisProximo(serie, t) {
  if (!serie.length) return null;
  let lo = 0;
  let hi = serie.length - 1;
  while (hi - lo > 1) {
    const meio = (lo + hi) >> 1;
    if (serie[meio].t < t) lo = meio;
    else hi = meio;
  }
  return Math.abs(serie[lo].t - t) <= Math.abs(serie[hi].t - t) ? lo : hi;
}

/**
 * `foco`: {evento, t} do `?evento=` e `?t=` - abre com o evento escolhido
 * e o zoom no trecho. `notas`: o card de km e notas, que vai no painel.
 */
export function AnaliseGraficos({ serie, eventos, inicio, limites, trechos = [], foco = null, notas = null }) {
  const total = useMemo(
    () => (serie.length ? [serie[0].t, serie[serie.length - 1].t] : [0, 1]),
    [serie]
  );
  const [zoom, setZoom] = useState(null);
  // O Brush do Recharts guarda os indices por conta propria: quando o zoom
  // muda por fora (painel, `?t=`), ele e remontado com os novos.
  const [versaoBrush, setVersaoBrush] = useState(0);
  const janela = zoom || total;

  const [destaque, setDestaque] = useState("rpm");
  const [cursor, setCursor] = useState(null);
  const [fixado, setFixado] = useState(null);
  const [selecao, setSelecao] = useState(null);

  /* ------------------------------------------------ eventos e trechos */

  const marcas = useMemo(() => marcasDeEvento(eventos, inicio), [eventos, inicio]);
  const porTipo = useMemo(() => {
    const mapa = Object.fromEntries(TIPOS_DO_MOTOR.map((tipo) => [tipo, []]));
    for (const e of marcas) mapa[e.tipo]?.push(e);
    return mapa;
  }, [marcas]);
  const trechosPorTipo = useMemo(() => {
    const mapa = Object.fromEntries(TIPOS_DE_TRECHO.map(({ tipo }) => [tipo, []]));
    trechos.forEach((tr, i) => mapa[tr.tipo]?.push({ ...tr, i }));
    return mapa;
  }, [trechos]);

  const eventoSel = selecao?.grupo === "evento" ? porTipo[selecao.tipo]?.[selecao.indice] : null;
  const trechoSel = selecao?.grupo === "trecho" ? trechosPorTipo[selecao.tipo]?.[selecao.indice] : null;

  // Os pontos do grafico grande: so os eventos do sinal em destaque, na
  // altura do valor que o backend mediu no disparo.
  const eventosDoSinal = useMemo(
    () =>
      marcas
        .filter((e) => TIPOS_EVENTO[e.tipo].campo === destaque)
        .map((e) => ({ ...e, valor: e.valor ?? serie[maisProximo(serie, e.t)]?.[destaque] }))
        .filter((e) => e.valor !== null && e.valor !== undefined),
    [marcas, destaque, serie]
  );

  /* ------------------------------------------------------------ eixos */

  const eixos = useMemo(() => {
    const porCampo = {};
    for (const { campo } of SINAIS) {
      const valores = serie.map((linha) => linha[campo]).filter((v) => v !== null && v !== undefined);
      const extras = zonasDeLimite(campo, limites).map((z) => z.valor);
      // A trilha nao mostra limite: o eixo dela e so a faixa da serie, com
      // uma folga, para a forma da linha nao virar um traco reto.
      const lo = valores.length ? Math.min(...valores) : 0;
      const hi = valores.length ? Math.max(...valores) : 1;
      const folga = (hi - lo) * 0.08 || 1;
      porCampo[campo] = {
        temLeitura: valores.length > 0,
        trilha: [lo - folga, hi + folga],
        ...eixoRedondo(campo, valores, extras),
      };
    }
    return porCampo;
  }, [serie, limites]);
  const zonas = useMemo(() => zonasDeLimite(destaque, limites), [destaque, limites]);

  /* ------------------------------------------------------------- zoom */

  const zoomEm = useCallback(
    (de, ate) => {
      // Tudo dentro da sessao, sempre com o inicio antes do fim: um `?t=`
      // alem do fim (ou antes do inicio) cai na borda, e nao inverte a
      // janela.
      let a = Math.min(Math.max(total[0], de), total[1]);
      let b = Math.max(Math.min(total[1], ate), total[0]);
      if (b - a < JANELA_MINIMA_S) {
        const meio = (a + b) / 2;
        a = Math.max(total[0], Math.min(meio - JANELA_MINIMA_S / 2, total[1] - JANELA_MINIMA_S));
        b = Math.min(total[1], a + JANELA_MINIMA_S);
      }
      setZoom(a <= total[0] && b >= total[1] ? null : [a, b]);
      setVersaoBrush((v) => v + 1);
    },
    [total]
  );

  const verSessaoInteira = useCallback(() => {
    setZoom(null);
    setVersaoBrush((v) => v + 1);
  }, []);

  const mudarPeloMinimapa = useCallback(
    (de, ate) => setZoom(de <= total[0] && ate >= total[1] ? null : [de, ate]),
    [total]
  );

  /* ---------------------------------------------------------- selecao */

  function irPara(nova) {
    setSelecao(nova);
    if (nova.grupo === "evento") {
      const e = porTipo[nova.tipo][nova.indice];
      setDestaque(TIPOS_EVENTO[nova.tipo].campo);
      zoomEm(e.t - MARGEM_ZOOM_S, e.t + MARGEM_ZOOM_S);
    } else {
      const tr = trechosPorTipo[nova.tipo][nova.indice];
      zoomEm(tr.inicio_s - MARGEM_ZOOM_S, tr.fim_s + MARGEM_ZOOM_S);
    }
  }

  function escolherTipo(grupo, tipo) {
    if (selecao?.grupo === grupo && selecao?.tipo === tipo) setSelecao(null);
    else irPara({ grupo, tipo, indice: 0 });
  }

  function passar(delta) {
    if (!selecao) return;
    const lista = selecao.grupo === "evento" ? porTipo[selecao.tipo] : trechosPorTipo[selecao.tipo];
    const indice = selecao.indice + delta;
    if (indice >= 0 && indice < lista.length) irPara({ ...selecao, indice });
  }

  // Clicar num ponto do grafico escolhe o evento, sem mexer no zoom.
  const escolherNoGrafico = useCallback(
    (e) => {
      const indice = porTipo[e.tipo].findIndex((x) => x.id === e.id);
      if (indice >= 0) setSelecao({ grupo: "evento", tipo: e.tipo, indice });
    },
    [porTipo]
  );

  // Chegou com ?evento= (e ?t=), da lista de eventos da tela da sessao.
  // Evento de qualidade escolhe o trecho dele.
  useEffect(() => {
    if (!foco || !serie.length) return;
    let alvo = foco.evento !== null ? marcas.find((e) => e.id === foco.evento) : null;
    if (!alvo && foco.t !== null) {
      const perto = marcas.reduce(
        (melhor, e) => (!melhor || Math.abs(e.t - foco.t) < Math.abs(melhor.t - foco.t) ? e : melhor),
        null
      );
      if (perto && Math.abs(perto.t - foco.t) <= TOLERANCIA_FOCO_S) alvo = perto;
    }
    if (alvo && !TIPOS_EVENTO[alvo.tipo].qualidade) {
      irPara({ grupo: "evento", tipo: alvo.tipo, indice: porTipo[alvo.tipo].findIndex((e) => e.id === alvo.id) });
    } else if (alvo) {
      const lista = trechosPorTipo[alvo.tipo] || [];
      let indice = lista.findIndex((tr) => tr.inicio_s - 1 <= alvo.t && alvo.t <= tr.fim_s + 1);
      if (indice < 0 && lista.length) {
        indice = lista.reduce(
          (melhor, tr, i) => (Math.abs(tr.inicio_s - alvo.t) < Math.abs(lista[melhor].inicio_s - alvo.t) ? i : melhor),
          0
        );
      }
      if (indice >= 0) irPara({ grupo: "trecho", tipo: alvo.tipo, indice });
      else zoomEm(alvo.t - MARGEM_ZOOM_S, alvo.t + MARGEM_ZOOM_S);
    } else if (foco.t !== null) {
      zoomEm(foco.t - MARGEM_ZOOM_S, foco.t + MARGEM_ZOOM_S);
    }
    // So na chegada: depois, quem manda e a tela.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [serie.length]);

  /* ----------------------------------------------- cursor e ponto fixo */

  const pilha = useRef(null);
  const [largura, setLargura] = useState(0);
  useLayoutEffect(() => {
    const el = pilha.current;
    if (!el) return undefined;
    setLargura(el.getBoundingClientRect().width);
    const observador = new ResizeObserver(([entrada]) => setLargura(entrada.contentRect.width));
    observador.observe(el);
    return () => observador.disconnect();
  }, []);

  const larguraDesenho = Math.max(1, largura - CALHA_ESQ - CALHA_DIR);
  const xDe = (t) => CALHA_ESQ + ((t - janela[0]) / (janela[1] - janela[0])) * larguraDesenho;
  const naJanela = (i) => i !== null && serie[i] && serie[i].t >= janela[0] && serie[i].t <= janela[1];

  function indiceEm(clientX) {
    const caixa = pilha.current.getBoundingClientRect();
    const x = clientX - caixa.left;
    if (x < CALHA_ESQ || x > caixa.width - CALHA_DIR) return null;
    return maisProximo(serie, janela[0] + ((x - CALHA_ESQ) / larguraDesenho) * (janela[1] - janela[0]));
  }

  function clicar(ev) {
    const i = indiceEm(ev.clientX);
    if (i === null) return;
    const perto = fixado !== null && Math.abs(xDe(serie[i].t) - xDe(serie[fixado].t)) <= TOLERANCIA_SOLTAR_PX;
    setFixado(perto ? null : i);
  }

  // Esc solta o ponto fixado.
  useEffect(() => {
    if (fixado === null) return undefined;
    const aoTeclar = (ev) => {
      if (ev.key === "Escape") setFixado(null);
    };
    window.addEventListener("keydown", aoTeclar);
    return () => window.removeEventListener("keydown", aoTeclar);
  }, [fixado]);

  // O que a barra e as trilhas leem: o mouse, ou o ponto fixado sem ele.
  const lido = cursor ?? fixado;
  const outros = SINAIS.filter((x) => x.campo !== destaque);
  const eixo = eixos[destaque];

  return (
    <div className={s.analise}>
      <div className={s.colunas}>
        <div className={s.principal}>
          <BarraLeitura serie={serie} cursor={cursor} fixado={fixado} destaque={destaque} />

          <section className={`${c.card} ${s.cardGrafico}`} aria-label="Gráfico da sessão">
            <div className={s.cabecalho}>
              <div className={s.seletor} role="group" aria-label="Sinal em destaque">
                {SINAIS.map((x) => (
                  <button
                    key={x.campo}
                    type="button"
                    className={`${s.seletorItem} ${x.campo === destaque ? s.seletorAtivo : ""}`.trim()}
                    aria-pressed={x.campo === destaque}
                    onClick={() => setDestaque(x.campo)}
                  >
                    <span className={`${s.pontinho} ${COR_SINAL[x.campo]}`} aria-hidden="true" />
                    {x.nome}
                  </button>
                ))}
              </div>
              <Legenda zonas={zonas} campo={destaque} limites={limites} />
            </div>

            {(eventoSel || trechoSel) && (
              <div className={s.selecao}>
                {eventoSel ? (
                  <>
                    <strong className={s.selecaoTitulo}>{TIPOS_EVENTO[eventoSel.tipo].nome}</strong>
                    <span className={c.mono}>{cronometro(eventoSel.t)}</span>
                    <span>{resumoDoEvento(eventoSel)}</span>
                    {TIPOS_EVENTO[eventoSel.tipo].campo !== destaque && (
                      <span className={s.selecaoNota}>no gráfico de {SINAL[TIPOS_EVENTO[eventoSel.tipo].campo].nome}</span>
                    )}
                  </>
                ) : (
                  <>
                    <strong className={s.selecaoTitulo}>{TIPOS_EVENTO[trechoSel.tipo].nome}</strong>
                    <span>{resumoDoTrecho(trechoSel)}</span>
                  </>
                )}
                <button
                  type="button"
                  className={s.selecaoFechar}
                  onClick={() => setSelecao(null)}
                  aria-label="Limpar seleção"
                  title="Limpar seleção"
                >
                  <X size={16} aria-hidden="true" />
                </button>
              </div>
            )}

            <div
              ref={pilha}
              className={s.pilha}
              onMouseMove={(ev) => setCursor(indiceEm(ev.clientX))}
              onMouseLeave={() => setCursor(null)}
              onClick={clicar}
            >
              {eixo.temLeitura ? (
                <GraficoDestaque
                  dados={serie}
                  campo={destaque}
                  janela={janela}
                  eixo={eixo}
                  zonas={zonas}
                  eventos={eventosDoSinal}
                  selecionado={eventoSel?.id ?? null}
                  trechos={trechos}
                  trechoSelecionado={trechoSel?.i ?? null}
                  classe={COR_SINAL[destaque]}
                  aoEscolherEvento={escolherNoGrafico}
                />
              ) : (
                <p className={s.semLeitura} style={{ height: ALTURA_DESTAQUE }}>
                  {/* Sem amostra nenhuma so existe sessao que acabou de
                      comecar: encerrada com menos de 10 e descartada. */}
                  {serie.length === 0
                    ? "Ainda não chegou nenhuma amostra desta sessão. Volte a abrir a análise daqui a pouco."
                    : `Nenhuma amostra desta sessão trouxe leitura válida de ${SINAL[destaque].nome.toLowerCase()}.`}
                </p>
              )}

              <div className={s.trilhas}>
                {outros.map((x) => (
                  <div
                    key={x.campo}
                    className={s.trilhaLinha}
                    style={{ gridTemplateColumns: `${CALHA_ESQ}px minmax(0, 1fr) ${CALHA_DIR}px` }}
                  >
                    <button
                      type="button"
                      className={s.trilhaNome}
                      title={`Pôr ${x.nome.toLowerCase()} em destaque`}
                      onClick={(ev) => {
                        ev.stopPropagation();
                        setDestaque(x.campo);
                      }}
                    >
                      {x.nome}
                    </button>
                    <GraficoTrilha
                      dados={serie}
                      campo={x.campo}
                      janela={janela}
                      dominio={eixos[x.campo].trilha}
                      classe={COR_SINAL[x.campo]}
                    />
                    <span
                      className={`${s.trilhaValor} ${lido !== null && serie[lido][x.campo] === null ? s.semResposta : c.mono}`}
                    >
                      {lido === null ? "—" : valorDoSinal(x.campo, serie[lido][x.campo])}
                    </span>
                  </div>
                ))}
              </div>

              <Camada
                serie={serie}
                cursor={naJanela(cursor) ? cursor : null}
                fixado={naJanela(fixado) ? fixado : null}
                fixadoFora={fixado !== null && !naJanela(fixado) ? serie[fixado].t : null}
                xDe={xDe}
                largura={largura}
                destaque={destaque}
                eixo={eixo}
              />
            </div>
          </section>

          <Minimapa
            key={versaoBrush}
            serie={serie}
            janela={janela}
            total={total}
            comZoom={zoom !== null}
            marcas={marcas}
            aoMudar={mudarPeloMinimapa}
            aoVerTudo={verSessaoInteira}
          />
        </div>

        <aside className={s.painel} aria-label="Eventos, qualidade do dado e notas">
          <PainelAnalise
            porTipo={porTipo}
            trechosPorTipo={trechosPorTipo}
            selecao={selecao}
            eventoSel={eventoSel}
            trechoSel={trechoSel}
            aoEscolherTipo={escolherTipo}
            aoPassar={passar}
          />
          {notas}
        </aside>
      </div>
    </div>
  );
}

/* --------------------------------------------------------- barra de leitura */

/**
 * O instante e os quatro sinais lado a lado, sempre visivel. Com um ponto
 * fixado (A) e o mouse noutro instante (B): os dois horarios, a diferenca
 * de cada sinal e o tempo entre eles.
 */
function BarraLeitura({ serie, cursor, fixado, destaque }) {
  const comparando = fixado !== null && cursor !== null && cursor !== fixado;
  const ponto = cursor ?? fixado;
  const a = fixado !== null ? serie[fixado] : null;
  const b = ponto !== null ? serie[ponto] : null;

  let instante;
  if (comparando) {
    instante = (
      <>
        <span className={s.marcaA}>A</span> {cronometro(a.t)} → <span className={s.marcaB}>B</span> {cronometro(b.t)}
      </>
    );
  } else if (b) {
    instante = (
      <>
        {fixado !== null && cursor === null && <span className={s.marcaA}>A</span>} {cronometro(b.t)}
      </>
    );
  } else {
    instante = "--:--";
  }

  const dica = comparando
    ? null
    : fixado !== null
      ? "Esc ou clique em A para soltar"
      : "Clique no gráfico para fixar um ponto";

  return (
    <div className={s.leitura} aria-live="off">
      <span className={`${s.leituraInstante} ${c.mono}`}>{instante}</span>
      <span className={s.leituraValores}>
        {SINAIS.map(({ campo }) => {
          const texto = !b
            ? "—"
            : comparando
              ? diferencaDoSinal(campo, a[campo], b[campo])
              : valorDoSinal(campo, b[campo]);
          const ausente = texto === "sem resposta";
          return (
            <span
              key={campo}
              className={`${s.leituraValor} ${campo === destaque ? s.leituraDestaque : ""} ${ausente ? s.semResposta : c.mono}`}
            >
              <span className={`${s.pontinho} ${COR_SINAL[campo]}`} aria-hidden="true" />
              {texto}
            </span>
          );
        })}
        {comparando && <span className={`${s.leituraValor} ${s.leituraDelta} ${c.mono}`}>{(b.t < a.t ? "−" : "") + intervalo(b.t - a.t)}</span>}
      </span>
      {dica && <span className={s.leituraDica}>{dica}</span>}
    </div>
  );
}

/* ------------------------------------------------------------------ legenda */

/** Os limites fora do desenho: um quadradinho da cor da zona e o valor. */
function Legenda({ zonas, campo, limites }) {
  if (limites?.do_snapshot === false) {
    return <span className={s.legenda}>sem limites gravados nesta sessão</span>;
  }
  if (!zonas.length) return null;
  return (
    <span className={s.legenda}>
      {zonas.map((z) => (
        <span key={z.chave} className={s.legendaItem}>
          <span className={`${s.legendaCor} ${z.tom === "risco" ? s.zonaRisco : s.zonaAlerta}`} aria-hidden="true" />
          {z.rotulo} {z.abaixo ? "<" : "≥"}{" "}
          <span className={c.mono}>{valorDoSinal(campo, z.valor)}</span>
        </span>
      ))}
    </span>
  );
}

/* ------------------------------------------------------------------- camada */

/**
 * O que acompanha o mouse, desenhado em HTML por cima dos graficos: a
 * linha do cursor (B), a do ponto fixado (A), a faixa entre os dois no
 * grafico grande e o valor do sinal em destaque na calha direita.
 */
function Camada({ serie, cursor, fixado, fixadoFora, xDe, largura, destaque, eixo }) {
  if (!largura) return null;
  const [lo, hi] = eixo.dominio;
  const yDe = (v) => TOPO_DESENHO + (1 - (v - lo) / (hi - lo)) * ALTURA_DESENHO;
  const xA = fixado !== null ? xDe(serie[fixado].t) : null;
  const xB = cursor !== null && cursor !== fixado ? xDe(serie[cursor].t) : null;
  const lido = cursor ?? fixado;
  const valor = lido !== null ? serie[lido][destaque] : null;
  const temValor = valor !== null && valor !== undefined && eixo.temLeitura;

  return (
    <div className={s.camada} aria-hidden="true">
      {xA !== null && xB !== null && (
        <div
          className={s.faixaAB}
          style={{ left: Math.min(xA, xB), width: Math.abs(xB - xA), top: TOPO_DESENHO, height: ALTURA_DESENHO }}
        />
      )}
      {xA !== null && (
        <div className={`${s.linha} ${s.linhaFixada}`} style={{ left: xA }}>
          <span className={s.etiqueta}>A</span>
        </div>
      )}
      {xB !== null && (
        <div className={s.linha} style={{ left: xB }}>
          {fixado !== null && <span className={`${s.etiqueta} ${s.etiquetaB}`}>B</span>}
        </div>
      )}
      {fixadoFora !== null && (
        <span className={s.foraDaJanela}>A em {cronometro(fixadoFora)}, fora do trecho mostrado</span>
      )}
      {temValor && (
        <>
          <span
            className={`${s.cursorPonto} ${COR_SINAL[destaque]}`}
            style={{ left: xDe(serie[lido].t), top: yDe(valor) }}
          />
          <span
            className={`${s.valorCalha} ${c.mono}`}
            style={{ left: largura - CALHA_DIR + 8, top: Math.min(Math.max(yDe(valor), TOPO_DESENHO + 8), TOPO_DESENHO + ALTURA_DESENHO - 8) }}
          >
            {valorDoSinal(destaque, valor)}
          </span>
        </>
      )}
    </div>
  );
}

/* ----------------------------------------------------------------- minimapa */

const CLASSE_TOM = { risco: s.risco, alerta: s.alerta };

/**
 * A sessao inteira: o Brush do Recharts sobre o RPM, com os eventos do
 * motor como tracinhos em cima. Mexer nele muda a janela de todos.
 */
const Minimapa = memo(function Minimapa({ serie, janela, total, comZoom, marcas, aoMudar, aoVerTudo }) {
  const inicio = Math.max(0, serie.findIndex((linha) => linha.t >= janela[0]));
  let fim = serie.length - 1;
  while (fim > 0 && serie[fim].t > janela[1]) fim -= 1;

  // O Brush posiciona por INDICE, nao por tempo: o tracinho vai no indice
  // da amostra do evento, senao um buraco na serie o deslocaria.
  const tracos = marcas
    .filter((m) => !TIPOS_EVENTO[m.tipo].qualidade)
    .map((m) => ({ ...m, p: serie.length > 1 ? maisProximo(serie, m.t) / (serie.length - 1) : 0 }));

  return (
    <section className={`${c.card} ${c.cardGraficoBaixo} ${s.minimapa}`} aria-label="Sessão inteira">
      <div className={s.minimapaTopo}>
        <span className={s.minimapaRotulo}>
          {comZoom ? (
            <>
              Mostrando <span className={c.mono}>{cronometro(janela[0])} – {cronometro(janela[1])}</span> de{" "}
              <span className={c.mono}>{cronometro(total[1])}</span>
            </>
          ) : (
            <>Sessão inteira · arraste as bordas para dar zoom</>
          )}
        </span>
        <button type="button" className={`${c.botao} ${c.botaoCompacto}`} onClick={aoVerTudo} disabled={!comZoom}>
          Ver sessão inteira
        </button>
      </div>
      <div className={s.minimapaDesenho}>
        <div className={s.tracos} style={{ left: CALHA_ESQ, right: CALHA_DIR }} aria-hidden="true">
          {tracos.map((m) => (
            <span
              key={m.id}
              className={`${s.traco} ${CLASSE_TOM[TIPOS_EVENTO[m.tipo].tom]}`}
              style={{ left: `calc(4px + (100% - 8px) * ${m.p})` }}
            />
          ))}
        </div>
        <ResponsiveContainer width="100%" height={56}>
          <AreaChart data={serie} margin={{ top: 0, right: CALHA_DIR, bottom: 0, left: CALHA_ESQ }}>
            <XAxis dataKey="t" type="number" domain={total} hide />
            <Brush
              dataKey="t"
              height={44}
              y={10}
              travellerWidth={8}
              startIndex={inicio}
              endIndex={Math.max(fim, inicio)}
              tickFormatter={cronometro}
              className={s.brush}
              onChange={({ startIndex, endIndex }) => {
                if (startIndex === inicio && endIndex === fim) return;
                aoMudar(serie[startIndex].t, serie[endIndex].t);
              }}
            >
              <AreaChart data={serie}>
                <Area
                  type="linear"
                  dataKey="rpm"
                  className={s.panorama}
                  stroke="currentColor"
                  fill="currentColor"
                  isAnimationActive={false}
                  dot={false}
                  connectNulls={false}
                />
              </AreaChart>
            </Brush>
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
});
