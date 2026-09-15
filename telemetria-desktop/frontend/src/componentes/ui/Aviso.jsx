import s from "./Aviso.module.css";

/**
 * Faixa de aviso. Vermelha por padrao (erro), ambar com `atencao`, para o
 * caso em que a tela informa uma condicao em vez de acusar falha.
 */
export function Aviso({ atencao, className = "", children }) {
  return (
    <p className={`${s.aviso} ${atencao ? s.atencao : ""} ${className}`.trim()}>
      {children}
    </p>
  );
}
