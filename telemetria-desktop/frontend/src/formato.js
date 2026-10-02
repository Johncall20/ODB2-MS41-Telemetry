/*
  Formatacao de exibicao. Nada aqui calcula regra de negocio: pico, duracao
  e integridade chegam prontos do backend (exportador.resumo). Estas funcoes
  so decidem como o numero aparece na tela.
*/

const SEM_VALOR = "—";

/*
  O backend grava UTC mas o SQLite devolve datetime sem fuso, e o JS trata
  string ISO sem fuso como hora LOCAL. Marcar o Z explicitamente e o que
  evita a sessao de um minuto atras aparecer como "ha 3 horas".
*/
export function paraData(iso) {
  if (!iso) return null;
  const temFuso = /(Z|[+-]\d{2}:?\d{2})$/.test(iso);
  return new Date(temFuso ? iso : `${iso}Z`);
}

/*
  A placa e guardada normalizada (maiuscula, sem separador). O hifen so
  aparece na exibicao, e so no padrao antigo de tres letras e quatro
  numeros - a placa Mercosul (ABC1D23) se escreve sem separador.
*/
export function placa(valor) {
  if (!valor) return "";
  return /^[A-Z]{3}[0-9]{4}$/.test(valor) ? `${valor.slice(0, 3)}-${valor.slice(3)}` : valor;
}

/*
  O nome do dono do carro como a tela escreve. O cliente implicito e a
  propria conta: o nome dele seria o de quem esta olhando, entao a tela
  diz "Meus carros". O backend so marca o caso (`implicito`,
  `cliente_implicito`); o texto e daqui.
*/
export const MEUS_CARROS = "Meus carros";

export function nomeCliente(nome, implicito) {
  return implicito ? MEUS_CARROS : nome || "";
}

/** Numero no padrao brasileiro ("2.940"). Travessao quando nao ha valor. */
export function milhar(n) {
  if (n === null || n === undefined) return SEM_VALOR;
  return n.toLocaleString("pt-BR");
}

export function quilometragem(km) {
  // Zero aqui e quem nao preencheu, nao um carro com 0 km: devolve vazio
  // para o cartao dizer "nao informado".
  if (!km) return "";
  return `${milhar(km)} km`;
}

/** Data e hora curtas, para tabela e cabecalho ("09/09/2026 · 13:32"). */
export function dataHora(iso) {
  const d = paraData(iso);
  if (!d) return SEM_VALOR;
  const data = d.toLocaleDateString("pt-BR");
  const hora = d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
  return `${data} · ${hora}`;
}

/** Duracao por extenso ("01min 30s"), para leitura humana. */
export function duracao(segundos) {
  if (segundos === null || segundos === undefined) return SEM_VALOR;
  const total = Math.round(segundos);
  const min = Math.floor(total / 60);
  const seg = total % 60;
  return `${String(min).padStart(2, "0")}min ${String(seg).padStart(2, "0")}s`;
}

const ESCALA = [
  [60, "segundo", "segundos"],
  [60, "minuto", "minutos"],
  [24, "hora", "horas"],
  [7, "dia", "dias"],
  [4.35, "semana", "semanas"],
  [12, "mês", "meses"],
  [Infinity, "ano", "anos"],
];

/** Tempo relativo ("ha 3 dias"), para a coluna de ultima sessao.
 *  Diz de relance se o carro anda sendo usado, o que uma data nao diz. */
export function haQuantoTempo(iso) {
  const d = paraData(iso);
  if (!d) return null;
  let valor = (Date.now() - d.getTime()) / 1000;
  if (valor < 45) return "agora há pouco";
  for (const [divisor, singular, plural] of ESCALA) {
    if (valor < divisor) {
      const inteiro = Math.floor(valor);
      return `há ${inteiro} ${inteiro === 1 ? singular : plural}`;
    }
    valor /= divisor;
  }
  return null;
}

// O backend manda o TipoEvento cru ("SHIFT_LIGHT"); a tela precisa da
// frase em portugues. A traducao mora aqui para as varias telas que
// mostram evento nao escreverem cada uma a sua.
export const ROTULO_EVENTO = {
  SHIFT_LIGHT: "Shift light",
  RPM_ALTO: "RPM alto",
  TEMP_ALTA: "Temperatura alta",
  BATERIA_BAIXA: "Bateria baixa",
  PERDA_CONEXAO: "Perda de conexão",
  LEITURA_INCOMPLETA: "Leitura incompleta",
};

/** mm:ss ou h:mm:ss, para eixo de grafico e cronometro de gravacao.
 *  Curto de proposito: vai repetido embaixo do desenho. */
export function cronometro(segundos) {
  const total = Math.max(0, Math.floor(segundos));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  const mm = String(m).padStart(2, "0");
  const ss = String(s).padStart(2, "0");
  return h > 0 ? `${h}:${mm}:${ss}` : `${mm}:${ss}`;
}
