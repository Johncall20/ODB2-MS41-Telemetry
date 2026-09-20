/*
  Ajustes da conta. Por ora, so o papel.

  Trocar de papel **nao apaga nada**: os clientes continuam gravados e os
  carros continuam pendurados neles. Sair de Profissional para Particular
  so esconde a tela de Clientes e a coluna da lista - e voltar reencontra
  tudo. O aviso antes de confirmar diz isso com esses termos, em vez de
  sugerir perda.

  Sem node no Figma.
*/
import { useEffect, useState } from "react";
import { Users, User } from "lucide-react";
import { useAutenticacao } from "../hooks/useAutenticacao.js";
import { api } from "../api.js";
import { Aviso } from "../componentes/ui/Aviso.jsx";
import c from "../estilos/comum.module.css";
import s from "./Conta.module.css";

const PAPEIS = [
  {
    valor: "PROFISSIONAL",
    rotulo: "Profissional",
    descricao: "Atendo carros de clientes",
    Icone: Users,
  },
  {
    valor: "PARTICULAR",
    rotulo: "Particular",
    descricao: "Cuido do meu próprio carro",
    Icone: User,
  },
];

/** Ajustes da conta logada. */
export function Conta() {
  const { usuario, recarregar } = useAutenticacao();
  const [escolhido, setEscolhido] = useState(usuario?.papel || "PROFISSIONAL");
  const [clientes, setClientes] = useState(null);
  const [erro, setErro] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const [salvou, setSalvou] = useState(false);

  // Quantos clientes existem hoje - so para o aviso saber o que dizer.
  useEffect(() => {
    api
      .listarClientes()
      .then((lista) => setClientes(lista.length))
      .catch(() => setClientes(null));
  }, []);

  if (!usuario) return null;

  const mudou = escolhido !== usuario.papel;
  // O aviso so tem o que dizer quando ha cliente para esconder.
  const vaiEsconder =
    mudou && escolhido === "PARTICULAR" && (clientes ?? 0) > 0;

  async function salvar() {
    setErro("");
    setOcupado(true);
    try {
      await api.trocarPapel(escolhido);
      await recarregar();
      setSalvou(true);
    } catch (falha) {
      setErro(String(falha.message || falha));
    } finally {
      setOcupado(false);
    }
  }

  return (
    <>
      <header className={c.paginaTopo}>
        <div>
          <h1 className={c.paginaTitulo}>Conta</h1>
          <p className={c.paginaSubtitulo}>Como o app se comporta para você.</p>
        </div>
      </header>

      <p className={s.dados}>
        <strong>{usuario.nome}</strong> · {usuario.email}
      </p>

      {erro && <Aviso>{erro}</Aviso>}

      <fieldset style={{ border: 0, margin: 0, padding: 0, minWidth: 0 }}>
        <legend className={c.campoRotulo}>Como você usa</legend>
        <div className={s.cartoes}>
          {PAPEIS.map(({ valor, rotulo, descricao, Icone }) => (
            <label
              key={valor}
              className={`${s.cartao} ${escolhido === valor ? s.cartaoEscolhido : ""}`.trim()}
            >
              <input
                className={s.radio}
                type="radio"
                name="papel"
                value={valor}
                checked={escolhido === valor}
                onChange={() => {
                  setEscolhido(valor);
                  setSalvou(false);
                }}
              />
              <Icone className={s.icone} size={24} aria-hidden="true" />
              <span className={s.cartaoRotulo}>{rotulo}</span>
              <span className={s.cartaoDescricao}>{descricao}</span>
            </label>
          ))}
        </div>
      </fieldset>

      {vaiEsconder && (
        <Aviso atencao>
          Você tem {clientes} {clientes === 1 ? "cliente" : "clientes"} cadastrado
          {clientes === 1 ? "" : "s"}. Como Particular, a tela de Clientes e a
          coluna na lista de veículos somem — mas <strong>nada é apagado</strong>:
          os clientes continuam gravados, os carros continuam ligados a eles, e
          voltar para Profissional reencontra tudo.
        </Aviso>
      )}

      <div className={s.acoes}>
        <button
          className={`${c.botao} ${c.botaoPrimario}`}
          type="button"
          onClick={salvar}
          disabled={ocupado || !mudou}
        >
          {salvou && !mudou ? "Salvo" : "Salvar"}
        </button>
        <button
          className={c.botao}
          type="button"
          disabled={!mudou}
          onClick={() => {
            setEscolhido(usuario.papel);
            setSalvou(false);
          }}
        >
          Descartar alterações
        </button>
      </div>
    </>
  );
}
