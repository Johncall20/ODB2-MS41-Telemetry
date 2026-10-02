import { Activity, Car, FileText, Gauge, LogOut, Users } from "lucide-react";
import { NavLink, useNavigate } from "react-router-dom";
import { useTelemetria } from "../hooks/useTelemetria.js";
import { useAutenticacao } from "../hooks/useAutenticacao.js";
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
  // So para o PROFISSIONAL: a conta PARTICULAR tem um cliente implicito
  // que e ela mesma, e nunca precisa ve-lo. `papel` diz de quem e o item.
  {
    para: "/clientes",
    rotulo: "Clientes",
    Icone: Users,
    acende: true,
    papel: "PROFISSIONAL",
  },
  // Nao ha "Ajustes": nao existe limite global para ajustar. O limite e
  // de cada carro, e a tela dele mora em /veiculos/:id/limites.
  { para: "/relatorios", rotulo: "Relatórios", Icone: FileText, acende: true },
];

// O papel e preferencia de interface, nao permissao: as duas contas veem
// so os proprios dados. Aqui ele e so a linha de baixo do rodape.
const ROTULO_PAPEL = {
  PROFISSIONAL: "Profissional",
  PARTICULAR: "Particular",
};

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
  const { usuario, sair } = useAutenticacao();
  const navegar = useNavigate();
  const gravando = Boolean(status?.gravando);

  async function encerrarConta() {
    await sair();
    // `replace` para o Voltar nao trazer de volta a tela interna de quem
    // acabou de sair - ela so mostraria o redirecionamento de novo.
    navegar("/login", { replace: true });
  }

  return (
    <nav className={s.barra} aria-label="Navegação principal">
      <div className={s.marca}>
        <img className={s.logo} src={logo} alt="" width="54" height="31" />
        <span className={s.nome}>
          ODB2 + MS41
          <br />
          Telemetry
        </span>
      </div>

      {DESTINOS.filter(({ papel }) => !papel || papel === usuario?.papel).map(
        ({ para, rotulo, Icone, acende }) => (
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
        ),
      )}

      <div className={s.vao} />

      <div className={s.rodape}>
        {/*
          A conta logada e o caminho ate /conta: e onde se troca nome,
          e-mail, senha e papel, e onde se exclui a conta. Mesmo realce de
          hover e de ativo dos links de cima; o Sair fica fora do link,
          ao lado, para um clique no nome nunca deslogar.
        */}
        <NavLink
          to="/conta"
          title="Minha conta"
          className={({ isActive }) => (isActive ? `${s.conta} ${s.contaAtiva}` : s.conta)}
        >
          <span className={s.avatar}>{iniciais(usuario?.nome || "")}</span>
          <span className={s.usuario}>
            <span className={s.usuarioNome}>{usuario?.nome}</span>
            <span className={s.usuarioPapel}>
              {ROTULO_PAPEL[usuario?.papel] || usuario?.papel}
            </span>
          </span>
        </NavLink>
        <button
          className={s.sair}
          type="button"
          onClick={encerrarConta}
          title="Sair"
        >
          <LogOut size={20} aria-hidden="true" />
          <span className={s.sairTexto}>Sair</span>
        </button>
      </div>
    </nav>
  );
}
