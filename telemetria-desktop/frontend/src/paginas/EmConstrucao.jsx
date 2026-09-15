import c from "../estilos/comum.module.css";

/*
  Marcador das rotas que ainda nao tem tela.

  Some quando a ultima tela da lista do CLAUDE.md entrar - hoje faltam
  login (item 7) e conexao ao adaptador (item 8).
*/

/** Um "ainda nao existe" honesto, com o numero do item que falta. */
export function EmConstrucao({ titulo, item }) {
  return (
    <>
      <header className={c.paginaTopo}>
        <h1 className={c.paginaTitulo}>{titulo}</h1>
      </header>
      <p className={c.paginaVazia}>
        Tela ainda não construída — item {item} da lista do CLAUDE.md.
      </p>
    </>
  );
}
