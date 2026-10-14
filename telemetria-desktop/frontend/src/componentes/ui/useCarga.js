/*
  A carga de uma tela com `:id` na URL (sessao, exportar, veiculo, cliente
  e as edicoes), num lugar so. Devolve o dado, ou a falha ja classificada
  para o `FalhaDeCarga` mostrar:

  - `{naoExiste: true}`: o id nem e um numero de registro, ou o backend
    respondeu 404 - que e tambem o que ele responde para registro de
    OUTRA conta, de proposito. Para quem le e a mesma coisa: nao ha o que
    abrir. Id invalido NAO vai ao backend: a resposta seria o 422 com o
    nome tecnico do parametro ("sessao id: informe um numero inteiro");
  - `{naoExiste: false, frase}`: falhou a carga (rede, 500). A frase e a
    do api.js, e `tentarDeNovo` repete.

  `buscar(id)` e a funcao do api.js. `recarregar()` busca de novo sem
  limpar a tela, depois de uma acao. `ativo` falso nao carrega nada (o
  formulario em modo de cadastro). `aoCarregar(dados)` roda junto com a
  chegada, no mesmo render - e o que deixa um formulario preencher os
  campos sem piscar vazio.
*/
import { useCallback, useEffect, useRef, useState } from "react";

// Inteiro positivo que cabe na coluna (int4 do Postgres): mais digitos que
// isso estouraria no banco e voltaria 500, nao 404.
const ID_VALIDO = /^[1-9]\d{0,8}$/;

export function idValido(id) {
  return ID_VALIDO.test(String(id ?? ""));
}

export function useCarga(id, buscar, { ativo = true, aoCarregar } = {}) {
  const [dados, setDados] = useState(null);
  const [falha, setFalha] = useState(null);
  const [tentativa, setTentativa] = useState(0);
  // As funcoes em ref: quem chama as cria a cada render, e como
  // dependencia do efeito elas recarregariam a tela sem parar.
  const funcoes = useRef({ buscar, aoCarregar });
  funcoes.current = { buscar, aoCarregar };

  useEffect(() => {
    if (!ativo) return undefined;
    let vivo = true;
    setDados(null);
    setFalha(null);
    if (!idValido(id)) {
      setFalha({ naoExiste: true });
      return undefined;
    }
    funcoes.current
      .buscar(id)
      .then((recebido) => {
        if (!vivo) return;
        funcoes.current.aoCarregar?.(recebido);
        setDados(recebido);
      })
      .catch((e) => {
        if (!vivo) return;
        setFalha(e.status === 404 ? { naoExiste: true } : { naoExiste: false, frase: String(e.message || e) });
      });
    // Trocou de id (ou a tela saiu) antes de a resposta chegar: a resposta
    // velha nao pode cair por cima da nova.
    return () => {
      vivo = false;
    };
  }, [id, ativo, tentativa]);

  const tentarDeNovo = useCallback(() => setTentativa((n) => n + 1), []);

  // Depois de uma acao (arquivar, restaurar): busca de novo SEM limpar a
  // tela - a ficha continua a vista ate o dado novo chegar. A falha volta
  // para quem chamou, que a mostra junto da acao.
  const recarregar = useCallback(async () => {
    const recebido = await funcoes.current.buscar(id);
    setDados(recebido);
    return recebido;
  }, [id]);

  return { dados, setDados, falha, carregando: ativo && !dados && !falha, tentarDeNovo, recarregar };
}
