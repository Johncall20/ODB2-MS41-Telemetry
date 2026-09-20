/*
  Quem esta logado, para a aplicacao inteira.

  O TOKEN nao passa por aqui: ele vive num cookie httpOnly, que o JS nao
  consegue ler nem escrever - e o navegador manda sozinho em cada
  requisicao. O que este contexto guarda em memoria e o USUARIO, e nada
  vai para localStorage (convencao do projeto).

  Por isso recarregar a pagina perde o estado e nao a sessao: o provider
  nasce vazio, pergunta `GET /api/auth/eu`, e o cookie responde quem e.
*/
import { createContext, useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../api.js";

export const ContextoAutenticacao = createContext(null);

/** Mantem o usuario logado em memoria. Um por app, acima do roteador. */
export function AutenticacaoProvider({ children }) {
  const [usuario, setUsuario] = useState(null);
  // `carregando` comeca true e e o que impede a guarda de rota de chutar
  // para /login antes de a primeira resposta chegar: sem isto, todo F5
  // numa tela interna piscaria o login antes de voltar.
  const [carregando, setCarregando] = useState(true);

  /** Repergunta quem esta logado. Usado depois de mudar algo da conta -
   *  trocar o papel muda o que a interface inteira mostra. */
  const recarregar = useCallback(async () => {
    try {
      setUsuario(await api.eu());
    } catch {
      setUsuario(null);   // 401 = nao logado, nao e erro
    }
  }, []);

  useEffect(() => {
    let vivo = true;
    api
      .eu()
      .then((conta) => vivo && setUsuario(conta))
      .catch(() => vivo && setUsuario(null))
      .finally(() => vivo && setCarregando(false));
    return () => {
      vivo = false;
    };
  }, []);

  const entrar = useCallback(async (credenciais) => {
    setUsuario(await api.login(credenciais));
  }, []);

  const cadastrar = useCallback(async (dados) => {
    // O backend ja devolve logado: quem acabou de provar que tem a senha
    // nao precisa prova-la de novo na tela seguinte.
    setUsuario(await api.cadastro(dados));
  }, []);

  const sair = useCallback(async () => {
    try {
      await api.logout();
    } finally {
      // Limpa mesmo se a chamada falhar: o cookie pode ja ter expirado, e
      // continuar mostrando a conta na tela seria mentira.
      setUsuario(null);
    }
  }, []);

  const valor = useMemo(
    () => ({ usuario, carregando, entrar, cadastrar, sair, recarregar }),
    [usuario, carregando, entrar, cadastrar, sair, recarregar]
  );

  return (
    <ContextoAutenticacao.Provider value={valor}>{children}</ContextoAutenticacao.Provider>
  );
}
