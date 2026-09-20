/*
  Quem esta logado. Le o AutenticacaoProvider, montado acima do roteador.

  Devolve `{ usuario, carregando, entrar, cadastrar, sair, recarregar }`. `usuario` e
  null quando nao ha sessao; `carregando` e true so ate a primeira
  resposta de `GET /api/auth/eu`.
*/
import { useContext } from "react";
import { ContextoAutenticacao } from "./AutenticacaoProvider.jsx";

/** A conta logada e as acoes de entrar, cadastrar e sair. */
export function useAutenticacao() {
  const valor = useContext(ContextoAutenticacao);
  if (valor === null) {
    throw new Error(
      "useAutenticacao() usado fora do AutenticacaoProvider - ele e montado no main.jsx."
    );
  }
  return valor;
}
