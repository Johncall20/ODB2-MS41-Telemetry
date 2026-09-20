/*
  Criar conta (node 3:529). Fora do Shell, mesmo layout do Login.

  O bloco "Como você vai usar" tem DOIS cards, e nao os tres do Figma
  (Mecânico / Preparador / Dono do carro). A decisao ja registrada no
  CLAUDE.md e de dois papeis - PROFISSIONAL e PARTICULAR -, porque
  mecanico e preparador fazem a mesma coisa no sistema: atendem carro de
  cliente. Com dois, cabe a descricao embaixo do rotulo.

  O papel e gravado agora, mas ainda nao muda nada na interface: quem usa
  isso e a Fase 3, que traz Cliente e as telas que dependem do papel.
*/
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Users, User } from "lucide-react";
import { useAutenticacao } from "../hooks/useAutenticacao.js";
import { PainelMarca } from "../componentes/ui/PainelMarca.jsx";
import { Aviso } from "../componentes/ui/Aviso.jsx";
import c from "../estilos/comum.module.css";
import s from "./CriarConta.module.css";

const SENHA_MINIMA = 8;

const PAPEIS = [
  // Profissional primeiro: e o publico principal do app.
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

/** Tela de cadastro. */
export function CriarConta() {
  const { cadastrar } = useAutenticacao();
  const navegar = useNavigate();

  const [nome, setNome] = useState("");
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [papel, setPapel] = useState("PROFISSIONAL");
  const [erro, setErro] = useState("");
  const [ocupado, setOcupado] = useState(false);

  async function enviar(e) {
    e.preventDefault();
    setErro("");
    setOcupado(true);
    try {
      // O backend devolve ja logado, entao daqui vai direto para dentro.
      await cadastrar({ nome, email, senha, papel });
      navegar("/veiculos", { replace: true });
    } catch (falha) {
      setErro(String(falha.message || falha));
    } finally {
      setOcupado(false);
    }
  }

  return (
    <div className={c.entradaTela}>
      <PainelMarca />

      <main className={c.entradaLado}>
        <form className={c.entradaColuna} onSubmit={enviar}>
          <h1 className={c.entradaTitulo}>Criar conta</h1>
          <p className={c.entradaSubtitulo}>
            Cadastre seus veículos e acompanhe cada sessão.
          </p>

          <div className={c.entradaCampos}>
            <label className={c.campo}>
              <span className={c.campoRotulo}>Nome</span>
              <input
                className={c.entrada}
                value={nome}
                onChange={(ev) => setNome(ev.target.value)}
                placeholder="Seu nome"
                autoComplete="name"
                required
                autoFocus
              />
            </label>

            <label className={c.campo}>
              <span className={c.campoRotulo}>E-mail</span>
              <input
                className={c.entrada}
                type="email"
                value={email}
                onChange={(ev) => setEmail(ev.target.value)}
                placeholder="teste@exemplo.com"
                autoComplete="email"
                required
              />
            </label>

            <label className={c.campo}>
              <span className={c.campoRotulo}>Senha</span>
              <input
                className={c.entrada}
                type="password"
                value={senha}
                onChange={(ev) => setSenha(ev.target.value)}
                autoComplete="new-password"
                minLength={SENHA_MINIMA}
                required
              />
              {/*
                A dica repete a regra que o backend cobra. O `minLength`
                so adianta o aviso: quem decide e o 422 do servidor, que
                vale para qualquer cliente.
              */}
              <span className={s.dica}>Mínimo de {SENHA_MINIMA} caracteres.</span>
            </label>

            <fieldset className={s.papeis}>
              <legend className={c.campoRotulo}>Como você vai usar</legend>
              <div className={s.cartoes}>
                {PAPEIS.map(({ valor, rotulo, descricao, Icone }) => (
                  <label
                    key={valor}
                    className={`${s.cartao} ${papel === valor ? s.cartaoEscolhido : ""}`.trim()}
                  >
                    {/*
                      Radio de verdade, escondido: o teclado e o leitor de
                      tela navegam o grupo sozinhos, e um <div onClick>
                      teria de reimplementar as duas coisas.
                    */}
                    <input
                      className={s.radio}
                      type="radio"
                      name="papel"
                      value={valor}
                      checked={papel === valor}
                      onChange={() => setPapel(valor)}
                    />
                    <Icone className={s.icone} size={24} aria-hidden="true" />
                    <span className={s.cartaoRotulo}>{rotulo}</span>
                    <span className={s.cartaoDescricao}>{descricao}</span>
                  </label>
                ))}
              </div>
            </fieldset>
          </div>

          {erro && <Aviso>{erro}</Aviso>}

          <button
            className={`${c.botao} ${c.botaoPrimario} ${c.entradaAcao}`}
            type="submit"
            disabled={ocupado}
          >
            {ocupado ? "Criando…" : "Criar conta"}
          </button>

          <p className={c.entradaRodape}>
            Já tem conta? <Link to="/login">Entrar</Link>
          </p>
        </form>
      </main>
    </div>
  );
}
