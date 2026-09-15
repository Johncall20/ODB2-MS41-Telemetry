import { Outlet } from "react-router-dom";
import { BarraLateral } from "./BarraLateral.jsx";
import s from "./Shell.module.css";

/*
  A moldura de toda tela interna: sidebar fixa de 288px e conteudo de
  1632px (node 2:87). So o conteudo rola.
*/

/** Envolve as telas com a navegacao. O <Outlet> e onde a rota entra. */
export function Shell() {
  return (
    <div className={s.shell}>
      <BarraLateral />
      <main className={s.conteudo}>
        <Outlet />
      </main>
    </div>
  );
}
