import { useEffect, useId, useRef, useState } from "react";
import { ChevronDown } from "lucide-react";
import c from "../../estilos/comum.module.css";
import s from "./FiltroPopover.module.css";

/**
 * Um grupo de filtro como botao que abre um painel. `exclusivo` decide a
 * forma: radio quando so um valor faz sentido, checkbox quando somam.
 * `children` entra no fim, para o que nao e opcao.
 *
 * O botao escreve "Rotulo · valor". Sem `resumo`, o valor sai das opcoes:
 * no exclusivo, o rotulo da escolhida ("Situação · Ativos"); no multiplo,
 * o rotulo da unica marcada ou a contagem, e nada quando nenhuma. Quem
 * passa `resumo` escreve o texto a mao (o "30 dias" do periodo).
 *
 * O destaque ambar quer dizer "o recorte nao e o padrao". Com `padrao`, e
 * isso ao pe da letra - o exclusivo pode mostrar "Ativos" sem acender. Sem
 * ele, acende quando ha resumo (ou marcado, no multiplo), como antes.
 *
 * `rotuloAcima={false}` tira o rotulo pequeno de cima: o botao ja diz o
 * mesmo, e as duas linhas liam "Situação / Situação". Ele continua como
 * nome do grupo para o leitor de tela.
 */
export function FiltroPopover({
  rotulo,
  opcoes,
  valor,
  onChange,
  exclusivo = false,
  resumo,
  padrao,
  rotuloAcima = true,
  children,
}) {
  const [aberto, setAberto] = useState(false);
  const caixa = useRef(null);
  const id = useId();

  const marcados = exclusivo ? [valor] : valor || [];
  const rotuloDe = (v) => opcoes.find((o) => o.valor === v)?.rotulo ?? "";

  let texto = resumo;
  if (texto === undefined) {
    if (exclusivo) texto = rotuloDe(valor);
    else if (marcados.length === 1) texto = rotuloDe(marcados[0]);
    else texto = marcados.length || "";
  }

  let ativo;
  if (padrao !== undefined) ativo = exclusivo ? valor !== padrao : marcados.length > 0;
  else if (resumo !== undefined) ativo = Boolean(resumo);
  else ativo = !exclusivo && marcados.length > 0;

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
      <span
        className={rotuloAcima ? c.rotuloFiltro : c.oculto}
        id={`${id}-rotulo`}
      >
        {rotulo}
      </span>
      <div className={s.caixa} ref={caixa}>
        <button
          type="button"
          className={`${c.botao} ${s.gatilho} ${ativo ? s.gatilhoAtivo : ""}`.trim()}
          onClick={() => setAberto((a) => !a)}
          aria-expanded={aberto}
          aria-haspopup="true"
        >
          <span className={s.gatilhoTexto}>
            {rotulo}
            {texto ? (
              <span className={ativo ? s.gatilhoResumo : s.gatilhoValor}> · {texto}</span>
            ) : null}
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
