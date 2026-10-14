/*
  O card "Quilometragem e notas" de uma sessao gravada: os dois editaveis
  a qualquer momento, pelo PATCH. E o mesmo na tela da sessao e no painel
  da Analise.

  Quem mostra o card guarda a sessao; `aoSalvar` recebe a resposta do
  PATCH, e `aplicarEdicao` a poe no estado de quem chama.
*/
import { useState } from "react";
import { api } from "../../api.js";
import { CampoKm } from "../ui/CampoKm.jsx";
import { ConfirmacaoKm } from "./ConfirmacaoKm.jsx";
import { NotasSessao } from "./NotasSessao.jsx";
import c from "../../estilos/comum.module.css";
import s from "./KmENotas.module.css";

/**
 * O estado da tela (a resposta do GET da sessao) com o que o PATCH
 * devolveu: so os campos que mudaram, sem recarregar a sessao inteira,
 * que traz a serie de amostras.
 */
export function aplicarEdicao(atual, resposta) {
  return {
    ...atual,
    sessao: { ...atual.sessao, observacao: resposta.observacao, km: resposta.km },
    veiculo: atual.veiculo && { ...atual.veiculo, quilometragem: resposta.quilometragem_do_carro },
  };
}

/** O card. Estreito (o painel da Analise), o km fica em cima das notas. */
export function KmENotas({ sessao, kmDoCarro, maisRecente, aoSalvar, classe = "" }) {
  return (
    <section className={`${c.card} ${s.dados} ${classe}`.trim()} aria-label="Quilometragem e notas">
      <span className={c.cardRotulo}>Quilometragem e notas</span>
      <div className={s.dadosSessao}>
        <KmDaSessao sessao={sessao} kmDoCarro={kmDoCarro} maisRecente={maisRecente} aoSalvar={aoSalvar} />
        <NotasSessao
          salvo={sessao.observacao}
          aoSalvar={async (texto) => aoSalvar(await api.editarSessao(sessao.id, { observacao: texto }))}
        />
      </div>
    </section>
  );
}

/*
  O km da sessao, editavel depois de gravada. Se a sessao e a mais recente
  do carro, salvar leva o valor ao carro - e so ai um km menor que o atual
  pede confirmacao. Numa sessao antiga, um km menor e o esperado (o carro
  rodou depois dela), e perguntar toda vez seria ruido.
*/
function KmDaSessao({ sessao, kmDoCarro, maisRecente, aoSalvar }) {
  const [km, setKm] = useState(sessao.km ?? null);
  const [confirmando, setConfirmando] = useState(false);
  const [ocupado, setOcupado] = useState(false);
  const [erro, setErro] = useState("");

  const alterado = km !== (sessao.km ?? null);

  async function salvar(confirmado = false) {
    setErro("");
    if (!confirmado && maisRecente && km !== null && kmDoCarro !== null && km < kmDoCarro) {
      setConfirmando(true);
      return;
    }
    setConfirmando(false);
    setOcupado(true);
    try {
      aoSalvar(await api.editarSessao(sessao.id, { km }));
    } catch (falha) {
      setErro(falha.campos?.km || String(falha.message || falha));
    } finally {
      setOcupado(false);
    }
  }

  // Fragmento: o painel de confirmacao e outro item da grade, que ocupa a
  // linha inteira - na coluna estreita do km os dois valores nao cabem.
  return (
    <>
      <div className={s.km}>
        <CampoKm
          rotulo="Quilometragem"
          valor={km}
          aoMudar={(novo) => {
            setKm(novo);
            setConfirmando(false);
          }}
          erro={erro}
          dica="não informada"
        />
        <button
          className={`${c.botao} ${alterado ? c.botaoPrimario : ""}`.trim()}
          type="button"
          onClick={() => salvar()}
          disabled={!alterado || ocupado}
        >
          Salvar km
        </button>
      </div>
      {confirmando && (
        <div className={s.linhaInteira}>
          <ConfirmacaoKm
            km={km}
            atual={kmDoCarro}
            rotuloConfirmar="Salvar mesmo assim"
            aoConfirmar={() => salvar(true)}
            aoCancelar={() => setConfirmando(false)}
            ocupado={ocupado}
          />
        </div>
      )}
    </>
  );
}
