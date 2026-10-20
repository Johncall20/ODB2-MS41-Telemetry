import { useEffect, useId, useRef, useState } from "react";
import { ChevronDown } from "lucide-react";
import { GRUPOS, PADRAO, PARAMETROS } from "../../parametros.js";
import c from "../../estilos/comum.module.css";
import s from "./SeletorParametros.module.css";

/**
 * Quais parametros a tela mostra: um botao que abre os parametros em
 * grupos, com atalhos para todos, nenhum e o padrao.
 *
 * Nao guarda estado: `selecionados` e as chaves marcadas, e `aoMudar`
 * recebe a lista nova inteira - quem decide onde ela mora e a pagina.
 * Mesmo comportamento do FiltroPopover: fecha no clique fora e no Esc,
 * devolvendo o foco ao botao.
 *
 * Serve ao Ao vivo e a Analise. `opcoes` ([{chave, rotulo, grupo}]) troca
 * os rotulos pelos da tela; `minimo` impede desmarcar abaixo dele (a
 * Analise precisa de um sinal em destaque); `compacto` e o botao baixo,
 * que abre para a direita - fica no comeco de uma linha.
 */
export function SeletorParametros({
  selecionados,
  aoMudar,
  rotulo = "Parâmetros",
  opcoes = PARAMETROS,
  padrao = PADRAO,
  minimo = 0,
  compacto = false,
}) {
  const [aberto, setAberto] = useState(false);
  const caixa = useRef(null);
  const id = useId();

  useEffect(() => {
    if (!aberto) return undefined;
    function aoClicar(evento) {
      if (!caixa.current?.contains(evento.target)) setAberto(false);
    }
    function aoTeclar(evento) {
      if (evento.key !== "Escape") return;
      setAberto(false);
      caixa.current?.querySelector("button")?.focus();
    }
    document.addEventListener("mousedown", aoClicar);
    document.addEventListener("keydown", aoTeclar);
    return () => {
      document.removeEventListener("mousedown", aoClicar);
      document.removeEventListener("keydown", aoTeclar);
    };
  }, [aberto]);

  function alternar(chave) {
    aoMudar(
      selecionados.includes(chave)
        ? selecionados.filter((k) => k !== chave)
        : [...selecionados, chave]
    );
  }

  const noMinimo = selecionados.length <= minimo;

  return (
    <div className={s.caixa} ref={caixa}>
      <button
        type="button"
        className={`${c.botao} ${s.gatilho} ${compacto ? s.gatilhoCompacto : ""}`.trim()}
        onClick={() => setAberto((a) => !a)}
        aria-expanded={aberto}
        aria-haspopup="true"
      >
        <span>
          {rotulo}
          <span className={s.contagem}>
            {" "}
            · {selecionados.length} de {opcoes.length}
          </span>
        </span>
        <ChevronDown className={aberto ? s.setaAberta : s.seta} size={18} aria-hidden="true" />
      </button>

      {aberto && (
        <div
          className={`${s.painel} ${compacto ? s.painelDireita : ""}`.trim()}
          role="group"
          aria-labelledby={`${id}-titulo`}
        >
          <span className={c.oculto} id={`${id}-titulo`}>
            {rotulo}
          </span>
          {GRUPOS.map((grupo) => (
            <fieldset key={grupo} className={s.grupo}>
              <legend className={s.grupoRotulo}>{grupo}</legend>
              <div className={s.opcoes}>
                {opcoes.filter((p) => p.grupo === grupo).map((p) => {
                  const marcado = selecionados.includes(p.chave);
                  return (
                    <label key={p.chave} className={s.opcao}>
                      <input
                        type="checkbox"
                        className={s.marca}
                        checked={marcado}
                        disabled={marcado && noMinimo}
                        onChange={() => alternar(p.chave)}
                      />
                      <span>{p.rotulo}</span>
                    </label>
                  );
                })}
              </div>
            </fieldset>
          ))}
          <div className={s.atalhos}>
            <button type="button" className={s.atalho} onClick={() => aoMudar(opcoes.map((p) => p.chave))}>
              Todos
            </button>
            {minimo === 0 && (
              <button type="button" className={s.atalho} onClick={() => aoMudar([])}>
                Nenhum
              </button>
            )}
            <button type="button" className={s.atalho} onClick={() => aoMudar(padrao)}>
              Padrão
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
