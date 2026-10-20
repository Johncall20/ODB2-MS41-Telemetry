/**
 * Um card de leitura do painel (nodes 5:106 / 5:307).
 *
 * Com o bit de `valid` apagado o numero some, o rotulo diz "sem resposta"
 * e o card fica apagado - nunca o ultimo valor lido. `semLeitura` ("sem
 * leitura há 8 s") e o mesmo para a amostra que parou de chegar (socket
 * ou BLE caido): o numero velho nao fica na tela como se fosse de agora.
 */
import c from "../../estilos/comum.module.css";
import s from "./Leitura.module.css";

export function Leitura({ rotulo, valor, unidade, casas = 0, invalido, semLeitura, largo, children }) {
  const semNumero = valor === null || valor === undefined;
  const apagado = invalido || Boolean(semLeitura);
  // Agrupamento de milhar e virgula decimal, como no Figma ("2.940", "13,9").
  // Sem "-0,0": a correcao de lambda oscila em volta do zero.
  const texto =
    apagado || semNumero
      ? "––"
      : Number(valor)
          .toLocaleString("pt-BR", {
            minimumFractionDigits: casas,
            maximumFractionDigits: casas,
          })
          .replace(/^-(0(,0+)?)$/, "$1");

  return (
    <div
      className={`${c.card} ${largo ? s.largo : ""} ${apagado ? s.parado : ""}`.trim()}
    >
      <span className={c.cardRotulo}>
        {rotulo}
        {semLeitura ? (
          <span className={s.semLeitura}> · {semLeitura}</span>
        ) : (
          invalido && <span className={s.semResposta}> · sem resposta</span>
        )}
      </span>
      <span className={`${s.numero} ${c.mono}`}>
        {texto}
        {unidade && !apagado && <span className={s.unidade}>{unidade}</span>}
      </span>
      {children}
    </div>
  );
}

/**
 * Barra segmentada de giro (node 5:381): verde ate a troca, ambar ate o
 * limite, vermelho acima. Com o bit de rpm apagado nao acende nada - nao
 * pode sugerir giro que a central nao respondeu.
 */
export function BarraGiro({ rpm, invalido, teto = 7000, shift = 6200, alto = 6800 }) {
  const BLOCOS = 12;
  const acesos = invalido ? 0 : Math.round((Math.min(rpm || 0, teto) / teto) * BLOCOS);

  return (
    <div className={s.blocos} role="presentation">
      {Array.from({ length: BLOCOS }, (_, i) => {
        const giroDoBloco = ((i + 1) / BLOCOS) * teto;
        let faixa = "blocoVerde";
        if (giroDoBloco > alto) faixa = "blocoVermelho";
        else if (giroDoBloco > shift) faixa = "blocoAmbar";
        return (
          <span
            key={i}
            className={`${s.bloco} ${i < acesos ? s[faixa] : ""}`.trim()}
          />
        );
      })}
    </div>
  );
}
