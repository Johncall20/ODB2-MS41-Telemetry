/*
  Ajustes da conta: perfil, senha, papel e a exclusao da conta.

  Cada bloco salva sozinho e mostra o proprio erro: trocar a senha nao
  deveria depender de o nome estar valido, e o erro de um bloco aparecendo
  em outro mandaria a pessoa corrigir o campo errado.

  Trocar de papel **nao apaga nada**: os clientes continuam gravados e os
  carros continuam pendurados neles. Sair de Profissional para Particular
  so esconde a tela de Clientes e a coluna da lista - e voltar reencontra
  tudo. O aviso antes de confirmar diz isso com esses termos, em vez de
  sugerir perda.

  Excluir a conta, ao contrario, apaga de verdade (ver "Exclusao de conta"
  no CLAUDE.md). O bloco diz o que vai sumir, em numeros, e pede a senha e
  o proprio e-mail.

  Sem node no Figma.
*/
import { useEffect, useState } from "react";
import { Users, User } from "lucide-react";
import { useAutenticacao } from "../hooks/useAutenticacao.js";
import { api } from "../api.js";
import { milhar } from "../formato.js";
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
  const { usuario } = useAutenticacao();
  if (!usuario) return null;

  return (
    <>
      <header className={c.paginaTopo}>
        <div>
          <h1 className={c.paginaTitulo}>Conta</h1>
          <p className={c.paginaSubtitulo}>
            {usuario.nome} · {usuario.email}
          </p>
        </div>
      </header>

      <Perfil />
      <Senha />
      <Papel />
      <Exclusao />
    </>
  );
}

/** Mesmo esqueleto de erro e ocupado para os quatro blocos. */
function useEnvio() {
  const [erro, setErro] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const [feito, setFeito] = useState("");

  async function enviar(fazer, mensagem) {
    setErro("");
    setFeito("");
    setOcupado(true);
    try {
      await fazer();
      if (mensagem) setFeito(mensagem);
    } catch (falha) {
      setErro(String(falha.message || falha));
    } finally {
      setOcupado(false);
    }
  }

  return { erro, ocupado, feito, enviar, setFeito };
}

function Perfil() {
  const { usuario, recarregar } = useAutenticacao();
  const [nome, setNome] = useState(usuario.nome);
  const [email, setEmail] = useState(usuario.email);
  const [senha, setSenha] = useState("");
  const { erro, ocupado, feito, enviar, setFeito } = useEnvio();

  // Trocar o e-mail e trocar o que entra no login: pede a senha atual. O
  // campo so aparece quando o e-mail mudou - nome sozinho nao exige.
  const trocaEmail = email.trim().toLowerCase() !== usuario.email;
  const mudou = nome.trim() !== usuario.nome || trocaEmail;

  function salvar(e) {
    e.preventDefault();
    enviar(async () => {
      await api.editarPerfil({ nome, email, senha_atual: trocaEmail ? senha : "" });
      setSenha("");
      // A sidebar le o nome do provider: recarregar e o que a atualiza.
      await recarregar();
    }, "Perfil salvo.");
  }

  return (
    <section className={s.secao}>
      <h2 className={s.secaoTitulo}>Perfil</h2>
      <form className={s.campos} onSubmit={salvar}>
        <label className={c.campo}>
          <span className={c.campoRotulo}>Nome</span>
          <input
            className={c.entrada}
            value={nome}
            onChange={(e) => {
              setNome(e.target.value);
              setFeito("");
            }}
            required
          />
        </label>
        <label className={c.campo}>
          <span className={c.campoRotulo}>E-mail</span>
          <input
            className={c.entrada}
            type="email"
            value={email}
            onChange={(e) => {
              setEmail(e.target.value);
              setFeito("");
            }}
            required
          />
        </label>
        {trocaEmail && (
          <label className={c.campo}>
            <span className={c.campoRotulo}>Senha atual</span>
            <input
              className={c.entrada}
              type="password"
              value={senha}
              onChange={(e) => setSenha(e.target.value)}
              autoComplete="current-password"
              required
            />
            <span className={s.dica}>Trocar o e-mail pede a senha atual.</span>
          </label>
        )}
        {erro && <Aviso>{erro}</Aviso>}
        {feito && <p className={s.feito}>{feito}</p>}
        <div className={s.acoes}>
          <button
            className={`${c.botao} ${c.botaoPrimario}`}
            type="submit"
            disabled={ocupado || !mudou || !nome.trim()}
          >
            Salvar perfil
          </button>
        </div>
      </form>
    </section>
  );
}

function Senha() {
  const [atual, setAtual] = useState("");
  const [nova, setNova] = useState("");
  const [repetida, setRepetida] = useState("");
  const { erro, ocupado, feito, enviar } = useEnvio();

  // Conferir a repeticao e so da tela: serve para pegar erro de digitacao,
  // e o backend nao tem o que fazer com ela. O tamanho minimo, esse, e
  // regra, e mora no backend.
  const naoBate = repetida !== "" && repetida !== nova;

  function salvar(e) {
    e.preventDefault();
    enviar(async () => {
      await api.trocarSenha({ senha_atual: atual, senha_nova: nova });
      setAtual("");
      setNova("");
      setRepetida("");
    }, "Senha trocada. Os outros navegadores em que a conta estava aberta foram desconectados.");
  }

  return (
    <section className={s.secao}>
      <h2 className={s.secaoTitulo}>Senha</h2>
      <form className={s.campos} onSubmit={salvar}>
        <label className={c.campo}>
          <span className={c.campoRotulo}>Senha atual</span>
          <input
            className={c.entrada}
            type="password"
            value={atual}
            onChange={(e) => setAtual(e.target.value)}
            autoComplete="current-password"
            required
          />
        </label>
        <label className={c.campo}>
          <span className={c.campoRotulo}>Nova senha</span>
          <input
            className={c.entrada}
            type="password"
            value={nova}
            onChange={(e) => setNova(e.target.value)}
            autoComplete="new-password"
            required
          />
        </label>
        <label className={c.campo}>
          <span className={c.campoRotulo}>Repita a nova senha</span>
          <input
            className={c.entrada}
            type="password"
            value={repetida}
            onChange={(e) => setRepetida(e.target.value)}
            autoComplete="new-password"
            required
          />
          {naoBate && <span className={s.dica}>As duas senhas novas não são iguais.</span>}
        </label>
        {erro && <Aviso>{erro}</Aviso>}
        {feito && <p className={s.feito}>{feito}</p>}
        <div className={s.acoes}>
          <button
            className={`${c.botao} ${c.botaoPrimario}`}
            type="submit"
            disabled={ocupado || !atual || !nova || repetida !== nova}
          >
            Trocar senha
          </button>
        </div>
      </form>
    </section>
  );
}

function Papel() {
  const { usuario, recarregar } = useAutenticacao();
  const [escolhido, setEscolhido] = useState(usuario.papel);
  const [clientes, setClientes] = useState(null);
  const [erroClientes, setErroClientes] = useState("");
  const [salvou, setSalvou] = useState(false);
  const { erro, ocupado, enviar } = useEnvio();

  // Quantos clientes existem hoje - so para o aviso saber o que dizer.
  useEffect(() => {
    api
      .listarClientes()
      .then((lista) => setClientes(lista.length))
      .catch((falha) => setErroClientes(falha.message));
  }, []);

  const mudou = escolhido !== usuario.papel;
  // O aviso so tem o que dizer quando ha cliente para esconder.
  const vaiEsconder = mudou && escolhido === "PARTICULAR" && (clientes ?? 0) > 0;

  function salvar() {
    enviar(async () => {
      await api.trocarPapel(escolhido);
      await recarregar();
      setSalvou(true);
    });
  }

  return (
    <section className={s.secao}>
      <h2 className={s.secaoTitulo}>Como você usa</h2>
      <fieldset className={s.grupo}>
        <legend className={c.oculto}>Papel da conta</legend>
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
      {/* Sem a contagem, o aviso de clientes que somem nao tem como sair: a
          tela diz isso em vez de trocar de papel calada. */}
      {mudou && escolhido === "PARTICULAR" && erroClientes && (
        <Aviso>
          Não foi possível conferir quantos clientes a conta tem: {erroClientes}
        </Aviso>
      )}
      {erro && <Aviso>{erro}</Aviso>}

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
    </section>
  );
}

function Exclusao() {
  const { usuario, excluirConta } = useAutenticacao();
  const [aberto, setAberto] = useState(false);
  const [dados, setDados] = useState(null);
  const [erroDados, setErroDados] = useState("");
  const [senha, setSenha] = useState("");
  const [confirmacao, setConfirmacao] = useState("");
  const { erro, ocupado, enviar } = useEnvio();

  // As contagens so quando o bloco abre: e so ali que elas servem.
  useEffect(() => {
    if (!aberto) return;
    setErroDados("");
    api
      .dadosDaConta()
      .then(setDados)
      .catch((falha) => setErroDados(falha.message));
  }, [aberto]);

  const confirmou = confirmacao.trim().toLowerCase() === usuario.email;

  function excluir(e) {
    e.preventDefault();
    // Deu certo, o provider zera o usuario e a guarda leva ao /login.
    enviar(() => excluirConta({ senha, confirmacao }));
  }

  return (
    <section className={s.secao}>
      <h2 className={s.secaoTitulo}>Excluir conta</h2>
      {!aberto ? (
        <>
          <p className={s.texto}>
            Apaga a conta e tudo o que está nela, de verdade — não é arquivar.
          </p>
          <div className={s.acoes}>
            <button
              className={`${c.botao} ${c.botaoRisco}`}
              type="button"
              onClick={() => setAberto(true)}
            >
              Excluir minha conta…
            </button>
          </div>
        </>
      ) : (
        <form className={s.risco} onSubmit={excluir}>
          <p className={s.pergunta}>Isto não tem volta.</p>
          <p className={s.texto}>
            Vão ser apagados, sem possibilidade de recuperar:
          </p>
          <ul className={s.lista}>
            {dados ? (
              <>
                {usuario.papel === "PROFISSIONAL" || dados.clientes > 0 ? (
                  <li>
                    {milhar(dados.clientes)} {dados.clientes === 1 ? "cliente" : "clientes"}
                  </li>
                ) : null}
                <li>
                  {milhar(dados.veiculos)} {dados.veiculos === 1 ? "veículo" : "veículos"},
                  inclusive os arquivados, com os limites de alerta
                </li>
                <li>
                  {milhar(dados.sessoes)} {dados.sessoes === 1 ? "sessão gravada" : "sessões gravadas"},
                  com todas as amostras e eventos
                </li>
              </>
            ) : erroDados ? (
              <li>
                clientes, veículos e sessões da conta (não foi possível contá-los:{" "}
                {erroDados})
              </li>
            ) : (
              <li>carregando o que há na conta…</li>
            )}
            <li>a própria conta e todos os logins abertos</li>
          </ul>
          <p className={s.texto}>
            Relatórios e arquivos já baixados (CSV, JSON, PDF) ficam onde você os
            guardou.
          </p>

          <label className={c.campo}>
            <span className={c.campoRotulo}>Senha</span>
            <input
              className={c.entrada}
              type="password"
              value={senha}
              onChange={(e) => setSenha(e.target.value)}
              autoComplete="current-password"
              required
            />
          </label>
          <label className={c.campo}>
            <span className={c.campoRotulo}>
              Para confirmar, digite o e-mail da conta ({usuario.email})
            </span>
            <input
              className={c.entrada}
              value={confirmacao}
              onChange={(e) => setConfirmacao(e.target.value)}
              autoComplete="off"
              required
            />
          </label>

          {erro && <Aviso>{erro}</Aviso>}

          <div className={s.acoes}>
            <button
              className={`${c.botao} ${c.botaoRisco}`}
              type="submit"
              disabled={ocupado || !senha || !confirmou}
            >
              Excluir conta e todos os dados
            </button>
            <button
              className={c.botao}
              type="button"
              onClick={() => {
                setAberto(false);
                setSenha("");
                setConfirmacao("");
              }}
              disabled={ocupado}
            >
              Cancelar
            </button>
          </div>
        </form>
      )}
    </section>
  );
}
