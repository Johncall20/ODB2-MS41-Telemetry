/*
  Campo de quilometragem com separador de milhar. Controlado pelo NUMERO
  (ou null, "nao informado"): a tela nunca lida com o texto mascarado.

  Usado no formulario do veiculo, no Ao vivo antes de gravar e na tela da
  sessao. Nao valida nada alem de aceitar so digitos - quem recusa e o 422
  do backend, e a frase dele chega por `erro`.
*/
import { useId } from "react";
import { mascaraMilhar, numeroDeMilhar } from "../../formato.js";
import c from "../../estilos/comum.module.css";

export function CampoKm({ rotulo, valor, aoMudar, erro, dica, somenteLeitura, className }) {
  const id = useId();
  return (
    <label className={`${c.campo} ${className || ""}`.trim()} htmlFor={id}>
      <span className={c.campoRotulo}>
        {rotulo} <span className={c.celulaApagada}>km</span>
      </span>
      <input
        id={id}
        className={`${c.entrada} ${c.mono} ${erro ? c.entradaInvalida : ""}`.trim()}
        type="text"
        inputMode="numeric"
        value={mascaraMilhar(valor)}
        onChange={(e) => aoMudar?.(numeroDeMilhar(e.target.value))}
        readOnly={somenteLeitura}
        placeholder={somenteLeitura ? "não informado" : dica}
        aria-invalid={erro ? true : undefined}
      />
      {erro && <span className={c.campoErro}>{erro}</span>}
    </label>
  );
}
