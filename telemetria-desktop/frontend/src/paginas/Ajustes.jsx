/*
  Tela de Ajustes: os limites que o detector usa para criar eventos.

  Mexer num limite aqui nao afeta a gravacao em curso - a sessao ativa
  levou uma copia dos valores no inicio.
*/
import { useEffect, useMemo, useState } from "react";
import { useTelemetria } from "../hooks/useTelemetria.js";
import { api } from "../api.js";
import { Aviso } from "../componentes/ui/Aviso.jsx";
import c from "../estilos/comum.module.css";
import s from "./Ajustes.module.css";

/*
  Sem node no Figma. Os limites daqui so valem para a proxima sessao - a
  que esta gravando levou uma copia no inicio.
*/

const CAMPOS = [
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

/** Edicao dos limites que o detector usa para criar eventos. */
export function Ajustes() {
  const { status } = useTelemetria();
  const [salvos, setSalvos] = useState(null);
  const [campos, setCampos] = useState(null);
  const [erro, setErro] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const [salvou, setSalvou] = useState(false);

  useEffect(() => {
    api
      .lerLimites()
      .then((l) => {
        setSalvos(l);
        setCampos(l);
      })
      .catch((e) => setErro(String(e.message || e)));
  }, []);

  const alterado = useMemo(
    () =>
      Boolean(salvos && campos) &&
      CAMPOS.some(({ id }) => Number(campos[id]) !== Number(salvos[id])),
    [campos, salvos]
  );

  if (erro) return <Aviso>{erro}</Aviso>;
  if (!campos) return <p className={c.paginaVazia}>Carregando…</p>;

  const gravando = Boolean(status?.gravando);
  const shiftAcimaDoRisco = Number(campos.shift_light_rpm) >= Number(campos.rpm_alto);

  function mudar(id, valor) {
    setSalvou(false);
    setCampos((atual) => ({ ...atual, [id]: valor }));
  }

  async function salvar(e) {
    e.preventDefault();
    setErro("");
    setOcupado(true);
    try {
      // O PUT substitui a linha inteira, entao vao os quatro campos.
      const gravado = await api.gravarLimites({
        id: 1,
        shift_light_rpm: Number(campos.shift_light_rpm),
        rpm_alto: Number(campos.rpm_alto),
        temp_alta_c: Number(campos.temp_alta_c),
        vbat_baixa: Number(campos.vbat_baixa),
      });
      setSalvos(gravado);
      setCampos(gravado);
      setSalvou(true);
    } catch (erroSalvar) {
      setErro(String(erroSalvar.message || erroSalvar));
    } finally {
      setOcupado(false);
    }
  }

  return (
    <>
      <header className={c.paginaTopo}>
        <div>
          <h1 className={c.paginaTitulo}>Ajustes</h1>
          <p className={c.paginaSubtitulo}>Limites que decidem o que vira evento na gravação</p>
        </div>
      </header>

      {/*
        O gravador copia os limites uma vez, quando a sessao comeca. Mudar
        aqui no meio de uma gravacao nao muda a sessao em curso - e proposital,
        senao a regra de um trecho da sessao seria diferente da do outro - mas
        a tela precisa dizer, senao parece que o ajuste nao funcionou.
      */}
      {gravando && (
        <Aviso atencao>
          Há uma sessão gravando agora. Ela continua com os limites que estavam
          valendo quando começou; o que você salvar aqui vale da próxima em diante.
        </Aviso>
      )}

      <form className={c.formulario} onSubmit={salvar}>
        {CAMPOS.map(({ id, rotulo, unidade, passo, dica }) => (
          <label className={c.campo} key={id}>
            <span className={c.campoRotulo}>
              {rotulo} <span className={s.unidade}>{unidade}</span>
            </span>
            <input
              className={`${c.entrada} ${c.mono}`}
              type="number"
              step={passo}
              value={campos[id]}
              onChange={(e) => mudar(id, e.target.value)}
              required
            />
            <span className={s.dica}>{dica}</span>
          </label>
        ))}

        {shiftAcimaDoRisco && (
          <Aviso atencao className={c.formularioLargo}>
            O shift light está igual ou acima do giro alto. Os dois eventos vão
            disparar praticamente juntos.
          </Aviso>
        )}

        <p className={`${s.dica} ${c.formularioLargo}`}>
          Cada regra tem margem de rearme: depois de disparar, o evento só se
          repete quando o valor volta com folga para a faixa normal. É isso que
          evita centenas de linhas iguais numa sessão longa.
        </p>

        <div className={`${c.formularioAcoes} ${c.formularioLargo}`}>
          <button className={`${c.botao} ${c.botaoPrimario}`} type="submit" disabled={ocupado || !alterado}>
            {salvou && !alterado ? "Salvo" : "Salvar limites"}
          </button>
          <button
            className={c.botao}
            type="button"
            disabled={!alterado}
            onClick={() => {
              setCampos(salvos);
              setSalvou(false);
            }}
          >
            Descartar alterações
          </button>
        </div>
      </form>
    </>
  );
}
