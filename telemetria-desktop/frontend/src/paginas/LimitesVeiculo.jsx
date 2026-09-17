/*
  Os limites de alerta de UM carro. Nao ha limite global nem heranca: os
  seis valores sao deste veiculo e so dele.

  Mexer num limite aqui nao afeta a gravacao em curso - a sessao ativa
  levou um snapshot dos valores no inicio.
*/
import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { useTelemetria } from "../hooks/useTelemetria.js";
import { api } from "../api.js";
import { CAMPOS_LIMITE } from "../limites.js";
import { placa } from "../formato.js";
import { Aviso } from "../componentes/ui/Aviso.jsx";
import { Migalha } from "../componentes/ui/Migalha.jsx";
import c from "../estilos/comum.module.css";
import s from "./LimitesVeiculo.module.css";

/* Sem node no Figma. Chega pelo botao "Limites de alerta" do detalhe do
   carro, e pelo link do painel ao vivo. */

/** Edicao dos seis limites de alerta de um veiculo. */
export function LimitesVeiculo() {
  const { id } = useParams();
  const { status } = useTelemetria();

  const [veiculo, setVeiculo] = useState(null);
  const [salvos, setSalvos] = useState(null);
  const [campos, setCampos] = useState(null);
  const [sugeridos, setSugeridos] = useState(null);
  const [erro, setErro] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const [salvou, setSalvou] = useState(false);

  useEffect(() => {
    Promise.all([api.lerVeiculo(id), api.lerLimitesVeiculo(id), api.lerLimitesSugeridos()])
      .then(([dados, limites, ponto]) => {
        setVeiculo(dados.veiculo);
        setSalvos(limites);
        setCampos(limites);
        setSugeridos(ponto);
      })
      .catch((e) => setErro(String(e.message || e)));
  }, [id]);

  const alterado = useMemo(
    () =>
      Boolean(salvos && campos) &&
      CAMPOS_LIMITE.some(({ id: campo }) => Number(campos[campo]) !== Number(salvos[campo])),
    [campos, salvos]
  );

  const mudar = useCallback((campo, valor) => {
    setSalvou(false);
    setErro("");
    setCampos((atual) => ({ ...atual, [campo]: valor }));
  }, []);

  if (erro && !campos) return <Aviso>{erro}</Aviso>;
  if (!campos) return <p className={c.paginaVazia}>Carregando…</p>;

  const gravando = Boolean(status?.gravando);
  const desteCarro = gravando && String(status?.sessao?.veiculo_id) === String(id);
  const titulo = veiculo ? placa(veiculo.placa) || `${veiculo.marca} ${veiculo.modelo}` : "";

  async function salvar(e) {
    e.preventDefault();
    setErro("");
    setOcupado(true);
    try {
      // Os seis vao sempre: sem heranca, campo ausente nao teria de quem
      // ser completado no backend.
      const gravado = await api.gravarLimitesVeiculo(
        id,
        Object.fromEntries(CAMPOS_LIMITE.map(({ id: campo }) => [campo, Number(campos[campo])]))
      );
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
      <Migalha para={`/veiculos/${id}`}>{titulo || "Veículo"}</Migalha>

      <header className={c.paginaTopo}>
        <div>
          <h1 className={c.paginaTitulo}>Limites de alerta</h1>
          <p className={c.paginaSubtitulo}>
            Valem só para este veículo e decidem o que vira evento na gravação.
          </p>
        </div>
      </header>

      {/*
        O gravador copia os limites uma vez, quando a sessao comeca. Mudar
        aqui no meio de uma gravacao nao muda a sessao em curso - e proposital,
        senao a regra de um trecho da sessao seria diferente da do outro - mas
        a tela precisa dizer, senao parece que o ajuste nao funcionou.
      */}
      {desteCarro && (
        <Aviso atencao>
          Este veículo está gravando agora. A sessão continua com os limites que
          estavam valendo quando começou; o que você salvar aqui vale da próxima
          em diante.
        </Aviso>
      )}

      {erro && <Aviso>{erro}</Aviso>}

      <form className={c.formulario} onSubmit={salvar}>
        {CAMPOS_LIMITE.map(({ id: campo, rotulo, unidade, passo, dica }) => (
          <label className={c.campo} key={campo}>
            <span className={c.campoRotulo}>
              {rotulo} <span className={s.unidade}>{unidade}</span>
            </span>
            <input
              className={`${c.entrada} ${c.mono}`}
              type="number"
              step={passo}
              value={campos[campo]}
              onChange={(e) => mudar(campo, e.target.value)}
              required
            />
            <span className={s.dica}>{dica}</span>
          </label>
        ))}

        <p className={`${s.dica} ${c.formularioLargo}`}>
          Cada regra tem margem de rearme: depois de disparar, o evento só se
          repete quando o valor volta com folga para a faixa normal. É isso que
          evita centenas de linhas iguais numa sessão longa.
        </p>

        <div className={`${c.formularioAcoes} ${c.formularioLargo}`}>
          <button
            className={`${c.botao} ${c.botaoPrimario}`}
            type="submit"
            disabled={ocupado || !alterado}
          >
            {salvou && !alterado ? "Salvo" : "Salvar"}
          </button>
          {/*
            So preenche o formulario - nao grava. Salvar continua sendo um
            ato separado, senao o botao viraria "descartar o que eu ajustei"
            com um clique e sem volta.
          */}
          <button
            className={c.botao}
            type="button"
            disabled={!sugeridos}
            onClick={() => {
              setSalvou(false);
              setErro("");
              setCampos((atual) => ({ ...atual, ...sugeridos }));
            }}
          >
            Usar valores sugeridos
          </button>
          <button
            className={c.botao}
            type="button"
            disabled={!alterado}
            onClick={() => {
              setCampos(salvos);
              setSalvou(false);
              setErro("");
            }}
          >
            Descartar alterações
          </button>
        </div>
      </form>
    </>
  );
}
