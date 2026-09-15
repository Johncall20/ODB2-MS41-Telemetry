import { useCallback, useMemo } from "react";
import { useSearchParams } from "react-router-dom";

/**
 * Estado de filtro e ordenacao na URL. `padroes` em array marca o campo
 * como de multipla escolha, e ele repete na query string.
 */
export function useFiltrosUrl(padroes) {
  const [parametros, setParametros] = useSearchParams();

  // A query em texto: e o que faz o filtro so mudar quando a URL muda.
  const chaveUrl = parametros.toString();

  const filtro = useMemo(() => {
    const atual = {};
    for (const [chave, padrao] of Object.entries(padroes)) {
      atual[chave] = Array.isArray(padrao)
        ? parametros.getAll(chave)
        : parametros.get(chave) ?? padrao;
    }
    return atual;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chaveUrl]);

  /**
   * Grava na URL so o que difere do padrao. `substituir` troca a entrada
   * do historico em vez de empilhar - a busca por digitacao usa isso,
   * senao cada tecla viraria um passo do botao voltar.
   */
  const aplicar = useCallback(
    (mudancas, { substituir = false } = {}) => {
      const novo = { ...filtro, ...mudancas };
      const query = new URLSearchParams();
      for (const [chave, valor] of Object.entries(novo)) {
        const padrao = padroes[chave];
        if (Array.isArray(padrao)) {
          for (const item of valor || []) query.append(chave, item);
        } else if (valor && valor !== padrao) {
          query.set(chave, valor);
        }
      }
      setParametros(query, { replace: substituir });
    },
    [filtro, padroes, setParametros]
  );

  /** Marca ou desmarca um valor num campo de multipla escolha. */
  const alternar = useCallback(
    (chave, valor) => {
      const atual = filtro[chave] || [];
      const novo = atual.includes(valor)
        ? atual.filter((v) => v !== valor)
        : [...atual, valor];
      aplicar({ [chave]: novo });
    },
    [filtro, aplicar]
  );

  /** Remove um filtro: o valor solto num campo multiplo, o campo inteiro
   *  nos demais. E o que o X do chip chama. */
  const remover = useCallback(
    (chave, valor) => {
      if (Array.isArray(padroes[chave]) && valor !== undefined) {
        aplicar({ [chave]: (filtro[chave] || []).filter((v) => v !== valor) });
        return;
      }
      aplicar({ [chave]: padroes[chave] });
    },
    [filtro, aplicar, padroes]
  );

  const limpar = useCallback(() => setParametros({}), [setParametros]);

  return { filtro, aplicar, alternar, remover, limpar };
}
