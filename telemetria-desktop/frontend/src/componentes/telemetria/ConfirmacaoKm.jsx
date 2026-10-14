/*
  Confirmacao de km menor que o atual do carro, mostrando os dois valores.

  O backend aceita km menor (troca de painel, correcao de digitacao): o
  aviso e so da tela, para o engano nao passar calado. Inline, e nao um
  confirm() do navegador, como a confirmacao de arquivar veiculo - precisa
  mostrar os dois numeros lado a lado. So na tela da sessao: no Ao vivo o
  aviso fica dentro do popup "Nova sessao", junto do campo de km.
*/
import { milhar } from "../../formato.js";
import c from "../../estilos/comum.module.css";
import s from "./ConfirmacaoKm.module.css";

export function ConfirmacaoKm({ km, atual, rotuloConfirmar, aoConfirmar, aoCancelar, ocupado }) {
  return (
    <div className={s.painel} role="alertdialog" aria-label="Confirmar quilometragem menor">
      <p className={s.pergunta}>
        A quilometragem informada é menor que a atual do carro.
      </p>
      <dl className={s.valores}>
        <div>
          <dt className={c.campoRotulo}>Informada</dt>
          <dd className={`${s.valor} ${c.mono}`}>{milhar(km)} km</dd>
        </div>
        <div>
          <dt className={c.campoRotulo}>Atual do carro</dt>
          <dd className={`${s.valor} ${c.mono}`}>{milhar(atual)} km</dd>
        </div>
      </dl>
      <p className={s.detalhe}>
        Pode ser troca de painel ou correção de um valor digitado errado. Confirmando,
        a quilometragem do carro passa a ser a informada.
      </p>
      <div className={s.botoes}>
        <button
          className={`${c.botao} ${c.botaoPrimario}`}
          type="button"
          onClick={aoConfirmar}
          disabled={ocupado}
        >
          {rotuloConfirmar}
        </button>
        <button className={c.botao} type="button" onClick={aoCancelar} disabled={ocupado}>
          Corrigir
        </button>
      </div>
    </div>
  );
}
