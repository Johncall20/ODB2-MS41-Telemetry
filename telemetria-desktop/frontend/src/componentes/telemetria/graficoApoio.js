/*
  O que os graficos da Analise precisam saber e nao e desenho: os sinais
  (nome, unidade, formato), os tipos de evento (nome, forma, tom, sinal), o
  eixo Y com marcas redondas, as zonas de limite e as linhas de limite do
  Ao vivo.

  Nada aqui e regra de negocio: os eventos (com valor, pico e duracao) e os
  trechos sem leitura vem prontos do backend, e os limites sao o snapshot
  da sessao. Isto so decide como mostrar.
*/
import { milhar, paraData } from "../../formato.js";
import { PARAMETROS } from "../../parametros.js";

/*
  Os sinais da Analise: todos os parametros do firmware (parametros.js),
  na ordem do seletor e da barra de leitura. Os quatro de sempre mantem o
  nome curto e o formato que a Analise ja usava - a tensao com uma casa,
  nao duas como no painel ao vivo.
*/
const NA_ANALISE = {
  rpm: { nome: "RPM", unidade: "rpm" },
  ect: { nome: "Temperatura" },
  vbat: { nome: "Tensão", casas: 1 },
};

export const SINAIS = PARAMETROS.map((p) => ({
  campo: p.chave,
  nome: p.rotulo,
  unidade: p.unidade,
  casas: p.casas,
  grupo: p.grupo,
  ...NA_ANALISE[p.chave],
}));

// Os que a Analise mostra sem escolha nenhuma: os quatro de antes dos extras.
export const SINAIS_PADRAO = ["rpm", "vss", "ect", "vbat"];

export const SINAL = Object.fromEntries(SINAIS.map((x) => [x.campo, x]));

// Sem "-0,0": a correcao de lambda oscila em volta do zero.
function numero(valor, casas) {
  return valor
    .toLocaleString("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas })
    .replace(/^-(0(,0+)?)$/, "$1");
}

/** "6.461 rpm", "13,8 V"; null e "sem resposta" - nunca um numero. */
export function valorDoSinal(campo, valor) {
  if (valor === null || valor === undefined) return "sem resposta";
  const { unidade, casas } = SINAL[campo];
  return `${numero(valor, casas)} ${unidade}`;
}

/** A diferenca B - A com sinal ("+2.100 rpm", "−0,3 V"). */
export function diferencaDoSinal(campo, a, b) {
  if (a === null || a === undefined || b === null || b === undefined) return "sem resposta";
  const { unidade, casas } = SINAL[campo];
  const fator = 10 ** casas;
  const d = Math.round((b - a) * fator) / fator;
  const sinal = d > 0 ? "+" : d < 0 ? "−" : "±";
  return `${sinal}${numero(Math.abs(d), casas)} ${unidade}`;
}

/** Intervalo curto e legivel: "2,1 s", "42 s", "4 min 12 s", "1 h 05 min". */
export function intervalo(segundos) {
  if (segundos === null || segundos === undefined) return "—";
  const s = Math.abs(segundos);
  if (s < 10) return `${numero(Math.round(s * 10) / 10, 1)} s`;
  if (s < 60) return `${Math.round(s)} s`;
  const total = Math.round(s);
  if (total < 3600) return `${Math.floor(total / 60)} min ${String(total % 60).padStart(2, "0")} s`;
  return `${Math.floor(total / 3600)} h ${String(Math.floor((total % 3600) / 60)).padStart(2, "0")} min`;
}

/*
  Cada tipo de evento: nome, forma do marcador e tom - a FONTE UNICA dos
  dois, tambem para a lista de eventos (Eventos.jsx), para a mesma cor
  querer dizer a mesma coisa no grafico e na lista. Vermelho e o que pode
  danificar o motor ou invalidar a gravacao; ambar, aviso. `campo`: o sinal
  em que o ponto do evento cai. `qualidade` sao os que falam do DADO, nao
  do motor: nao viram ponto - o trecho deles (os `trechos` do backend) e
  que aparece, com fundo neutro.
*/
export const TIPOS_EVENTO = {
  SHIFT_LIGHT: { nome: "Shift light", forma: "triangulo", tom: "alerta", campo: "rpm" },
  RPM_ALTO: { nome: "Giro acima do limite", forma: "losango", tom: "risco", campo: "rpm" },
  TEMP_ALTA: { nome: "Temperatura alta", forma: "circulo", tom: "risco", campo: "ect" },
  BATERIA_BAIXA: { nome: "Bateria baixa", forma: "quadrado", tom: "risco", campo: "vbat" },
  PERDA_CONEXAO: { nome: "Perda de conexão", forma: "xis", tom: "risco", qualidade: true },
  LEITURA_INCOMPLETA: { nome: "Leitura incompleta", forma: "xis", tom: "alerta", qualidade: true },
};

// Os tipos que viram ponto sobre a linha, na ordem do painel.
export const TIPOS_DO_MOTOR = Object.keys(TIPOS_EVENTO).filter((tipo) => !TIPOS_EVENTO[tipo].qualidade);

// Os trechos de qualidade, na ordem do painel, com o nome no plural.
export const TIPOS_DE_TRECHO = [
  { tipo: "LEITURA_INCOMPLETA", nome: "Trechos sem leitura" },
  { tipo: "PERDA_CONEXAO", nome: "Perdas de conexão" },
];

// Os de rotina so aparecem na lista, nunca no grafico.
export const NOMES_ROTINA = {
  INICIO_SESSAO: "Início da sessão",
  FIM_SESSAO: "Fim da sessão",
};

/** Nome e tom de qualquer tipo, para a lista de eventos e os graficos. */
export function tipoDeEvento(tipo) {
  if (TIPOS_EVENTO[tipo]) return TIPOS_EVENTO[tipo];
  return { nome: NOMES_ROTINA[tipo] || tipo, tom: "neutro" };
}

// Inicio e fim existem em toda sessao e nao dizem nada sobre o motor.
const ROTINA = new Set(["INICIO_SESSAO", "FIM_SESSAO"]);

/** Segundos desde o inicio da sessao, ou null. */
export function segundosDesde(quando, inicio) {
  const t0 = paraData(inicio)?.getTime();
  const t = paraData(quando)?.getTime();
  return t0 === undefined || t === undefined ? null : (t - t0) / 1000;
}

/**
 * Os eventos anomalos como posicao no eixo X (segundos desde o inicio),
 * em ordem de tempo. Os de rotina ficam de fora.
 */
export function marcasDeEvento(eventos, inicio) {
  return (eventos || [])
    .filter((e) => !ROTINA.has(e.tipo) && TIPOS_EVENTO[e.tipo])
    .map((e) => ({ ...e, t: segundosDesde(e.criado_em, inicio) }))
    .filter((e) => e.t !== null)
    .sort((a, b) => a.t - b.t);
}

/**
 * O resumo de um evento do motor: "5.888 rpm por 2,1 s · pico 6.012".
 * Valor, pico e duracao vem do backend; o que faltar some da frase.
 */
export function resumoDoEvento(evento) {
  const campo = TIPOS_EVENTO[evento.tipo]?.campo;
  if (!campo || evento.valor === null || evento.valor === undefined) return evento.mensagem;
  const { casas } = SINAL[campo];
  let frase = valorDoSinal(campo, evento.valor);
  if (evento.duracao_s !== null && evento.duracao_s !== undefined) frase += ` por ${intervalo(evento.duracao_s)}`;
  if (evento.pico !== null && evento.pico !== undefined && evento.pico !== evento.valor) {
    frase += ` · ${evento.tipo === "BATERIA_BAIXA" ? "mínima" : "pico"} ${numero(evento.pico, casas)}`;
  }
  return frase;
}

/*
  Eixo Y de cada campo: o passo das marcas e se o eixo parte do zero. RPM
  e velocidade partem do zero (a altura da linha e a grandeza); agua e
  bateria partem do multiplo abaixo do minimo, senao a faixa util ficaria
  espremida no alto do grafico. O passo e o menor: `eixoRedondo` dobra ou
  quintuplica quando a faixa pede.

  Knock, avanco e as integracoes de lambda nao partem do zero: ficam em
  volta dele, ou abaixo (o retardo de knock e negativo).
*/
const EIXOS = {
  rpm: { passo: 1000, desdeZero: true },
  vss: { passo: 20, desdeZero: true },
  ect: { passo: 20, desdeZero: false },
  vbat: { passo: 1, desdeZero: false },
  tps: { passo: 10, desdeZero: true },
  vanos: { passo: 10, desdeZero: true },
  iat: { passo: 10, desdeZero: false },
  load: { passo: 50, desdeZero: true },
  maf: { passo: 50, desdeZero: true },
  mafv: { passo: 0.5, desdeZero: true },
  iacv: { passo: 5, desdeZero: true },
  ign: { passo: 5, desdeZero: false },
  knock: { passo: 1, desdeZero: false },
  inj: { passo: 1, desdeZero: true },
  lam1: { passo: 0.1, desdeZero: true },
  lam2: { passo: 0.1, desdeZero: true },
  lint1: { passo: 2, desdeZero: false },
  lint2: { passo: 2, desdeZero: false },
};

// Mais intervalos que isto e o passo dobra (ou quintuplica): as marcas se
// encostariam.
const MAXIMO_INTERVALOS = 8;

/**
 * Dominio e marcas redondas do eixo Y, sobre a sessao INTEIRA (o zoom no
 * tempo nao reescala o valor). `extras` entram no dominio - os limites,
 * senao a zona do shift light poderia cair fora do desenho.
 */
export function eixoRedondo(campo, valores, extras = []) {
  const { passo: base, desdeZero } = EIXOS[campo] || { passo: 1, desdeZero: false };
  const todos = [...valores, ...extras];
  if (todos.length === 0) return { dominio: [0, base], marcas: [0, base] };
  const minimo = Math.min(...todos);
  const maximo = Math.max(...todos);

  let passo = base;
  for (const fator of [1, 2, 5, 10, 20, 50]) {
    passo = base * fator;
    const lo = desdeZero ? 0 : Math.floor(minimo / passo) * passo;
    const hi = Math.ceil(maximo / passo) * passo;
    if ((hi - lo) / passo <= MAXIMO_INTERVALOS) break;
  }
  const lo = desdeZero ? Math.min(0, Math.floor(minimo / passo) * passo) : Math.floor(minimo / passo) * passo;
  let hi = Math.ceil(maximo / passo) * passo;
  if (hi <= lo) hi = lo + passo;

  const marcas = [];
  // Arredonda para nao acumular erro de ponto flutuante (passo 1 V).
  for (let v = lo; v <= hi + passo / 1000; v += passo) marcas.push(Math.round(v * 1000) / 1000);
  return { dominio: [lo, hi], marcas };
}

/*
  As zonas de limite do grafico em destaque, do snapshot da sessao: acima
  do shift light em ambar fraco (ate o giro alto), acima do giro alto em
  vermelho fraco, acima da temperatura alta e abaixo da tensao baixa. Sem
  snapshot (sessao antiga), nenhuma: os sugeridos fariam parecer que eram
  os limites daquela gravacao.
*/
const ZONAS_DO_CAMPO = {
  rpm: [
    { chave: "shift_light_rpm", rotulo: "shift", tom: "alerta", ate: "rpm_alto" },
    { chave: "rpm_alto", rotulo: "giro alto", tom: "risco" },
  ],
  ect: [{ chave: "temp_alta_c", rotulo: "temp. alta", tom: "risco" }],
  vbat: [{ chave: "vbat_baixa", rotulo: "tensão baixa", tom: "risco", abaixo: true }],
};

/**
 * [{chave, rotulo, tom, valor, abaixo, ate}] do campo, ou [] sem snapshot.
 * `ate`: o valor onde a zona para (o shift light para no giro alto, que
 * tem a zona propria); sem ele, vai ate a borda do eixo.
 */
export function zonasDeLimite(campo, limites) {
  if (!limites || limites.do_snapshot === false) return [];
  return (ZONAS_DO_CAMPO[campo] || [])
    .filter((z) => typeof limites[z.chave] === "number")
    .map((z) => ({
      ...z,
      valor: limites[z.chave],
      ate: z.ate && typeof limites[z.ate] === "number" && limites[z.ate] > limites[z.chave] ? limites[z.ate] : null,
    }));
}

/*
  As linhas de limite do Traco do Ao vivo (a Analise usa as zonas).
  [chave, rotulo, onde vai o rotulo]: no RPM os dois limites ficam perto,
  entao o de baixo (shift) leva o rotulo por baixo e o de cima por cima.
*/
const LIMITES_DO_CAMPO = {
  rpm: [
    ["shift_light_rpm", "shift", "insideTopRight"],
    ["rpm_alto", "giro alto", "insideBottomRight"],
  ],
};

/** [{chave, valor, rotulo, posicao}] do campo, ou [] sem snapshot. */
export function linhasDeLimite(campo, limites, unidade = "") {
  if (!limites || limites.do_snapshot === false) return [];
  return (LIMITES_DO_CAMPO[campo] || [])
    .filter(([chave]) => typeof limites[chave] === "number")
    .map(([chave, rotulo, posicao]) => ({
      chave,
      posicao,
      valor: limites[chave],
      rotulo: `${rotulo} ${milhar(limites[chave])}${unidade ? ` ${unidade}` : ""}`,
    }));
}
