import { Activity, Car, FileText, Settings } from "lucide-react";
import { NavLink } from "react-router-dom";
import logo from "../assets/logo.svg";
import s from "./BarraLateral.module.css";

/*
  Sidebar do Figma (node 2:88), em todas as telas menos Login e Criar
  conta. "Relatorios" nao tem node - a tela foi desenhada depois.
*/
const DESTINOS = [
  { para: "/veiculos", rotulo: "Veículos", Icone: Car, acende: true },
  { para: "/sessoes", rotulo: "Sessões", Icone: Activity, acende: true },
  { para: "/relatorios", rotulo: "Relatórios", Icone: FileText, acende: true },
  { para: "/ajustes", rotulo: "Ajustes", Icone: Settings, acende: true },
];

// Sem autenticacao ainda (item 7 do CLAUDE.md nao foi decidido). Ate la o
// rodape mostra o dono da maquina, fixo, como no prototipo.
const USUARIO = { nome: "Leonardo Caloni", papel: "Mecânico" };

function iniciais(nome) {
  return nome
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((parte) => parte[0].toUpperCase())
    .join("");
}

/** A navegacao fixa a esquerda, presente em toda tela interna. */
export function BarraLateral() {
  return (
    <nav className={s.barra} aria-label="Navegação principal">
      <div className={s.marca}>
        <img className={s.logo} src={logo} alt="" width="54" height="31" />
        <span className={s.nome}>
          OBD2 + MS41
          <br />
          Telemetry
        </span>
      </div>

      {DESTINOS.map(({ para, rotulo, Icone, acende }) => (
        <NavLink
          key={rotulo}
          to={para}
          end={false}
          className={({ isActive }) =>
            acende && isActive ? `${s.link} ${s.linkAtivo}` : s.link
          }
        >
          <Icone className={s.icone} size={22} aria-hidden="true" />
          {rotulo}
        </NavLink>
      ))}

      <div className={s.vao} />

      <div className={s.rodape}>
        <span className={s.avatar}>{iniciais(USUARIO.nome)}</span>
        <span className={s.usuario}>
          <span className={s.usuarioNome}>{USUARIO.nome}</span>
          <span className={s.usuarioPapel}>{USUARIO.papel}</span>
        </span>
      </div>
    </nav>
  );
}
