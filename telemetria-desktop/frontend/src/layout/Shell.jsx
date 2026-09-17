import { Outlet } from "react-router-dom";
import { TelemetriaProvider } from "../hooks/TelemetriaProvider.jsx";
import { BarraLateral } from "./BarraLateral.jsx";
import s from "./Shell.module.css";

/*
  A moldura de toda tela interna: sidebar fixa de 288px e conteudo de
  1632px (node 2:87). So o conteudo rola.

  O TelemetriaProvider entra aqui, por fora do <Outlet>: assim existe um
  socket so, a sidebar pode mostrar "Gravando" em qualquer tela, e trocar
  de rota nao derruba nem reabre a conexao.
*/

/** Envolve as telas com a navegacao. O <Outlet> e onde a rota entra. */
export function Shell() {
  return (
    <TelemetriaProvider>
      <div className={s.shell}>
        <BarraLateral />
        <main className={s.conteudo}>
          <Outlet />
        </main>
      </div>
    </TelemetriaProvider>
  );
}
