/*
  Os parametros que o firmware publica, como a tela os mostra. Mexe aqui
  quem acrescentar parametro no firmware: a chave tem de ser a mesma do
  JSON (tabela kParams do .ino) e da coluna da Amostra no backend.

  A ordem e a dos cards no painel ao vivo, nao a dos bits - quem sabe que
  bit e de qual campo e o backend (modelos.BITS_PARAMETROS), e o que chega
  aqui e a lista `invalidos` ja decodificada.

  `casas` de temperatura e 0 porque o backend guarda ect e iat inteiros.
*/

export const GRUPOS = ["Motor", "Temperaturas", "Ignição", "Combustível", "Elétrica e veículo"];

export const PARAMETROS = [
  // Os sete do nucleo, os que o painel sempre mostrou.
  { chave: "rpm", rotulo: "RPM", unidade: "", casas: 0, grupo: "Motor" },
  { chave: "vss", rotulo: "Velocidade", unidade: "km/h", casas: 0, grupo: "Elétrica e veículo" },
  { chave: "ect", rotulo: "Temp. do motor", unidade: "°C", casas: 0, grupo: "Temperaturas" },
  { chave: "tps", rotulo: "TPS", unidade: "%", casas: 1, grupo: "Motor" },
  { chave: "vanos", rotulo: "VANOS", unidade: "°CRK", casas: 1, grupo: "Motor" },
  { chave: "iat", rotulo: "Temp. do ar", unidade: "°C", casas: 0, grupo: "Temperaturas" },
  { chave: "vbat", rotulo: "Bateria", unidade: "V", casas: 2, grupo: "Elétrica e veículo" },
  // Os extras da MS41. Firmware antigo nao manda: o card fica "sem resposta".
  { chave: "load", rotulo: "Carga", unidade: "mg/str", casas: 1, grupo: "Motor" },
  { chave: "maf", rotulo: "Fluxo de ar (MAF)", unidade: "kg/h", casas: 1, grupo: "Motor" },
  { chave: "mafv", rotulo: "Tensão MAF", unidade: "V", casas: 2, grupo: "Motor" },
  { chave: "iacv", rotulo: "IACV (lenta)", unidade: "%", casas: 1, grupo: "Motor" },
  { chave: "ign", rotulo: "Avanço de ignição", unidade: "°CRK", casas: 1, grupo: "Ignição" },
  { chave: "knock", rotulo: "Retardo de knock", unidade: "°CRK", casas: 1, grupo: "Ignição" },
  { chave: "inj", rotulo: "Tempo de injeção", unidade: "ms", casas: 2, grupo: "Combustível" },
  { chave: "lam1", rotulo: "Sonda lambda 1", unidade: "V", casas: 2, grupo: "Combustível" },
  { chave: "lam2", rotulo: "Sonda lambda 2", unidade: "V", casas: 2, grupo: "Combustível" },
  { chave: "lint1", rotulo: "Lambda int. 1", unidade: "%", casas: 1, grupo: "Combustível" },
  { chave: "lint2", rotulo: "Lambda int. 2", unidade: "%", casas: 1, grupo: "Combustível" },
];

// O que o painel mostra sem escolha nenhuma: o mesmo de antes dos extras.
export const PADRAO = ["rpm", "vss", "ect", "tps", "vanos", "iat", "vbat"];

const CHAVES = new Set(PARAMETROS.map((p) => p.chave));

/*
  A escolha mora na query (`?parametros=rpm,ect` no Ao vivo, `?sinais=` na
  Analise), como o carro: sem localStorage, e o link reabre a mesma tela.
  Sem o parametro, o padrao da tela; com ele vazio, nada - "nenhum" tambem
  e uma escolha.
*/
export function lerSelecao(texto, padrao = PADRAO) {
  if (texto === null || texto === undefined) return padrao;
  return texto.split(",").filter((chave) => CHAVES.has(chave));
}

/** O texto da query para a escolha, ou null quando ela e o padrao. */
export function escreverSelecao(chaves, padrao = PADRAO) {
  const ordenadas = PARAMETROS.map((p) => p.chave).filter((chave) => chaves.includes(chave));
  const igual = ordenadas.length === padrao.length && padrao.every((chave) => ordenadas.includes(chave));
  return igual ? null : ordenadas.join(",");
}
