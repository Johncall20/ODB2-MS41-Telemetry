/*
  Entrar (node 2:2). Fora do Shell: sem sidebar, layout de duas colunas.

  Nao ha "Esqueci a senha" nem "Manter conectado", embora estejam no
  Figma: o primeiro depende de servidor de e-mail (esta em "Limitacoes
  conhecidas" no CLAUDE.md) e o segundo de uma decisao sobre validade de
  token. Desenhar o controle sem o que ele precisa atras seria prometer o
  que a tela nao cumpre.
*/
import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAutenticacao } from "../hooks/useAutenticacao.js";
import { PainelMarca } from "../componentes/ui/PainelMarca.jsx";
import { Aviso } from "../componentes/ui/Aviso.jsx";
import c from "../estilos/comum.module.css";

/** Tela de login. */
export function Login() {
  const { entrar } = useAutenticacao();
  const navegar = useNavigate();
  // A guarda manda para ca com de onde a pessoa veio e se a sessao
  // expirou. Um link direto para /login nao traz nada disso.
  const { de, expirou } = useLocation().state || {};

  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [erro, setErro] = useState("");
  const [errosCampo, setErrosCampo] = useState({});
  const [ocupado, setOcupado] = useState(false);

  async function enviar(e) {
    e.preventDefault();
    setErro("");
    setErrosCampo({});
    setOcupado(true);
    try {
      await entrar({ email, senha });
      // Volta para onde estava quando a sessao caiu. `replace` para o
      // Voltar do navegador nao trazer de volta o login.
      navegar(de && de !== "/login" ? de : "/veiculos", { replace: true });
    } catch (falha) {
      // Formato do e-mail (422) vai embaixo do campo; credencial errada
      // (401) e uma frase so, a mesma para e-mail inexistente e senha
      // errada - de proposito, vinda do backend.
      const campos = falha.campos || {};
      setErrosCampo(campos);
      if (!campos.email && !campos.senha) setErro(falha.message);
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

          {expirou && <Aviso atencao>Sua sessão expirou. Entre de novo para continuar.</Aviso>}

          <div className={c.entradaCampos}>
            <label className={c.campo}>
              <span className={c.campoRotulo}>E-mail</span>
              <input
                className={`${c.entrada} ${errosCampo.email ? c.entradaInvalida : ""}`.trim()}
                type="email"
                value={email}
                onChange={(ev) => setEmail(ev.target.value)}
                placeholder="teste@exemplo.com"
                autoComplete="email"
                required
                autoFocus
                aria-invalid={errosCampo.email ? true : undefined}
              />
              {errosCampo.email && <span className={c.campoErro}>{errosCampo.email}</span>}
            </label>

            <label className={c.campo}>
              <span className={c.campoRotulo}>Senha</span>
              <input
                className={`${c.entrada} ${errosCampo.senha ? c.entradaInvalida : ""}`.trim()}
                type="password"
                value={senha}
                onChange={(ev) => setSenha(ev.target.value)}
                autoComplete="current-password"
                required
                aria-invalid={errosCampo.senha ? true : undefined}
              />
              {errosCampo.senha && <span className={c.campoErro}>{errosCampo.senha}</span>}
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
