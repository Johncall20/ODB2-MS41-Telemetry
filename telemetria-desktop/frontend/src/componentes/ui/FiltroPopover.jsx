import { useEffect, useId, useRef, useState } from "react";
import { ChevronDown } from "lucide-react";
import c from "../../estilos/comum.module.css";
import s from "./FiltroPopover.module.css";

/**
 * Um grupo de filtro como botao que abre um painel. `exclusivo` decide a
 * forma: radio quando so um valor faz sentido, checkbox quando somam.
 * `children` entra no fim, para o que nao e opcao.
 */
export function FiltroPopover({
  rotulo,
  opcoes,
  valor,
  onChange,
  exclusivo = false,
  resumo,
  children,
}) {
  const [aberto, setAberto] = useState(false);
  const caixa = useRef(null);
  const id = useId();

  const marcados = exclusivo ? [valor] : valor || [];

  useEffect(() => {
    if (!aberto) return undefined;
    function aoClicar(evento) {
      if (!caixa.current?.contains(evento.target)) setAberto(false);
    }
    function aoTeclar(evento) {
      if (evento.key !== "Escape") return;
      setAberto(false);
      // Devolve o foco para o botao: fechar com Esc nao pode largar o foco
      // no corpo da pagina, senao o Tab seguinte recomeca do topo.
      caixa.current?.querySelector("button")?.focus();
    }
    document.addEventListener("mousedown", aoClicar);
    document.addEventListener("keydown", aoTeclar);
    return () => {
      document.removeEventListener("mousedown", aoClicar);
      document.removeEventListener("keydown", aoTeclar);
    };
  }, [aberto]);

  return (
    <div className={c.grupoFiltro}>
      <span className={c.rotuloFiltro} id={`${id}-rotulo`}>
        {rotulo}
      </span>
      <div className={s.caixa} ref={caixa}>
        <button
          type="button"
          className={`${c.botao} ${s.gatilho} ${resumo ? s.gatilhoAtivo : ""}`.trim()}
          onClick={() => setAberto((a) => !a)}
          aria-expanded={aberto}
          aria-haspopup="true"
        >
          <span className={s.gatilhoTexto}>
            {rotulo}
            {resumo ? <span className={s.gatilhoResumo}> · {resumo}</span> : null}
          </span>
          <ChevronDown className={aberto ? s.setaAberta : s.seta} size={18} aria-hidden="true" />
        </button>

        {aberto && (
          <div className={s.painel} role="group" aria-labelledby={`${id}-rotulo`}>
            {opcoes.map((o) => (
              <label key={o.valor} className={s.opcao}>
                <input
                  type={exclusivo ? "radio" : "checkbox"}
                  name={exclusivo ? id : undefined}
                  className={s.marca}
                  checked={marcados.includes(o.valor)}
                  onChange={() => onChange(o.valor)}
                />
                <span className={s.opcaoRotulo}>{o.rotulo}</span>
              </label>
            ))}
            {children}
          </div>
        )}
      </div>
    </div>
  );
}
