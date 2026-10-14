/*
  A porta de entrada da interface: monta o React na pagina.

  A ordem dos imports de estilo importa - fontes, depois tokens, depois o
  reset. Mexe aqui quem trocar o roteador ou acrescentar algo que precise
  envolver a aplicacao inteira.
*/
import React from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { Rotas } from "./rotas.jsx";
import { AutenticacaoProvider } from "./hooks/AutenticacaoProvider.jsx";
import { LimiteDeErro } from "./componentes/ui/LimiteDeErro.jsx";
import "@fontsource/space-grotesk/400.css";
import "@fontsource/space-grotesk/500.css";
import "@fontsource/jetbrains-mono/400.css";
import "./estilos/tokens.css";
import "./estilos/base.css";

createRoot(document.getElementById("raiz")).render(
  <React.StrictMode>
    {/* O que quebrar fora do Shell (login, cadastro, o roteador) mostra a
        pagina de erro inteira; dentro dele, o boundary do Shell pega antes. */}
    <LimiteDeErro inteira>
      <BrowserRouter>
        {/*
          O provider envolve o roteador inteiro, e nao o Shell: login e
          cadastro ficam FORA do Shell e tambem precisam saber se ja ha
          sessao - e a guarda que os manda para dentro quando ha.
        */}
        <AutenticacaoProvider>
          <Rotas />
        </AutenticacaoProvider>
      </BrowserRouter>
    </LimiteDeErro>
  </React.StrictMode>
);
