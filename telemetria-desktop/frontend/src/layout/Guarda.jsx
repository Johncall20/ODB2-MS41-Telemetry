/*
  Quem pode ver o que. Duas guardas simetricas, usadas no `rotas.jsx`.

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
  const { usuario, carregando } = useAutenticacao();
  const lugar = useLocation();

  if (carregando) return <Esperando />;
  if (!usuario) {
    // `state` guarda de onde a pessoa veio, e `replace` evita empilhar o
    // redirecionamento no historico.
    return <Navigate to="/login" replace state={{ de: lugar.pathname }} />;
  }
  return <Outlet />;
}

/** Envolve login e cadastro: com sessao, manda para dentro. */
export function SoDeslogado() {
  const { usuario, carregando } = useAutenticacao();

  if (carregando) return <Esperando />;
  if (usuario) return <Navigate to="/veiculos" replace />;
  return <Outlet />;
}
