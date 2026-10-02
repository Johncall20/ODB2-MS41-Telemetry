/*
  Tela de Sessoes: todas as gravacoes, com filtro e ordenacao.

  Mexe aqui quem mudar o que cada linha resume ou como a lista e
  recortada.
*/
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowDown, ArrowUp, X } from "lucide-react";
import { api } from "../api.js";
import { ROTULO_EVENTO, dataHora, duracao, milhar, placa } from "../formato.js";
import { Aviso } from "../componentes/ui/Aviso.jsx";
import { Chip, Chips } from "../componentes/ui/Chip.jsx";
import { Seta } from "../componentes/ui/Seta.jsx";
import { DropdownOrdenacao, direcaoInicial } from "../componentes/ui/DropdownOrdenacao.jsx";
import { FiltroPopover } from "../componentes/ui/FiltroPopover.jsx";
import { useFiltrosUrl } from "../componentes/ui/useFiltrosUrl.js";
import c from "../estilos/comum.module.css";
import s from "./Sessoes.module.css";

/*
  Node 5:668. Nada e filtrado aqui: os recortes viram query string para
  /api/sessoes. O estado mora na URL.
*/

const PADROES = {
  veiculo_id: "",
  periodo: "tudo",
  data_inicio: "",
  data_fim: "",
  // Arrays = multipla escolha; repetem na query string.
  tipo_evento: [],
  sem_eventos: "",
  ordenar_por: "data",
  direcao: "desc",
};

const PERIODOS = [
  { valor: "tudo", rotulo: "Todo o período", curto: "tudo" },
  { valor: "7d", rotulo: "Últimos 7 dias", curto: "7 dias" },
  { valor: "30d", rotulo: "Últimos 30 dias", curto: "30 dias" },
  { valor: "90d", rotulo: "Últimos 90 dias", curto: "90 dias" },
  { valor: "personalizado", rotulo: "Intervalo personalizado", curto: "personalizado" },
];

const ORDENACOES = [
  { campo: "data", direcao: "desc", rotulo: "Data, mais recente primeiro" },
  { campo: "data", direcao: "asc", rotulo: "Data, mais antiga primeiro" },
  { campo: "duracao", direcao: "desc", rotulo: "Duração, da mais longa" },
  { campo: "duracao", direcao: "asc", rotulo: "Duração, da mais curta" },
  { campo: "rpm_maximo", direcao: "desc", rotulo: "RPM máximo, do maior" },
  { campo: "rpm_maximo", direcao: "asc", rotulo: "RPM máximo, do menor" },
  { campo: "eventos", direcao: "desc", rotulo: "Mais eventos primeiro" },
  { campo: "eventos", direcao: "asc", rotulo: "Menos eventos primeiro" },
];

// Vermelho para o que pode danificar o motor ou invalidar a gravacao.
const GRAVES = new Set(["RPM_ALTO", "TEMP_ALTA", "BATERIA_BAIXA", "PERDA_CONEXAO"]);

/*
  Os de rotina nao entram - existem em toda sessao. "sem" vira o parametro
  sem_eventos no backend, nao um tipo. As marcas somam entre si.
*/
const EVENTOS = [
  { valor: "TEMP_ALTA", rotulo: "Temperatura alta" },
  { valor: "SHIFT_LIGHT", rotulo: "Shift light" },
  { valor: "RPM_ALTO", rotulo: "Giro alto" },
  { valor: "BATERIA_BAIXA", rotulo: "Bateria baixa" },
  { valor: "PERDA_CONEXAO", rotulo: "Perda de conexão" },
  { valor: "LEITURA_INCOMPLETA", rotulo: "Leitura incompleta" },
  { valor: "sem", rotulo: "Sem eventos" },
];

const COLUNAS = [
  { campo: null, rotulo: "Veículo" },
  { campo: "data", rotulo: "Data" },
  { campo: "duracao", rotulo: "Duração" },
  { campo: "rpm_maximo", rotulo: "RPM máx." },
  { campo: "eventos", rotulo: "Eventos" },
];

/** A lista de gravacoes. Filtro e ordem vem da URL. */
export function Sessoes() {
  const navegar = useNavigate();
  const { filtro, aplicar, alternar, remover, limpar } = useFiltrosUrl(PADROES);
  const [sessoes, setSessoes] = useState(null);
  const [veiculos, setVeiculos] = useState([]);
  const [erro, setErro] = useState("");

  const personalizado = filtro.periodo === "personalizado";
  const semEventos = filtro.sem_eventos === "sim";

  useEffect(() => {
    // Inclui arquivados: sessao de carro arquivado continua na lista, e o
    // seletor precisa poder chegar nela.
    api
      .listarVeiculos({ incluir_arquivados: true })
      .then(setVeiculos)
      .catch(() => {});
  }, []);

  useEffect(() => {
    setErro("");
    api
      .listarSessoes({
        veiculo_id: filtro.veiculo_id,
        // "personalizado" nao existe no backend: e so o sinal de que quem
        // manda sao data_inicio e data_fim.
        periodo: personalizado ? "tudo" : filtro.periodo,
        data_inicio: personalizado && filtro.data_inicio ? filtro.data_inicio : "",
        // Fim do dia, senao o proprio dia escolhido ficaria de fora.
        data_fim: personalizado && filtro.data_fim ? `${filtro.data_fim}T23:59:59` : "",
        tipo_evento: filtro.tipo_evento,
        sem_eventos: semEventos,
        ordenar_por: filtro.ordenar_por,
        direcao: filtro.direcao,
      })
      .then(setSessoes)
      .catch((e) => setErro(String(e.message || e)));
  }, [filtro, personalizado, semEventos]);

  /** Periodo e exclusivo; trocar por um atalho descarta o intervalo. */
  function escolherPeriodo(valor) {
    aplicar(
      valor === "personalizado"
        ? { periodo: valor }
        : { periodo: valor, data_inicio: "", data_fim: "" }
    );
  }

  /** "sem" nao e um tipo de evento: vira o parametro proprio do backend. */
  function alternarEvento(valor) {
    if (valor === "sem") {
      aplicar({ sem_eventos: semEventos ? "" : "sim" });
      return;
    }
    alternar("tipo_evento", valor);
  }

  function ordenarPor(campo) {
    if (!campo) return;
    if (filtro.ordenar_por === campo) {
      aplicar({ direcao: filtro.direcao === "asc" ? "desc" : "asc" });
    } else {
      aplicar({ ordenar_por: campo, direcao: direcaoInicial(ORDENACOES, campo) });
    }
  }

  const carro = veiculos.find((v) => String(v.id) === filtro.veiculo_id);
  const marcadosEvento = [...filtro.tipo_evento, ...(semEventos ? ["sem"] : [])];

  // Um chip por valor escolhido: com selecao multipla, tirar um evento nao
  // pode derrubar os outros.
  const ativos = [];
  if (filtro.veiculo_id) {
    ativos.push({
      chave: "veiculo_id",
      rotulo: carro ? placa(carro.placa) || carro.modelo : "veículo",
    });
  }
  if (personalizado && (filtro.data_inicio || filtro.data_fim)) {
    ativos.push({
      chave: "periodo",
      rotulo: `${filtro.data_inicio || "início"} até ${filtro.data_fim || "hoje"}`,
      // Passa pelo mesmo caminho do popover: voltar para "tudo" tem de
      // descartar o intervalo. Sem isto as datas ficariam penduradas na
      // URL, invisiveis, e voltariam sozinhas ao reabrir o personalizado.
      aoRemover: () => escolherPeriodo(PADROES.periodo),
    });
  } else if (filtro.periodo !== PADROES.periodo && !personalizado) {
    ativos.push({
      chave: "periodo",
      rotulo: PERIODOS.find((p) => p.valor === filtro.periodo).rotulo.toLowerCase(),
    });
  }
  for (const tipo of filtro.tipo_evento) {
    ativos.push({
      chave: "tipo_evento",
      valor: tipo,
      rotulo: (ROTULO_EVENTO[tipo] || tipo).toLowerCase(),
    });
  }
  if (semEventos) ativos.push({ chave: "sem_eventos", rotulo: "sem eventos" });

  const periodoEscolhido = PERIODOS.find((p) => p.valor === filtro.periodo);
  const Direcao = filtro.direcao === "asc" ? ArrowUp : ArrowDown;

  if (erro) return <Aviso>{erro}</Aviso>;

  return (
    <>
      <header className={c.paginaTopo}>
        <div>
          <h1 className={c.paginaTitulo}>Sessões</h1>
          <p className={c.paginaSubtitulo}>
            {sessoes === null
              ? "carregando…"
              : `${sessoes.length} ${sessoes.length === 1 ? "listada" : "listadas"}`}
          </p>
        </div>
      </header>

      <div className={c.filtros}>
        <FiltroPopover
          rotulo="Período"
          rotuloAcima={false}
          exclusivo
          opcoes={PERIODOS}
          valor={filtro.periodo}
          onChange={escolherPeriodo}
          resumo={filtro.periodo === PADROES.periodo ? "" : periodoEscolhido?.curto}
        >
          {personalizado && (
            <div className={s.intervalo}>
              <label className={s.intervaloCampo}>
                De
                <input
                  className={`${c.entrada} ${s.data}`}
                  type="date"
                  value={filtro.data_inicio}
                  onChange={(e) => aplicar({ data_inicio: e.target.value })}
                />
              </label>
              <label className={s.intervaloCampo}>
                Até
                <input
                  className={`${c.entrada} ${s.data}`}
                  type="date"
                  value={filtro.data_fim}
                  onChange={(e) => aplicar({ data_fim: e.target.value })}
                />
              </label>
            </div>
          )}
        </FiltroPopover>

        <FiltroPopover
          rotulo="Eventos"
          rotuloAcima={false}
          opcoes={EVENTOS}
          valor={marcadosEvento}
          onChange={alternarEvento}
          resumo={marcadosEvento.length || ""}
        />

        <label className={c.grupoFiltro}>
          <span className={c.rotuloFiltro}>Veículo</span>
          <select
            className={c.selecao}
            value={filtro.veiculo_id}
            onChange={(e) => aplicar({ veiculo_id: e.target.value })}
          >
            <option value="">Todos os veículos</option>
            {veiculos.map((v) => (
              <option key={v.id} value={String(v.id)}>
                {placa(v.placa) || `${v.marca} ${v.modelo}`}
                {v.arquivado_em ? " (arquivado)" : ""}
              </option>
            ))}
          </select>
        </label>

        <DropdownOrdenacao
          opcoes={ORDENACOES}
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
              onClick={() => (a.aoRemover ? a.aoRemover() : remover(a.chave, a.valor))}
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

      {sessoes === null ? (
        <p className={c.paginaVazia}>Carregando…</p>
      ) : sessoes.length === 0 ? (
        <p className={c.paginaVazia}>
          {ativos.length > 0
            ? "Nenhuma sessão bate com esses filtros."
            : "Nenhuma sessão gravada ainda."}
        </p>
      ) : (
        <table className={`${c.tabela} ${s.tabela}`}>
          <thead>
            <tr>
              {COLUNAS.map((coluna) => {
                const ativa = coluna.campo && filtro.ordenar_por === coluna.campo;
                return (
                  <th
                    key={coluna.rotulo}
                    aria-sort={
                      ativa ? (filtro.direcao === "asc" ? "ascending" : "descending") : "none"
                    }
                  >
                    {coluna.campo ? (
                      <button className={c.thBotao} onClick={() => ordenarPor(coluna.campo)}>
                        {coluna.rotulo}
                        {ativa && <Direcao size={14} aria-hidden="true" />}
                      </button>
                    ) : (
                      coluna.rotulo
                    )}
                  </th>
                );
              })}
              <th />
            </tr>
          </thead>
          <tbody>
            {sessoes.map((sessao) => (
              <tr
                key={sessao.id}
                onClick={() => navegar(`/sessoes/${sessao.id}`)}
                tabIndex={0}
                onKeyDown={(e) => e.key === "Enter" && navegar(`/sessoes/${sessao.id}`)}
              >
                <td>
                  <span className={c.placaLinha}>
                    <span className={`${s.placa} ${c.mono}`}>
                      {placa(sessao.veiculo?.placa) || "sem placa"}
                    </span>
                    {sessao.veiculo?.arquivado_em && <Chip>arquivado</Chip>}
                  </span>
                  <span className={c.celulaFraca}>
                    {sessao.veiculo
                      ? `${sessao.veiculo.marca} ${sessao.veiculo.modelo}`
                      : "veículo removido"}
                  </span>
                </td>
                <td className={c.mono}>{dataHora(sessao.iniciada_em)}</td>
                <td className={`${c.mono} ${c.celulaApagada}`}>
                  {duracao(sessao.resumo?.duracao_s)}
                </td>
                {/*
                  Pico nulo = nenhuma amostra da sessao trouxe o bit de valid
                  ligado para rpm. Nao ha numero, entao travessao.
                */}
                <td className={c.mono}>{milhar(sessao.resumo?.rpm_pico)}</td>
                <td>
                  <ChipsEvento tipos={sessao.eventos_notaveis} />
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

function ChipsEvento({ tipos }) {
  if (!tipos || tipos.length === 0) return <span className={c.celulaApagada}>—</span>;
  const [primeiro, ...resto] = tipos;
  return (
    <Chips>
      <Chip tom={GRAVES.has(primeiro) ? "risco" : "alerta"}>
        {ROTULO_EVENTO[primeiro] || primeiro}
      </Chip>
      {resto.length > 0 && <Chip>+{resto.length}</Chip>}
    </Chips>
  );
}
