import { Link } from "react-router-dom";
import { cronometro, paraData } from "../../formato.js";
import { Chip } from "../ui/Chip.jsx";
// Nome e cor de cada tipo: a mesma fonte dos graficos da Analise.
import { tipoDeEvento } from "./graficoApoio.js";
import s from "./Eventos.module.css";

/*
  Lista de eventos do painel (nodes 5:295 / 5:491). O horario e o tempo
  desde o inicio da sessao; fora de uma sessao, a hora do relogio.
*/

function marca(evento, inicioSessao) {
  const quando = paraData(evento.criado_em);
  if (!quando) return "";
  if (inicioSessao) {
    return cronometro((quando.getTime() - inicioSessao.getTime()) / 1000);
  }
  return quando.toLocaleTimeString("pt-BR", { hour12: false });
}

const VAZIO_PADRAO =
  "Nada registrado. Os eventos passam a ser gravados quando você iniciar a sessão.";

/**
 * Lista de eventos. `destino(evento)`, opcional, faz de cada item um link
 * (a tela da sessao leva a Analise com `?evento=` e `?t=`).
 */
export function Eventos({ eventos, iniciadaEm, vazio = VAZIO_PADRAO, destino }) {
  const inicio = paraData(iniciadaEm);

  if (!eventos.length) {
    return <p className={s.vazio}>{vazio}</p>;
  }

  return (
    <ul className={s.eventos}>
      {eventos.map((e, i) => {
        const conteudo = (
          <>
            <span className={s.marca}>{marca(e, inicio)}</span>
            <Chip tom={tipoDeEvento(e.tipo).tom}>{tipoDeEvento(e.tipo).nome}</Chip>
            <span className={s.msg}>{e.mensagem}</span>
          </>
        );
        return (
          <li key={i} className={s.evento}>
            {destino ? (
              <Link className={s.acao} to={destino(e)} title="Ver este trecho na análise">
                {conteudo}
              </Link>
            ) : (
              <div className={s.linha}>{conteudo}</div>
            )}
          </li>
        );
      })}
    </ul>
  );
}
