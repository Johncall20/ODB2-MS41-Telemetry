import { Activity, Car, FileText, Gauge } from "lucide-react";
import { NavLink } from "react-router-dom";
import { useTelemetria } from "../hooks/useTelemetria.js";
import logo from "../assets/logo.svg";
import s from "./BarraLateral.module.css";

/*
  Sidebar do Figma (node 2:88), em todas as telas menos Login e Criar
  conta. "Relatorios" nao tem node - a tela foi desenhada depois, e
  "Ao vivo" tambem nao: o painel existia sem entrada na navegacao.
*/
const DESTINOS = [
  // Primeiro da lista de proposito: e a tela que se abre com o carro
  // ligado na frente. A rota inicial continua sendo /veiculos - escolher
  // o carro vem antes de olhar o painel dele.
  { para: "/ao-vivo", rotulo: "Ao vivo", Icone: Gauge, acende: true },
  { para: "/veiculos", rotulo: "Veículos", Icone: Car, acende: true },
  { para: "/sessoes", rotulo: "Sessões", Icone: Activity, acende: true },
  // Nao ha "Ajustes": nao existe limite global para ajustar. O limite e
  // de cada carro, e a tela dele mora em /veiculos/:id/limites.
  { para: "/relatorios", rotulo: "Relatórios", Icone: FileText, acende: true },
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
  // Do provider do Shell, nao de fetch proprio: e a mesma conexao que o
  // painel usa, entao a sidebar acusa a gravacao em qualquer tela.
  const { status } = useTelemetria();
  const gravando = Boolean(status?.gravando);

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
          {/*
            O aviso de gravacao mora no item do Ao vivo: e para la que se
            vai encerrar a sessao, entao o indicador aponta para onde agir.
          */}
          {para === "/ao-vivo" && gravando && (
            <span className={s.gravando}>
              <span className={s.ponto} />
              Gravando
            </span>
          )}
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
