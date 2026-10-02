/*
  Os clientes da conta: a lista, com o recorte de ativos e arquivados.

  So a conta PROFISSIONAL chega aqui - a guarda `SoProfissional` manda o
  PARTICULAR para /veiculos, e o backend responde 403 as escritas dele.
  O cliente implicito ("Meus carros") nao aparece: nao e alguem que a
  pessoa cadastrou.

  Mesma forma da tela de Veiculos: botao de cadastro no cabecalho, filtro
  embaixo, e a linha inteira levando ao detalhe. Editar, arquivar e
  desarquivar moram na tela do cliente (/clientes/:id); cadastro e edicao
  no ClienteFormulario.

  Sem node no Figma.
*/
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { X } from "lucide-react";
import { api } from "../api.js";
import { Aviso } from "../componentes/ui/Aviso.jsx";
import { FiltroPopover } from "../componentes/ui/FiltroPopover.jsx";
import { Seta } from "../componentes/ui/Seta.jsx";
import { useFiltrosUrl } from "../componentes/ui/useFiltrosUrl.js";
import c from "../estilos/comum.module.css";
import s from "./Clientes.module.css";

const PADROES = { situacao: "ativos" };

// Radio, nao checkbox: a API devolve um lado ou o outro, e nenhuma tela
// mistura ativo com arquivado.
const SITUACOES = [
  { valor: "ativos", rotulo: "Ativos" },
  { valor: "arquivados", rotulo: "Arquivados" },
];

/** A lista de clientes da conta. O recorte vem da URL. */
export function Clientes() {
  const navegar = useNavigate();
  const { filtro, aplicar, limpar } = useFiltrosUrl(PADROES);
  const arquivados = filtro.situacao === "arquivados";

  const [clientes, setClientes] = useState(null);
  const [erro, setErro] = useState("");

  useEffect(() => {
    setErro("");
    setClientes(null);
    api
      .listarClientes({ arquivados })
      .then(setClientes)
      .catch((e) => setErro(String(e.message || e)));
  }, [arquivados]);

  if (erro) return <Aviso>{erro}</Aviso>;

  return (
    <>
      <header className={c.paginaTopo}>
        <div>
          <h1 className={c.paginaTitulo}>Clientes</h1>
          <p className={c.paginaSubtitulo}>
            {clientes === null
              ? "carregando…"
              : `${clientes.length} ${clientes.length === 1 ? "listado" : "listados"}`}
          </p>
        </div>
        <button
          className={`${c.botao} ${c.botaoPrimario}`}
          onClick={() => navegar("/clientes/novo")}
        >
          Novo cliente
        </button>
      </header>

      <div className={c.filtros}>
        <FiltroPopover
          rotulo="Situação"
          rotuloAcima={false}
          exclusivo
          opcoes={SITUACOES}
          valor={filtro.situacao}
          padrao={PADROES.situacao}
          onChange={(valor) => aplicar({ situacao: valor })}
        />
      </div>

      {arquivados && (
        <div className={c.ativos}>
          <span className={c.ativosRotulo}>Filtros ativos:</span>
          <button className={c.ativoChip} onClick={limpar} title="Voltar aos ativos">
            arquivados
            <X size={14} aria-hidden="true" />
          </button>
        </div>
      )}

      {clientes === null ? (
        <p className={c.paginaVazia}>Carregando…</p>
      ) : clientes.length === 0 && arquivados ? (
        <p className={c.paginaVazia}>Nenhum cliente arquivado.</p>
      ) : clientes.length === 0 ? (
        <div className={c.estadoVazio}>
          <p>
            Nenhum cliente cadastrado ainda. Cadastre o primeiro para poder
            vincular veículos a ele.
          </p>
          <button
            className={`${c.botao} ${c.botaoPrimario}`}
            onClick={() => navegar("/clientes/novo")}
          >
            Cadastrar o primeiro cliente
          </button>
        </div>
      ) : (
        <table className={`${c.tabela} ${s.tabela}`}>
          <thead>
            <tr>
              <th>Nome</th>
              <th>Contato</th>
              <th>Veículos ativos</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {clientes.map((cliente) => (
              <tr
                key={cliente.id}
                onClick={() => navegar(`/clientes/${cliente.id}`)}
                tabIndex={0}
                onKeyDown={(e) => e.key === "Enter" && navegar(`/clientes/${cliente.id}`)}
              >
                <td>
                  <span className={c.celulaForte}>{cliente.nome}</span>
                </td>
                <td className={cliente.contato ? c.celulaApagada : c.celulaNula}>
                  {cliente.contato || "sem contato"}
                </td>
                {/*
                  Conta so os carros ativos: o arquivado nao some do banco,
                  mas somar os dois numeros faria a coluna nao bater com a
                  lista de veiculos do cliente.
                */}
                <td className={c.mono}>{cliente.veiculos}</td>
                <td>
                  <Seta />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  );
}
