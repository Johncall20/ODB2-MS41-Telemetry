/*
  Os limites de alerta da proxima sessao.

  Os limites sao da SESSAO: escolhidos no popup "Nova sessão", mandados no
  POST que inicia a gravacao e gravados so nela, sem edicao depois. Tres
  pontos de partida:

  - Última sessão: os da sessao mais recente do carro com limites
    gravados, por mais antiga que seja. Desabilitada quando nao ha.
  - Sugeridos: o ponto de partida do sistema.
  - Personalizar: vira input, a partir do que estava na tela - nunca em
    branco.

  As duas primeiras mostram os valores como TEXTO (rotulo, valor e
  unidade), e nao como input desabilitado: nao ha o que editar ali.

  A regra (positivos, marcha lenta < shift light < giro alto) e do
  backend: o 422 chega por campo e e escrito embaixo de cada input. Aqui
  nao se confere nada - duas fontes da verdade sairiam do ar uma da outra.
*/
import { useEffect, useState } from "react";
import { api } from "../../api.js";
import { CAMPOS_LIMITE } from "../../limites.js";
import { dataHora, milhar } from "../../formato.js";
import c from "../../estilos/comum.module.css";
import s from "./LimitesSessao.module.css";

export const ORIGENS = [
  { id: "ultima", rotulo: "Última sessão" },
  { id: "sugeridos", rotulo: "Sugeridos" },
  { id: "personalizar", rotulo: "Personalizar" },
];

/** Os seis campos de uma fonte, como texto editavel ("" quando falta). */
export function seis(fonte) {
  return Object.fromEntries(CAMPOS_LIMITE.map(({ id }) => [id, fonte?.[id] ?? ""]));
}

/** Os seis como numero, para o POST e a barra de giro. Vazio nao vai. */
export function numericos(valores) {
  return Object.fromEntries(
    Object.entries(valores || {})
      .filter(([, v]) => v !== "" && v !== null && v !== undefined)
      .map(([k, v]) => [k, Number(v)])
  );
}

/*
  `{ultima_sessao, sugeridos, quilometragem}` do carro, para a linha de
  limites do Ao vivo e para o popup. Recarrega ao trocar de carro e quando
  a gravacao comeca ou termina - a sessao que acabou pode ter virado a
  "ultima", e o km do carro pode ter mudado.
*/
export function useInicioSessao(veiculoId, gravando) {
  const [inicio, setInicio] = useState(null);
  // Sem o inicio, "Gravar sessão" fica desabilitado: a frase diz por que.
  const [erro, setErro] = useState("");

  useEffect(() => {
    setErro("");
    if (!veiculoId) {
      setInicio(null);
      return undefined;
    }
    let atual = true;
    api
      .lerInicioSessao(veiculoId)
      .then((r) => atual && setInicio(r))
      .catch((falha) => {
        if (!atual) return;
        setInicio(null);
        setErro(falha.message);
      });
    return () => {
      atual = false;
    };
  }, [veiculoId, gravando]);

  return { inicio, erro };
}

/**
 * De onde a proxima sessao parte, sem escolha de ninguem: a ultima sessao
 * se existir, senao os sugeridos. E o que o popup abre marcado e o que a
 * linha do Ao vivo resume antes de gravar.
 */
export function limitesDePartida(inicio) {
  if (!inicio) return null;
  const origem = inicio.ultima_sessao ? "ultima" : "sugeridos";
  return { origem, valores: seis(inicio.ultima_sessao || inicio.sugeridos) };
}

/** A secao "Limites de alerta" do popup. Controlada por quem usa. */
export function LimitesSessao({ inicio, origem, valores, erros, aoEscolherOrigem, aoMudar }) {
  const temUltima = Boolean(inicio?.ultima_sessao);
  const editavel = origem === "personalizar";

  const legenda = {
    ultima: temUltima && `Da sessão de ${dataHora(inicio.ultima_sessao.iniciada_em)}.`,
    sugeridos: temUltima
      ? "O ponto de partida do sistema, não o limite de nenhum carro."
      : "Este carro ainda não tem sessão com limites gravados; partindo dos sugeridos.",
    personalizar: "Ajuste os valores. Eles valem só para esta sessão e não mudam depois.",
  }[origem];

  return (
    <div className={s.secao}>
      <div className={s.seletor} role="radiogroup" aria-label="De onde vêm os limites">
        {ORIGENS.map(({ id, rotulo }) => {
          const desabilitada = id === "ultima" && !temUltima;
          return (
            <label
              key={id}
              className={`${s.opcao} ${origem === id ? s.opcaoAtiva : ""} ${
                desabilitada ? s.opcaoDesabilitada : ""
              }`.trim()}
              title={desabilitada ? "Este carro ainda não tem sessão com limites gravados." : undefined}
            >
              <input
                className={c.oculto}
                type="radio"
                name="origem-limites"
                value={id}
                checked={origem === id}
                disabled={desabilitada}
                onChange={() => aoEscolherOrigem(id)}
              />
              {rotulo}
            </label>
          );
        })}
      </div>
      <p className={s.legenda}>{legenda}</p>

      {editavel ? (
        <div className={s.grade}>
          {CAMPOS_LIMITE.map(({ id, rotulo, unidade, passo }) => (
            <label className={c.campo} key={id}>
              <span className={c.campoRotulo}>
                {rotulo} <span className={s.unidade}>{unidade}</span>
              </span>
              <input
                className={`${c.entrada} ${c.mono} ${erros[id] ? c.entradaInvalida : ""}`.trim()}
                type="number"
                step={passo}
                value={valores[id]}
                onChange={(e) => aoMudar(id, e.target.value)}
                aria-invalid={erros[id] ? true : undefined}
              />
              {erros[id] && <span className={c.campoErro}>{erros[id]}</span>}
            </label>
          ))}
        </div>
      ) : (
        <dl className={s.grade}>
          {CAMPOS_LIMITE.map(({ id, rotulo, unidade }) => (
            <div className={s.lido} key={id}>
              <dt className={c.campoRotulo}>{rotulo}</dt>
              <dd className={`${s.valorLido} ${c.mono}`}>
                {valores[id] === "" ? "—" : `${milhar(Number(valores[id]))} ${unidade}`}
              </dd>
              {erros[id] && <dd className={c.campoErro}>{erros[id]}</dd>}
            </div>
          ))}
        </dl>
      )}
    </div>
  );
}
