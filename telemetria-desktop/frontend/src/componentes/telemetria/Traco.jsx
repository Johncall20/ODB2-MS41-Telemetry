/**
 * Traco dos ultimos ciclos, em SVG puro. X e o indice da amostra, nao o
 * tempo - e uma faixa pequena, sem eixo. Ciclo com `valid` apagado vira
 * buraco no traco, nunca uma reta ligando os dois lados.
 */
import s from "./Traco.module.css";

export function Traco({ historico, campo, teto, classe = "" }) {
  const L = 600;
  const A = 120;
  const n = Math.max(historico.length, 2);

  const y = (valor) => A - (Math.min(valor, teto) / teto) * (A - 6) - 3;
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
    <svg
      className={`${s.traco} ${classe}`}
      viewBox={`0 0 ${L} ${A}`}
      preserveAspectRatio="none"
      aria-hidden="true"
    >
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
  );
}
