/*
  Quem pode ver o que. Duas guardas simetricas, usadas no `rotas.jsx`, e
  uma de papel - `SoProfissional`, na frente das telas de cliente.

  As duas esperam `carregando` acabar antes de decidir. Sem isso, todo F5
  numa tela interna redirecionaria para /login antes de o
  `GET /api/auth/eu` responder, e a pessoa veria o login piscar sem nunca
  ter saido.
*/
import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAutenticacao } from "../hooks/useAutenticacao.js";
import c from "../estilos/comum.module.css";

function Esperando() {
  return <p className={c.paginaVazia}>Carregando…</p>;
}

/** Envolve as telas internas: sem sessao, manda para /login. */
export function ExigeSessao() {
  const { usuario, carregando, expirou } = useAutenticacao();
  const lugar = useLocation();

  if (carregando) return <Esperando />;
  if (!usuario) {
    // `state` guarda de onde a pessoa veio (o login volta para la) e se a
    // sessao expirou (o login avisa); `replace` evita empilhar o
    // redirecionamento no historico.
    return (
      <Navigate
        to="/login"
        replace
        state={{ de: lugar.pathname + lugar.search, expirou }}
      />
    );
  }
  return <Outlet />;
}

/** Envolve login e cadastro: com sessao, manda para dentro. */
export function SoDeslogado() {
  const { usuario, carregando } = useAutenticacao();
  const lugar = useLocation();

  if (carregando) return <Esperando />;
  // Quem acabou de entrar volta para onde estava quando a sessao caiu (o
  // mesmo destino que o Login escolhe - nenhum dos dois ganha a corrida
  // levando para outro lugar).
  if (usuario) return <Navigate to={lugar.state?.de || "/veiculos"} replace />;
  return <Outlet />;
}

/*
  As telas de cliente sao so do PROFISSIONAL: o PARTICULAR nao gerencia
  clientes, e o backend responde 403 nas rotas de escrita. Vai por dentro
  do ExigeSessao, entao o usuario ja esta carregado aqui.

  Redireciona em vez de dar 404: um link salvo de quando a conta era
  PROFISSIONAL leva para os carros, que continuam todos visiveis.
*/
/** Envolve as telas de cliente: conta PARTICULAR vai para /veiculos. */
export function SoProfissional() {
  const { usuario } = useAutenticacao();
  if (usuario?.papel !== "PROFISSIONAL") return <Navigate to="/veiculos" replace />;
  return <Outlet />;
}
