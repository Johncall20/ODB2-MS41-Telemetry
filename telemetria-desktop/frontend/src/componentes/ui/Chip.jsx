import s from "./Chip.module.css";

/**
 * Etiqueta de evento. `tom` decide a cor: neutro para marco de rotina,
 * alerta para aviso, risco para o que pode danificar o motor.
 */
export function Chip({ tom = "neutro", children }) {
  const cor = tom === "risco" ? s.risco : tom === "alerta" ? s.alerta : "";
  return <span className={`${s.chip} ${cor}`.trim()}>{children}</span>;
}

/** Fila horizontal de chips. */
export function Chips({ children }) {
  return <span className={s.chips}>{children}</span>;
}
