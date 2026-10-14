/*
  Quem esta logado, para a aplicacao inteira.

  O TOKEN nao passa por aqui: ele vive num cookie httpOnly, que o JS nao
  consegue ler nem escrever - e o navegador manda sozinho em cada
  requisicao. O que este contexto guarda em memoria e o USUARIO, e nada
  vai para localStorage (convencao do projeto).

  Por isso recarregar a pagina perde o estado e nao a sessao: o provider
  nasce vazio, pergunta `GET /api/auth/eu`, e o cookie responde quem e.
*/
import { createContext, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, quandoSessaoExpirar } from "../api.js";

export const ContextoAutenticacao = createContext(null);

/** Mantem o usuario logado em memoria. Um por app, acima do roteador. */
export function AutenticacaoProvider({ children }) {
  const [usuario, setUsuario] = useState(null);
  // `carregando` comeca true e e o que impede a guarda de rota de chutar
  // para /login antes de a primeira resposta chegar: sem isto, todo F5
  // numa tela interna piscaria o login antes de voltar.
  const [carregando, setCarregando] = useState(true);
  // A sessao caiu sozinha (401 numa tela interna), e nao por "Sair": a
  // guarda leva ao /login com o aviso. Zera ao entrar de novo.
  const [expirou, setExpirou] = useState(false);
  const usuarioRef = useRef(null);
  usuarioRef.current = usuario;

  // O api.js avisa todo 401 fora do login. So conta como expirada se havia
  // alguem logado: antes disso, 401 e so "ninguem entrou ainda".
  useEffect(() => {
    quandoSessaoExpirar(() => {
      if (!usuarioRef.current) return;
      setExpirou(true);
      setUsuario(null);
    });
    return () => quandoSessaoExpirar(null);
  }, []);

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
    setExpirou(false);
  }, []);

  const cadastrar = useCallback(async (dados) => {
    // O backend ja devolve logado: quem acabou de provar que tem a senha
    // nao precisa prova-la de novo na tela seguinte.
    setUsuario(await api.cadastro(dados));
    setExpirou(false);
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

  /** Exclui a conta. O backend ja apagou o cookie; zerar o usuario e o
   *  que faz a guarda de rota mandar para /login. So zera se deu certo:
   *  senha errada ou gravacao ativa deixam a pessoa onde estava. */
  const excluirConta = useCallback(async (dados) => {
    await api.excluirConta(dados);
    setUsuario(null);
  }, []);

  const valor = useMemo(
    () => ({ usuario, carregando, expirou, entrar, cadastrar, sair, recarregar, excluirConta }),
    [usuario, carregando, expirou, entrar, cadastrar, sair, recarregar, excluirConta]
  );

  return (
    <ContextoAutenticacao.Provider value={valor}>{children}</ContextoAutenticacao.Provider>
  );
}
