/*
  Error boundary: um componente que quebra ao renderizar mostra "Algo deu
  errado" com o caminho de volta, em vez de desmontar a arvore inteira e
  deixar a pagina em branco.

  Sao dois no app:
  - no Shell, em volta do <Outlet>: so a tela quebra, e a sidebar e o
    websocket continuam vivos. O Shell o remonta a cada troca de rota
    (`key` pelo pathname), entao sair da tela quebrada ja limpa o erro;
  - no main.jsx, em volta de tudo (`inteira`): pega o que quebra fora do
    Shell (login, cadastro, o proprio roteador) e mostra a pagina toda.

  Erro de renderizacao nao passa pelo api.js; o detalhe vai para o
  console daqui, como o resto. Boundary so existe como classe no React.
*/
import { Component } from "react";
import c from "../../estilos/comum.module.css";
import s from "./LimiteDeErro.module.css";

export class LimiteDeErro extends Component {
  constructor(props) {
    super(props);
    this.state = { quebrou: false };
  }

  static getDerivedStateFromError() {
    return { quebrou: true };
  }

  componentDidCatch(erro, info) {
    console.error("[tela] erro ao desenhar", erro, info?.componentStack);
  }

  render() {
    if (!this.state.quebrou) return this.props.children;
    return (
      <div className={`${s.caixa} ${this.props.inteira ? s.inteira : ""}`.trim()} role="alert">
        <h1 className={s.titulo}>Algo deu errado nesta tela</h1>
        <p className={s.texto}>
          Uma parte da página não conseguiu ser exibida. Recarregar costuma resolver; se continuar,
          volte ao início e tente de novo.
        </p>
        <div className={s.acoes}>
          <button type="button" className={`${c.botao} ${c.botaoPrimario}`} onClick={() => window.location.reload()}>
            Recarregar a página
          </button>
          {/* Link comum, e nao do roteador: o boundary de fora fica acima
              dele, e recarregar do zero e o que se quer aqui. */}
          <a className={c.botao} href="/">
            Voltar ao início
          </a>
        </div>
      </div>
    );
  }
}
