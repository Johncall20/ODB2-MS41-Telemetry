/*
  O painel da Analise: os eventos do motor agrupados por tipo e a
  qualidade do dado (trechos sem leitura e perdas de conexao), cada tipo
  com a contagem e, escolhido, "N de M" com as setas que levam a cada
  ocorrencia. Quem guarda a selecao e faz o zoom e o AnaliseGraficos; aqui
  so se mostra e se avisa.
*/
import { ChevronLeft, ChevronRight } from "lucide-react";
import { cronometro } from "../../formato.js";
import { Forma } from "./GraficoSessao.jsx";
import {
  intervalo,
  resumoDoEvento,
  TIPOS_DE_TRECHO,
  TIPOS_DO_MOTOR,
  TIPOS_EVENTO,
} from "./graficoApoio.js";
import c from "../../estilos/comum.module.css";
import s from "./PainelAnalise.module.css";

const CLASSE_TOM = { risco: s.risco, alerta: s.alerta };

/** "02:13 – 02:21 · 8 s · sem resposta: rpm, tps". */
export function resumoDoTrecho(tr) {
  const faltou = tr.campos?.length ? `sem resposta: ${tr.campos.join(", ")}` : "nenhuma leitura chegou";
  return `${cronometro(tr.inicio_s)} – ${cronometro(tr.fim_s)} · ${intervalo(tr.fim_s - tr.inicio_s)} · ${faltou}`;
}

export function PainelAnalise({ porTipo, trechosPorTipo, selecao, eventoSel, trechoSel, aoEscolherTipo, aoPassar }) {
  const semEventos = TIPOS_DO_MOTOR.every((tipo) => porTipo[tipo].length === 0);
  return (
    <>
      <section className={`${c.card} ${s.bloco}`} aria-label="Eventos da sessão">
        <span className={c.cardRotulo}>Eventos</span>
        <ul className={s.tipos}>
          {TIPOS_DO_MOTOR.map((tipo) => (
            <Tipo
              key={tipo}
              nome={TIPOS_EVENTO[tipo].nome}
              icone={<Icone tipo={tipo} />}
              total={porTipo[tipo].length}
              escolhido={selecao?.grupo === "evento" && selecao.tipo === tipo}
              indice={selecao?.indice}
              aoEscolher={() => aoEscolherTipo("evento", tipo)}
              aoPassar={aoPassar}
            >
              {eventoSel && (
                <>
                  <span className={`${s.quando} ${c.mono}`}>{cronometro(eventoSel.t)}</span>
                  <span className={s.resumo}>{resumoDoEvento(eventoSel)}</span>
                </>
              )}
            </Tipo>
          ))}
        </ul>
        {semEventos && <p className={s.nota}>Nenhum evento do motor nesta sessão.</p>}
      </section>

      <section className={`${c.card} ${s.bloco}`} aria-label="Qualidade do dado">
        <span className={c.cardRotulo}>Qualidade do dado</span>
        <ul className={s.tipos}>
          {TIPOS_DE_TRECHO.map(({ tipo, nome }) => (
            <Tipo
              key={tipo}
              nome={nome}
              icone={<Icone tipo={tipo} />}
              total={trechosPorTipo[tipo].length}
              escolhido={selecao?.grupo === "trecho" && selecao.tipo === tipo}
              indice={selecao?.indice}
              aoEscolher={() => aoEscolherTipo("trecho", tipo)}
              aoPassar={aoPassar}
            >
              {trechoSel && <span className={s.resumo}>{resumoDoTrecho(trechoSel)}</span>}
            </Tipo>
          ))}
        </ul>
      </section>
    </>
  );
}

/**
 * Uma linha do painel. Zero ocorrencias: apagada e sem clique. Escolhida:
 * "N de M", as setas e o resumo da ocorrencia (`children`).
 */
function Tipo({ nome, icone, total, escolhido, indice, aoEscolher, aoPassar, children }) {
  return (
    <li className={`${s.tipo} ${escolhido ? s.tipoEscolhido : ""}`.trim()}>
      <button
        type="button"
        className={s.tipoBotao}
        onClick={aoEscolher}
        disabled={total === 0}
        aria-expanded={escolhido}
      >
        {icone}
        <span className={s.tipoNome}>{nome}</span>
        <span className={`${s.contagem} ${c.mono}`}>{total}</span>
      </button>
      {escolhido && (
        <div className={s.detalhe}>
          <div className={s.navegacao}>
            <button
              type="button"
              className={s.seta}
              onClick={() => aoPassar(-1)}
              disabled={indice <= 0}
              aria-label="Anterior"
            >
              <ChevronLeft size={18} aria-hidden="true" />
            </button>
            <span className={`${s.posicao} ${c.mono}`}>
              {indice + 1} de {total}
            </span>
            <button
              type="button"
              className={s.seta}
              onClick={() => aoPassar(1)}
              disabled={indice >= total - 1}
              aria-label="Próximo"
            >
              <ChevronRight size={18} aria-hidden="true" />
            </button>
          </div>
          {children}
        </div>
      )}
    </li>
  );
}

function Icone({ tipo }) {
  const { forma, tom } = TIPOS_EVENTO[tipo];
  return (
    <svg className={`${s.icone} ${CLASSE_TOM[tom]}`} viewBox="-9 -9 18 18" aria-hidden="true">
      <Forma forma={forma} cx={0} cy={0} />
    </svg>
  );
}
