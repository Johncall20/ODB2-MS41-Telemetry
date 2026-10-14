/*
  Os desenhos da Analise, em Recharts, e a serie que todos usam:

  - `GraficoDestaque`: o grafico grande do sinal escolhido, com as zonas de
    limite, os pontos dos eventos daquele sinal e os trechos sem leitura;
  - `GraficoTrilha`: a faixa baixa dos outros sinais, so a linha;
  - `MiniaturaSerie`: a previa da exportacao.

  Quem junta tudo (cursor, ponto fixado, zoom, painel) e o
  `AnaliseGraficos.jsx`; os sinais, os tipos de evento e o eixo ficam no
  `graficoApoio.js`.

  Os dois graficos da Analise sao `memo` e NAO recebem o cursor: ele e uma
  camada HTML por cima (AnaliseGraficos), e assim mover o mouse nao
  redesenha milhares de pontos a cada pixel. Para a camada cair no tempo
  certo, todos tem a area de desenho nas mesmas calhas laterais
  (`CALHA_ESQ`, `CALHA_DIR`).

  Mexe aqui quem mudar o desenho de um grafico da Analise.
*/
import { memo, useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ReferenceArea,
  ReferenceDot,
  ResponsiveContainer,
  XAxis,
  YAxis,
} from "recharts";
import { resumoDoEvento, TIPOS_EVENTO } from "./graficoApoio.js";
import { cronometro, milhar, paraData } from "../../formato.js";
import c from "../../estilos/comum.module.css";
import s from "./GraficoSessao.module.css";

// Os sete campos que o firmware publica. A serie carrega todos para os
// graficos poderem compartilhar um array so.
const CAMPOS = ["rpm", "ect", "iat", "vbat", "tps", "vanos", "vss"];

// Intervalo entre amostras acima do qual a linha quebra: o mesmo
// `DT_MAXIMO_S` (3 s) do backend, que faz desse buraco uma perda de conexao.
const BURACO_S = 3;

/**
 * Uma linha por amostra: tempo decorrido e cada campo nulo onde `valid`
 * estava apagado. Montada uma vez e passada a todos os graficos.
 *
 * Onde nenhuma amostra chegou por mais de `BURACO_S`, entra uma linha com
 * tudo nulo no meio do buraco (`buraco: true`): sem ela a linha ligaria
 * os dois lados, e o desenho inventaria a leitura que nao houve.
 */
export function serieDaSessao(amostras, inicio) {
  const t0 = paraData(inicio)?.getTime();
  const serie = [];
  for (const a of amostras || []) {
    const d = paraData(a.recebida_em);
    const linha = { t: d && t0 !== undefined ? (d.getTime() - t0) / 1000 : 0 };
    const invalidos = a.invalidos || [];
    for (const campo of CAMPOS) {
      linha[campo] = invalidos.includes(campo) ? null : a[campo];
    }
    const anterior = serie[serie.length - 1];
    if (anterior && linha.t - anterior.t > BURACO_S) {
      const vazio = { t: (anterior.t + linha.t) / 2, buraco: true };
      for (const campo of CAMPOS) vazio[campo] = null;
      serie.push(vazio);
    }
    serie.push(linha);
  }
  return serie;
}

/**
 * A serie sem eixo, tooltip nem Brush - a miniatura da previa de
 * exportacao. Campo sem leitura valida devolve null, para quem chama
 * escrever texto no lugar de uma faixa vazia.
 */
export function MiniaturaSerie({ dados, campo, altura = 54 }) {
  const temLeitura = (dados || []).some(
    (linha) => linha[campo] !== null && linha[campo] !== undefined
  );
  if (!temLeitura) return null;

  return (
    <div className={s.miniatura} style={{ height: altura }}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={dados} margin={{ top: 2, right: 0, bottom: 0, left: 0 }}>
          <XAxis dataKey="t" type="number" domain={["dataMin", "dataMax"]} hide />
          <YAxis hide />
          <Area
            type="linear"
            dataKey={campo}
            className={s.serie}
            stroke="currentColor"
            strokeWidth={1.2}
            fill="currentColor"
            isAnimationActive={false}
            dot={false}
            activeDot={false}
            connectNulls={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

/*
  A geometria que a camada do cursor precisa conhecer. A area de desenho
  de todo grafico da Analise vai de CALHA_ESQ ate a largura menos
  CALHA_DIR: no grafico grande a esquerda e o eixo Y; nas trilhas, o nome.
  A direita, o valor no cursor.
*/
export const CALHA_ESQ = 92;
export const CALHA_DIR = 92;
// O grafico grande: 300 px de desenho, a folga de cima e o eixo do tempo.
export const ALTURA_DESENHO = 300;
export const TOPO_DESENHO = 10;
const ALTURA_EIXO_X = 26;
export const ALTURA_DESTAQUE = TOPO_DESENHO + ALTURA_DESENHO + ALTURA_EIXO_X;
export const ALTURA_TRILHA = 40;

const CLASSE_TOM = { risco: s.risco, alerta: s.alerta, neutro: s.neutro };

/**
 * O grafico grande do sinal escolhido.
 *
 * - `janela`: o dominio X [de, ate], o zoom;
 * - `eixo`: dominio e marcas do Y (`eixoRedondo`), calculado por quem
 *   chama - a camada do cursor usa o mesmo para pôr o valor na altura certa;
 * - `zonas`: as zonas de limite (`zonasDeLimite`), tingidas;
 * - `eventos`: so os do sinal, com `t` e `valor`; o selecionado
 *   (`selecionado`, id) fica maior. Clicar num ponto chama
 *   `aoEscolherEvento` e NAO chega ao grafico - fixar o cursor e clicar
 *   fora dos pontos;
 * - `trechos`: onde a leitura falhou, fundo neutro; o `trechoSelecionado`
 *   (indice em `trechos`) mais marcado.
 */
export const GraficoDestaque = memo(function GraficoDestaque({
  dados,
  campo,
  janela,
  eixo,
  zonas,
  eventos,
  selecionado,
  trechos,
  trechoSelecionado,
  classe,
  aoEscolherEvento,
}) {
  const [dica, setDica] = useState(null);

  return (
    <div className={`${s.desenho} ${classe}`} style={{ height: ALTURA_DESTAQUE }} onMouseLeave={() => setDica(null)}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={dados} margin={{ top: TOPO_DESENHO, right: CALHA_DIR, bottom: 0, left: 0 }}>
          <CartesianGrid vertical={false} />
          <XAxis
            dataKey="t"
            type="number"
            // A janela do zoom; allowDataOverflow corta o que sai dela em
            // vez de esticar o dominio.
            domain={janela}
            allowDataOverflow
            tickFormatter={cronometro}
            tickMargin={8}
            minTickGap={48}
            height={ALTURA_EIXO_X}
          />
          <YAxis
            domain={eixo.dominio}
            ticks={eixo.marcas}
            interval={0}
            tickFormatter={milhar}
            tickMargin={8}
            width={CALHA_ESQ}
            allowDataOverflow
          />

          {/* Acima (ou abaixo) do limite: a faixa inteira, tingida. */}
          {zonas.map((z) => (
            <ReferenceArea
              key={z.chave}
              y1={z.abaixo ? eixo.dominio[0] : z.valor}
              y2={z.abaixo ? z.valor : z.ate ?? eixo.dominio[1]}
              ifOverflow="hidden"
              className={`${s.zona} ${CLASSE_TOM[z.tom]}`}
            />
          ))}

          {/* Leitura que falhou: fundo neutro no trecho. */}
          {trechos.map((tr, i) => (
            <ReferenceArea
              key={`tr-${i}`}
              x1={tr.inicio_s}
              x2={Math.max(tr.fim_s, tr.inicio_s + 0.5)}
              ifOverflow="hidden"
              className={`${s.trecho} ${i === trechoSelecionado ? s.trechoSelecionado : ""}`.trim()}
            />
          ))}

          <Area
            type="linear"
            dataKey={campo}
            className={s.serie}
            stroke="currentColor"
            strokeWidth={1.5}
            fill="currentColor"
            isAnimationActive={false}
            dot={false}
            activeDot={false}
            // Buraco na leitura e buraco no desenho.
            connectNulls={false}
          />

          {eventos.map((e) => (
            <ReferenceDot
              key={e.id}
              x={e.t}
              y={e.valor}
              r={8}
              ifOverflow="discard"
              shape={(p) => (
                <PontoEvento
                  cx={p.cx}
                  cy={p.cy}
                  evento={e}
                  selecionado={e.id === selecionado}
                  aoEntrar={() => setDica({ x: p.cx, y: p.cy, evento: e })}
                  aoSair={() => setDica(null)}
                  aoEscolher={() => aoEscolherEvento(e)}
                />
              )}
            />
          ))}
        </AreaChart>
      </ResponsiveContainer>

      {dica && (
        <div
          className={`${s.dica} ${dica.y < 110 ? s.dicaAbaixo : ""}`.trim()}
          style={{ left: dica.x, top: dica.y }}
          role="tooltip"
        >
          <strong className={s.dicaTitulo}>{TIPOS_EVENTO[dica.evento.tipo].nome}</strong>
          <span className={`${s.dicaLinha} ${c.mono}`}>{cronometro(dica.evento.t)}</span>
          <span className={s.dicaLinha}>{resumoDoEvento(dica.evento)}</span>
        </div>
      )}
    </div>
  );
});

function PontoEvento({ cx, cy, evento, selecionado, aoEntrar, aoSair, aoEscolher }) {
  const tipo = TIPOS_EVENTO[evento.tipo];
  if (!Number.isFinite(cx) || !Number.isFinite(cy)) return null;
  return (
    <g
      className={`${s.ponto} ${CLASSE_TOM[tipo.tom]} ${selecionado ? s.pontoSelecionado : ""}`.trim()}
      role="button"
      tabIndex={0}
      aria-label={`${tipo.nome} em ${cronometro(evento.t)}`}
      aria-pressed={selecionado}
      onMouseEnter={aoEntrar}
      onMouseLeave={aoSair}
      onFocus={aoEntrar}
      onBlur={aoSair}
      // O clique no ponto escolhe o evento e nao chega ao grafico, onde
      // fixaria o cursor.
      onClick={(ev) => {
        ev.stopPropagation();
        aoEscolher();
      }}
      onKeyDown={(ev) => {
        if (ev.key === "Enter" || ev.key === " ") {
          ev.preventDefault();
          aoEscolher();
        }
      }}
    >
      <circle cx={cx} cy={cy} r={12} className={s.alvo} />
      {selecionado && <circle cx={cx} cy={cy} r={12} className={s.anel} />}
      <Forma forma={tipo.forma} cx={cx} cy={cy} escala={selecionado ? 1.35 : 1} />
    </g>
  );
}

/** O desenho de cada tipo, centrado em (cx, cy). A cor vem do `color`. */
export function Forma({ forma, cx, cy, escala = 1 }) {
  const k = escala;
  switch (forma) {
    case "triangulo":
      return (
        <polygon
          className={s.forma}
          points={`${cx},${cy - 6 * k} ${cx + 6 * k},${cy + 5 * k} ${cx - 6 * k},${cy + 5 * k}`}
        />
      );
    case "losango":
      return (
        <polygon
          className={s.forma}
          points={`${cx},${cy - 7 * k} ${cx + 6 * k},${cy} ${cx},${cy + 7 * k} ${cx - 6 * k},${cy}`}
        />
      );
    case "quadrado":
      return <rect className={s.forma} x={cx - 5 * k} y={cy - 5 * k} width={10 * k} height={10 * k} />;
    case "xis":
      return (
        <path
          className={s.formaTraco}
          d={`M${cx - 5 * k},${cy - 5 * k} L${cx + 5 * k},${cy + 5 * k} M${cx + 5 * k},${cy - 5 * k} L${cx - 5 * k},${cy + 5 * k}`}
        />
      );
    default:
      return <circle className={s.forma} cx={cx} cy={cy} r={5.5 * k} />;
  }
}

/**
 * Uma trilha: so a linha do sinal, sem eixo, grade, evento nem limite. A
 * area de desenho ocupa o elemento inteiro - quem poe nome e valor nas
 * calhas e a linha da trilha, no AnaliseGraficos.
 */
export const GraficoTrilha = memo(function GraficoTrilha({ dados, campo, janela, dominio, classe }) {
  return (
    <div className={`${s.trilha} ${classe}`} style={{ height: ALTURA_TRILHA }}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={dados} margin={{ top: 3, right: 0, bottom: 3, left: 0 }}>
          <XAxis dataKey="t" type="number" domain={janela} allowDataOverflow hide />
          <YAxis domain={dominio} allowDataOverflow hide />
          <Area
            type="linear"
            dataKey={campo}
            className={s.serie}
            stroke="currentColor"
            strokeWidth={1.2}
            fill="currentColor"
            isAnimationActive={false}
            dot={false}
            activeDot={false}
            connectNulls={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
});
