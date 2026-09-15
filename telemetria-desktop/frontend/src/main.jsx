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
import "@fontsource/space-grotesk/400.css";
import "@fontsource/space-grotesk/500.css";
import "@fontsource/jetbrains-mono/400.css";
import "./estilos/tokens.css";
import "./estilos/base.css";

createRoot(document.getElementById("raiz")).render(
  <React.StrictMode>
    <BrowserRouter>
      <Rotas />
    </BrowserRouter>
  </React.StrictMode>
);
