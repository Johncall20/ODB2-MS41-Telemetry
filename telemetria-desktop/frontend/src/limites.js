/*
  Os seis limites como a interface os apresenta: rotulo, unidade, passo do
  input e a frase que explica para que serve cada um.

  So apresentacao. A regra - ordem entre eles, valor positivo - e do
  backend, e e ele que responde 422 com a frase de cada campo, que o
  popup "Nova sessao" do Ao vivo escreve embaixo do campo. Duplicar a checagem aqui
  criaria duas fontes da verdade que sairiam do ar uma da outra.

  A ordem da lista e a ordem da tela: a escada de giro primeiro, depois as
  temperaturas, depois a bateria.
*/

export const CAMPOS_LIMITE = [
  {
    id: "rpm_marcha_lenta",
    rotulo: "Marcha lenta",
    unidade: "rpm",
    passo: 50,
    dica: "Teto do giro em marcha lenta com o motor quente. Separa marcha lenta de motor em uso.",
  },
  {
    id: "shift_light_rpm",
    rotulo: "Shift light",
    unidade: "rpm",
    passo: 100,
    dica: "Giro em que o alerta de troca de marcha acende.",
  },
  {
    id: "rpm_alto",
    rotulo: "Giro alto",
    unidade: "rpm",
    passo: 100,
    dica: "Acima disso o giro entra na faixa de risco do motor.",
  },
  {
    id: "ect_operacao_c",
    rotulo: "Temperatura de operação",
    unidade: "°C",
    passo: 1,
    dica: "Onde o termostato estabiliza. É o alvo do tempo de aquecimento.",
  },
  {
    id: "temp_alta_c",
    rotulo: "Temperatura alta",
    unidade: "°C",
    passo: 1,
    dica: "Temperatura da água que dispara o alerta.",
  },
  {
    id: "vbat_baixa",
    rotulo: "Bateria baixa",
    unidade: "V",
    passo: 0.1,
    dica: "Abaixo disso a tensão vira alerta — alternador ou bateria.",
  },
];
