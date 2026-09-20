/*
  Entrar (node 2:2). Fora do Shell: sem sidebar, layout de duas colunas.

  Nao ha "Esqueci a senha" nem "Manter conectado", embora estejam no
  Figma: o primeiro depende de servidor de e-mail e o segundo de uma
  decisao sobre validade de token. Os dois estao registrados como
  pendencia no CLAUDE.md - desenhar o controle sem o que ele precisa
  atras seria prometer o que a tela nao cumpre.
*/
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAutenticacao } from "../hooks/useAutenticacao.js";
import { PainelMarca } from "../componentes/ui/PainelMarca.jsx";
import { Aviso } from "../componentes/ui/Aviso.jsx";
import c from "../estilos/comum.module.css";

/** Tela de login. */
export function Login() {
  const { entrar } = useAutenticacao();
  const navegar = useNavigate();

  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [erro, setErro] = useState("");
  const [ocupado, setOcupado] = useState(false);

  async function enviar(e) {
    e.preventDefault();
    setErro("");
    setOcupado(true);
    try {
      await entrar({ email, senha });
      // `replace` para o Voltar do navegador nao trazer de volta o login
      // de quem acabou de entrar.
      navegar("/veiculos", { replace: true });
    } catch (falha) {
      // A frase vem do backend, e e a mesma para e-mail inexistente e
      // senha errada - de proposito.
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
          <h1 className={c.entradaTitulo}>Entrar</h1>

          <div className={c.entradaCampos}>
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
                autoFocus
              />
            </label>

            <label className={c.campo}>
              <span className={c.campoRotulo}>Senha</span>
              <input
                className={c.entrada}
                type="password"
                value={senha}
                onChange={(ev) => setSenha(ev.target.value)}
                autoComplete="current-password"
                required
              />
            </label>
          </div>

          {erro && <Aviso>{erro}</Aviso>}

          <button
            className={`${c.botao} ${c.botaoPrimario} ${c.entradaAcao}`}
            type="submit"
            disabled={ocupado}
          >
            {ocupado ? "Entrando…" : "Entrar"}
          </button>

          <p className={c.entradaRodape}>
            Sem conta? <Link to="/criar-conta">Cadastre-se aqui agora</Link>
          </p>
        </form>
      </main>
    </div>
  );
}
