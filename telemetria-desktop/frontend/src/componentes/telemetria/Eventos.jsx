import { cronometro, paraData } from "../../formato.js";
import { Chip } from "../ui/Chip.jsx";
import s from "./Eventos.module.css";

/*
  Lista de eventos do painel (nodes 5:295 / 5:491). O horario e o tempo
  desde o inicio da sessao; fora de uma sessao, a hora do relogio.
*/

const NOMES = {
  INICIO_SESSAO: "Início da sessão",
  FIM_SESSAO: "Fim da sessão",
  SHIFT_LIGHT: "Shift light",
  RPM_ALTO: "Giro acima do limite",
  TEMP_ALTA: "Temperatura alta",
  BATERIA_BAIXA: "Bateria baixa",
  PERDA_CONEXAO: "Perda de conexão",
  LEITURA_INCOMPLETA: "Leitura incompleta",
};

// Vermelho para o que pode danificar o motor ou invalidar a gravacao;
// ambar para aviso; cinza para os marcos de rotina da sessao.
const GRAVES = new Set(["RPM_ALTO", "TEMP_ALTA", "BATERIA_BAIXA", "PERDA_CONEXAO"]);
const AVISOS = new Set(["SHIFT_LIGHT", "LEITURA_INCOMPLETA"]);

function marca(evento, inicioSessao) {
  const quando = paraData(evento.criado_em);
  if (!quando) return "";
  if (inicioSessao) {
    return cronometro((quando.getTime() - inicioSessao.getTime()) / 1000);
  }
  return quando.toLocaleTimeString("pt-BR", { hour12: false });
}

function tomDoChip(tipo) {
  if (GRAVES.has(tipo)) return "risco";
  if (AVISOS.has(tipo)) return "alerta";
  return "neutro";
}

const VAZIO_PADRAO =
  "Nada registrado. Os eventos passam a ser gravados quando você iniciar a sessão.";

export function Eventos({ eventos, iniciadaEm, vazio = VAZIO_PADRAO }) {
  const inicio = paraData(iniciadaEm);

  if (!eventos.length) {
    return <p className={s.vazio}>{vazio}</p>;
  }

  return (
    <ul className={s.eventos}>
      {eventos.map((e, i) => (
        <li key={i} className={s.evento}>
          <span className={s.marca}>{marca(e, inicio)}</span>
          <Chip tom={tomDoChip(e.tipo)}>{NOMES[e.tipo] || e.tipo}</Chip>
          <span className={s.msg}>{e.mensagem}</span>
        </li>
      ))}
    </ul>
  );
}
