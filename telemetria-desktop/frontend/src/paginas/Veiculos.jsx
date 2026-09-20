/*
  Tela de Veiculos: a lista de carros, com busca, filtro e ordenacao.

  E a tela inicial do app. Mexe aqui quem mudar o que a lista mostra por
  linha ou como ela e recortada.
*/
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowDown, ArrowUp, Search, X } from "lucide-react";
import { api } from "../api.js";
import { useAutenticacao } from "../hooks/useAutenticacao.js";
import { haQuantoTempo, placa } from "../formato.js";
import { Aviso } from "../componentes/ui/Aviso.jsx";
import { Chip } from "../componentes/ui/Chip.jsx";
import { Seta } from "../componentes/ui/Seta.jsx";
import { DropdownOrdenacao, direcaoInicial } from "../componentes/ui/DropdownOrdenacao.jsx";
import { FiltroPopover } from "../componentes/ui/FiltroPopover.jsx";
import { useFiltrosUrl } from "../componentes/ui/useFiltrosUrl.js";
import c from "../estilos/comum.module.css";
import s from "./Veiculos.module.css";

/*
  Node 2:85. Nada e filtrado aqui: busca, ordenacao e situacao viram query
  string para /api/veiculos, que filtra no SQL. O estado mora na URL.
*/

const PADROES = {
  busca: "",
  ordenar_por: "ultima_sessao",
  direcao: "desc",
  // Array = multipla escolha; repete na query string.
  situacao: [],
};

/*
  Campo e sentido na mesma opcao, escritos como se fala na oficina. A
  ordem importa duas vezes: e a ordem do dropdown, e o primeiro de cada
  campo e o sentido que o header da tabela assume no primeiro clique.
*/
const ORDENACOES = [
  { campo: "ultima_sessao", direcao: "desc", rotulo: "Última sessão, mais recente primeiro" },
  { campo: "ultima_sessao", direcao: "asc", rotulo: "Última sessão, mais antiga primeiro" },
  { campo: "total_sessoes", direcao: "desc", rotulo: "Mais sessões primeiro" },
  { campo: "total_sessoes", direcao: "asc", rotulo: "Menos sessões primeiro" },
  { campo: "placa", direcao: "asc", rotulo: "Placa, A-Z" },
  { campo: "placa", direcao: "desc", rotulo: "Placa, Z-A" },
  { campo: "modelo", direcao: "asc", rotulo: "Modelo, A-Z" },
  { campo: "modelo", direcao: "desc", rotulo: "Modelo, Z-A" },
  { campo: "cliente", direcao: "asc", rotulo: "Cliente, A-Z" },
  { campo: "cliente", direcao: "desc", rotulo: "Cliente, Z-A" },
  { campo: "criado_em", direcao: "desc", rotulo: "Cadastro, mais recente primeiro" },
  { campo: "criado_em", direcao: "asc", rotulo: "Cadastro, mais antigo primeiro" },
];

/*
  Situacoes somam entre si (o backend une com OR). "Arquivados" marcado
  sozinho mostra so os arquivados; desmarcado, eles continuam fora da
  lista, como sempre estiveram.
*/
const SITUACOES = [
  { valor: "recentes", rotulo: "Com sessão recente" },
  { valor: "nunca", rotulo: "Nunca usado" },
  { valor: "arquivados", rotulo: "Arquivados" },
];

// Coluna da tabela -> criterio de ordenacao. A ultima coluna e a seta.
// `papel` marca a coluna que so uma das contas ve. A PARTICULAR tem um
// cliente implicito que e ela mesma: a coluna mostraria o proprio nome em
// toda linha.
const COLUNAS = [
  { campo: "placa", rotulo: "Placa" },
  { campo: "modelo", rotulo: "Veículo" },
  { campo: "cliente", rotulo: "Cliente", papel: "PROFISSIONAL" },
  { campo: "ultima_sessao", rotulo: "Última sessão" },
];

/** A lista de carros cadastrados. Filtro e ordem vem da URL. */
export function Veiculos() {
  const { usuario } = useAutenticacao();
  const mostraCliente = usuario?.papel === "PROFISSIONAL";
  // Coluna e opcao de ordenacao andam juntas: deixar a ordenacao por
  // cliente no dropdown de quem nao ve a coluna daria uma lista reordenada
  // por um criterio invisivel.
  const colunas = COLUNAS.filter(({ papel }) => !papel || papel === usuario?.papel);
  const ordenacoes = ORDENACOES.filter(
    ({ campo }) => campo !== "cliente" || mostraCliente
  );

  const navegar = useNavigate();
  const { filtro, aplicar, alternar, remover, limpar } = useFiltrosUrl(PADROES);
  const [veiculos, setVeiculos] = useState(null);
  const [erro, setErro] = useState("");

  // A busca digita rapido demais para virar navegacao a cada tecla; o
  // campo mantem estado proprio e so encosta na URL depois da pausa.
  const [buscaLocal, setBuscaLocal] = useState(filtro.busca);
  useEffect(() => setBuscaLocal(filtro.busca), [filtro.busca]);
  useEffect(() => {
    if (buscaLocal === filtro.busca) return undefined;
    const t = setTimeout(() => aplicar({ busca: buscaLocal }, { substituir: true }), 300);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [buscaLocal]);

  useEffect(() => {
    setErro("");
    api
      .listarVeiculos({
        busca: filtro.busca,
        ordenar_por: filtro.ordenar_por,
        direcao: filtro.direcao,
        situacao: filtro.situacao,
      })
      .then(setVeiculos)
      .catch((e) => setErro(String(e.message || e)));
  }, [filtro]);

  /** Clique no header: ativa o criterio, ou inverte se ja era o ativo. */
  function ordenarPor(campo) {
    if (filtro.ordenar_por === campo) {
      aplicar({ direcao: filtro.direcao === "asc" ? "desc" : "asc" });
    } else {
      aplicar({ ordenar_por: campo, direcao: direcaoInicial(ORDENACOES, campo) });
    }
  }

  // Um chip por valor escolhido, e nao um por grupo: com selecao multipla
  // quem marcou tres situacoes precisa poder tirar uma sem perder as
  // outras.
  const ativos = [];
  if (filtro.busca) ativos.push({ chave: "busca", rotulo: `busca: ${filtro.busca}` });
  for (const valor of filtro.situacao) {
    const opcao = SITUACOES.find((o) => o.valor === valor);
    if (opcao) ativos.push({ chave: "situacao", valor, rotulo: opcao.rotulo.toLowerCase() });
  }

  const Direcao = filtro.direcao === "asc" ? ArrowUp : ArrowDown;

  if (erro) return <Aviso>{erro}</Aviso>;

  return (
    <>
      <header className={c.paginaTopo}>
        <div>
          <h1 className={c.paginaTitulo}>Veículos</h1>
          <p className={c.paginaSubtitulo}>
            {veiculos === null
              ? "carregando…"
              : `${veiculos.length} ${veiculos.length === 1 ? "listado" : "listados"}`}
          </p>
        </div>
        <button className={`${c.botao} ${c.botaoPrimario}`} onClick={() => navegar("/veiculos/novo")}>
          Adicionar veículo
        </button>
      </header>

      <div className={c.filtros}>
        <div className={c.campoBusca}>
          <Search className={c.campoBuscaIcone} size={22} aria-hidden="true" />
          <input
            className={c.entrada}
            value={buscaLocal}
            onChange={(e) => setBuscaLocal(e.target.value)}
            placeholder={
              mostraCliente
                ? "Buscar por placa, modelo ou cliente"
                : "Buscar por placa ou modelo"
            }
            aria-label="Buscar veículo"
          />
        </div>

        <FiltroPopover
          rotulo="Situação"
          opcoes={SITUACOES}
          valor={filtro.situacao}
          onChange={(valor) => alternar("situacao", valor)}
          resumo={filtro.situacao.length || ""}
        />

        <DropdownOrdenacao
          opcoes={ordenacoes}
          campo={filtro.ordenar_por}
          direcao={filtro.direcao}
          onChange={(campo, direcao) => aplicar({ ordenar_por: campo, direcao })}
        />
      </div>

      {ativos.length > 0 && (
        <div className={c.ativos}>
          <span className={c.ativosRotulo}>Filtros ativos:</span>
          {ativos.map((a) => (
            <button
              key={`${a.chave}:${a.valor ?? ""}`}
              className={c.ativoChip}
              onClick={() => remover(a.chave, a.valor)}
              title="Remover este filtro"
            >
              {a.rotulo}
              <X size={14} aria-hidden="true" />
            </button>
          ))}
          <button className={c.limpar} onClick={limpar}>
            Limpar filtros
          </button>
        </div>
      )}

      {veiculos === null ? (
        <p className={c.paginaVazia}>Carregando…</p>
      ) : veiculos.length === 0 ? (
        <p className={c.paginaVazia}>
          {ativos.length > 0
            ? "Nenhum veículo bate com esses filtros."
            : "Nenhum veículo cadastrado ainda."}
        </p>
      ) : (
        <table className={`${c.tabela} ${s.tabela}`}>
          <thead>
            <tr>
              {colunas.map((coluna) => {
                const ativa = filtro.ordenar_por === coluna.campo;
                return (
                  <th key={coluna.campo} aria-sort={ativa ? (filtro.direcao === "asc" ? "ascending" : "descending") : "none"}>
                    <button className={c.thBotao} onClick={() => ordenarPor(coluna.campo)}>
                      {coluna.rotulo}
                      {ativa && <Direcao size={14} aria-hidden="true" />}
                    </button>
                  </th>
                );
              })}
              <th />
            </tr>
          </thead>
          <tbody>
            {veiculos.map((v) => (
              <tr
                key={v.id}
                onClick={() => navegar(`/veiculos/${v.id}`)}
                tabIndex={0}
                onKeyDown={(e) => e.key === "Enter" && navegar(`/veiculos/${v.id}`)}
              >
                <td>
                  <span className={c.placaLinha}>
                    <span className={`${c.mono} ${s.placa}`}>{placa(v.placa) || "—"}</span>
                    {v.arquivado_em && <Chip>arquivado</Chip>}
                  </span>
                </td>
                <td>
                  <span className={c.celulaForte}>
                    {v.marca} {v.modelo}
                  </span>
                  <span className={c.celulaFraca}>
                    {[v.ano, v.motor, v.ecu].filter(Boolean).join(" · ")}
                  </span>
                </td>
                {mostraCliente && (
                  <td className={c.celulaApagada}>{v.cliente || "—"}</td>
                )}
                <td className={v.ultima_sessao ? c.celulaApagada : c.celulaNula}>
                  {haQuantoTempo(v.ultima_sessao) || "nenhuma ainda"}
                </td>
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
