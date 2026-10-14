/*
  As notas da sessao (coluna `sessao.observacao`): texto livre, com quebra
  de linha, ate 2000 caracteres.

  Duas formas:

  - `CampoNotas`: so o campo, controlado por quem usa. E o do Ao vivo
    antes de gravar, onde as notas vao junto no POST que inicia.
  - `NotasSessao`: o campo com botao "Salvar notas" e a indicacao de
    alteracao nao salva. E o do Ao vivo durante a gravacao e o da tela da
    sessao - as notas se editam a qualquer momento, pelo PATCH.

  O contador e so aviso: quem recusa o que passa de 2000 e o backend, e a
  frase dele aparece embaixo do campo.
*/
import { useEffect, useId, useState } from "react";
import c from "../../estilos/comum.module.css";
import s from "./NotasSessao.module.css";

export const NOTAS_MAXIMO = 2000;

export function CampoNotas({ valor, aoMudar, erro, rotulo = "Notas", desabilitado }) {
  const id = useId();
  const tamanho = (valor || "").trim().length;
  return (
    <label className={c.campo} htmlFor={id}>
      <span className={s.topo}>
        <span className={c.campoRotulo}>{rotulo}</span>
        <span className={`${s.contador} ${tamanho > NOTAS_MAXIMO ? s.contadorPassou : ""}`.trim()}>
          {tamanho}/{NOTAS_MAXIMO}
        </span>
      </span>
      <textarea
        id={id}
        className={`${c.entrada} ${c.entradaArea} ${erro ? c.entradaInvalida : ""}`.trim()}
        value={valor || ""}
        onChange={(e) => aoMudar(e.target.value)}
        rows={4}
        placeholder="O que vale lembrar desta sessão: peça trocada, condição da pista, queixa do cliente…"
        disabled={desabilitado}
        aria-invalid={erro ? true : undefined}
      />
      {erro && <span className={c.campoErro}>{erro}</span>}
    </label>
  );
}

/**
 * Notas ja gravadas, com salvar explicito. `salvo` e o valor que esta no
 * banco; `aoSalvar(texto)` faz o PATCH e devolve a sessao atualizada.
 */
export function NotasSessao({ salvo, aoSalvar }) {
  const [rascunho, setRascunho] = useState(salvo || "");
  const [ocupado, setOcupado] = useState(false);
  const [erro, setErro] = useState("");
  const [acabouDeSalvar, setAcabouDeSalvar] = useState(false);

  // Chegou um valor novo de fora (outra aba, recarga do status): se nao ha
  // edicao pendente, acompanha.
  useEffect(() => {
    setRascunho((atual) => (atual.trim() === (salvo || "").trim() ? salvo || "" : atual));
  }, [salvo]);

  const alterado = rascunho.trim() !== (salvo || "").trim();

  async function salvar() {
    setErro("");
    setOcupado(true);
    try {
      await aoSalvar(rascunho);
      setAcabouDeSalvar(true);
    } catch (falha) {
      setErro(falha.campos?.observacao || String(falha.message || falha));
    } finally {
      setOcupado(false);
    }
  }

  return (
    <div className={s.bloco}>
      <CampoNotas
        valor={rascunho}
        aoMudar={(texto) => {
          setRascunho(texto);
          setAcabouDeSalvar(false);
        }}
        erro={erro}
      />
      <div className={s.acoes}>
        <button
          className={`${c.botao} ${alterado ? c.botaoPrimario : ""}`.trim()}
          type="button"
          onClick={salvar}
          disabled={!alterado || ocupado}
        >
          {ocupado ? "Salvando…" : "Salvar notas"}
        </button>
        {alterado ? (
          <span className={s.pendente} role="status">
            Alteração não salva
          </span>
        ) : (
          acabouDeSalvar && (
            <span className={s.salvo} role="status">
              Notas salvas
            </span>
          )
        )}
      </div>
    </div>
  );
}
