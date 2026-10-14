/**
 * Traco dos ultimos ciclos, em SVG puro. X e o indice da amostra, nao o
 * tempo - e uma faixa pequena, sem eixo. Ciclo com `valid` apagado vira
 * buraco no traco, nunca uma reta ligando os dois lados.
 *
 * `limites` ([{chave, valor, rotulo}]) sao linhas horizontais tracejadas,
 * com o rotulo na borda direita - no Ao vivo, os limites da sessao em
 * curso, ou os de partida antes de gravar. O teto sobe para caber neles.
 *
 * `parado` ("sem leitura há 8 s"): as amostras pararam de chegar. O traco
 * fica esmaecido, com a frase por cima - o ultimo trecho nao pode parecer
 * a leitura de agora.
 */
import s from "./Traco.module.css";

export function Traco({ historico, campo, teto, limites = [], classe = "", parado = null }) {
  const L = 600;
  const A = 120;
  const n = Math.max(historico.length, 2);
  // Limite acima do teto ficaria colado na borda de cima: o teto sobe.
  const topo = Math.max(teto, ...limites.map((l) => l.valor * 1.08));

  const y = (valor) => A - (Math.min(valor, topo) / topo) * (A - 6) - 3;
  const x = (i) => (i / (n - 1)) * L;

  const segmentos = [];
  let atual = [];
  historico.forEach((a, i) => {
    const ok = !(a.invalidos || []).includes(campo);
    if (ok) {
      atual.push([x(i), y(a[campo] ?? 0)]);
    } else if (atual.length) {
      segmentos.push(atual);
      atual = [];
    }
  });
  if (atual.length) segmentos.push(atual);

  return (
    <div className={`${s.caixa} ${classe} ${parado ? s.caixaParada : ""}`.trim()}>
      <svg
        className={s.traco}
        viewBox={`0 0 ${L} ${A}`}
        preserveAspectRatio="none"
        aria-hidden="true"
      >
        {limites.map((l) => (
          <line key={l.chave} className={s.limite} x1={0} x2={L} y1={y(l.valor)} y2={y(l.valor)} />
        ))}
        {segmentos.map((pontos, k) => (
          <g key={k}>
            {pontos.length > 1 && (
              <polygon
                className={s.area}
                points={[
                  `${pontos[0][0].toFixed(1)},${A}`,
                  ...pontos.map(([px, py]) => `${px.toFixed(1)},${py.toFixed(1)}`),
                  `${pontos[pontos.length - 1][0].toFixed(1)},${A}`,
                ].join(" ")}
              />
            )}
            <polyline
              className={s.linha}
              points={pontos.map(([px, py]) => `${px.toFixed(1)},${py.toFixed(1)}`).join(" ")}
            />
          </g>
        ))}
      </svg>
      {/* Rotulo em HTML: dentro do SVG esticado (preserveAspectRatio none)
          o texto sairia deformado. */}
      {limites.map((l) => (
        <span
          key={l.chave}
          // Mesmo lado do rotulo que a Analise usa (graficoApoio): "insideTop"
          // fica abaixo da linha, para dois limites proximos nao se encostarem.
          className={`${s.rotulo} ${l.posicao?.startsWith("insideTop") ? s.rotuloAbaixo : ""}`.trim()}
          style={{ top: `${(y(l.valor) / A) * 100}%` }}
        >
          {l.rotulo}
        </span>
      ))}
      {parado && <span className={s.aviso}>{parado}</span>}
    </div>
  );
}
