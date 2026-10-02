/*
  Tela de Relatorios: VARIAS sessoes - evolucao, frequencia de eventos e
  comparacao entre duas gravacoes.

  O contraste e com /sessoes/:id/analise, que olha uma sessao so.
*/
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "../api.js";
import { ROTULO_EVENTO, dataHora, duracao, milhar, paraData, placa } from "../formato.js";
import { Aviso } from "../componentes/ui/Aviso.jsx";
import { Chip } from "../componentes/ui/Chip.jsx";
import { FiltroPopover } from "../componentes/ui/FiltroPopover.jsx";
import { useFiltrosUrl } from "../componentes/ui/useFiltrosUrl.js";
import c from "../estilos/comum.module.css";
import s from "./Relatorios.module.css";

const PADROES = {
  veiculo_id: "",
  periodo: "tudo",
  a: "",
  b: "",
};

const PERIODOS = [
  { valor: "tudo", rotulo: "Todo o período", curto: "tudo" },
  { valor: "7d", rotulo: "Últimos 7 dias", curto: "7 dias" },
  { valor: "30d", rotulo: "Últimos 30 dias", curto: "30 dias" },
  { valor: "90d", rotulo: "Últimos 90 dias", curto: "90 dias" },
];

// As tres series da evolucao. Escalas muito diferentes (rpm na casa dos
// milhares, temperatura em dezenas, integridade em porcento), entao sao
// tres graficos e nao tres linhas no mesmo eixo.
const SERIES = [
  { campo: "rpm_pico", titulo: "RPM máximo por sessão", unidade: "", classe: "rpm" },
  { campo: "ect_pico", titulo: "Temperatura máxima por sessão", unidade: "°C", classe: "ect" },
  { campo: "integridade_pct", titulo: "Integridade por sessão", unidade: "%", classe: "integridade" },
];

const SYNC = "relatorio-evolucao";

function dia(iso) {
  const d = paraData(iso);
  return d ? d.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" }) : "";
}

function DicaEvolucao({ active, payload, titulo, unidade }) {
  if (!active || !payload || payload.length === 0) return null;
  const ponto = payload[0];
  const valor = ponto.value;
  const linha = ponto.payload;
  return (
    <div className={s.dica}>
      <span className={`${s.dicaInstante} ${c.mono}`}>{dataHora(linha.iniciada_em)}</span>
      <span className={s.dicaCampo}>{titulo}</span>
      <span className={`${s.dicaValor} ${c.mono}`}>
        {valor === null || valor === undefined
          ? "sem valor calculado"
          : `${milhar(valor)}${unidade ? ` ${unidade}` : ""}`}
      </span>
    </div>
  );
}

/**
 * Uma serie da evolucao. X e o instante da sessao, nao o indice: por
 * indice, tres sessoes do mesmo dia pareceriam espalhadas na semana.
 * Sessao sem valor calculado entra como null e a linha para ali.
 */
function GraficoEvolucao({ dados, campo, titulo, unidade, classe }) {
  const temValor = dados.some((d) => d[campo] !== null && d[campo] !== undefined);

  return (
    <section className={`${c.card} ${c.cardGrafico} ${s[classe]}`}>
      <div className={c.graficoTopo}>
        <span className={s.tituloGrafico}>{titulo}</span>
      </div>
      {!temValor ? (
        <p className={s.vazioNota}>
          Nenhuma sessão deste período tem esse valor calculado.
        </p>
      ) : (
        <div className={s.desenho}>
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={dados} syncId={SYNC} margin={{ top: 12, right: 12, bottom: 0, left: 0 }}>
              <CartesianGrid vertical={false} />
              <XAxis
                dataKey="quando"
                type="number"
                domain={["dataMin", "dataMax"]}
                tickFormatter={(v) => dia(new Date(v).toISOString())}
                tickMargin={8}
                minTickGap={40}
              />
              <YAxis tickFormatter={milhar} tickMargin={6} width={58} />
              <Tooltip
                content={<DicaEvolucao titulo={titulo} unidade={unidade} />}
                cursor={{ className: s.cursor }}
                isAnimationActive={false}
              />
              <Area
                type="linear"
                dataKey={campo}
                className={s.serie}
                stroke="currentColor"
                strokeWidth={1.5}
                fill="currentColor"
                isAnimationActive={false}
                dot={{ r: 2.5, strokeWidth: 0 }}
                connectNulls={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </section>
  );
}

/** Varias sessoes: evolucao, frequencia de eventos e comparacao. */
export function Relatorios() {
  const { filtro, aplicar } = useFiltrosUrl(PADROES);
  const [veiculos, setVeiculos] = useState([]);
  const [frota, setFrota] = useState(null);
  const [evolucao, setEvolucao] = useState(null);
  const [eventos, setEventos] = useState(null);
  const [comparacao, setComparacao] = useState(null);
  const [erro, setErro] = useState("");

  useEffect(() => {
    api
      .listarVeiculos({ incluir_arquivados: true })
      .then(setVeiculos)
      .catch(() => {});
  }, []);

  useEffect(() => {
    setErro("");
    Promise.all([
      api.lerFrota(filtro.periodo),
      api.lerEventosAgregados({ veiculo_id: filtro.veiculo_id, periodo: filtro.periodo }),
    ])
      .then(([f, e]) => {
        setFrota(f);
        setEventos(e);
      })
      .catch((e) => setErro(String(e.message || e)));
  }, [filtro.periodo, filtro.veiculo_id]);

  useEffect(() => {
    if (!filtro.veiculo_id) {
      setEvolucao(null);
      return;
    }
    api
      .lerEvolucao(filtro.veiculo_id, filtro.periodo)
      .then(setEvolucao)
      .catch((e) => setErro(String(e.message || e)));
  }, [filtro.veiculo_id, filtro.periodo]);

  useEffect(() => {
    if (!filtro.a || !filtro.b || filtro.a === filtro.b) {
      setComparacao(null);
      return;
    }
    api
      .lerComparacao(filtro.a, filtro.b)
      .then(setComparacao)
      .catch((e) => setComparacao({ erro: String(e.message || e) }));
  }, [filtro.a, filtro.b]);

  const periodoEscolhido = PERIODOS.find((p) => p.valor === filtro.periodo);
  const carro = veiculos.find((v) => String(v.id) === filtro.veiculo_id);
  // O eixo X precisa de numero, entao a data vira epoch.
  const serieEvolucao = (evolucao?.sessoes || []).map((linha) => ({
    ...linha,
    quando: paraData(linha.iniciada_em)?.getTime() ?? 0,
  }));

  if (erro) return <Aviso>{erro}</Aviso>;

  return (
    <>
      <header className={c.paginaTopo}>
        <div>
          <h1 className={c.paginaTitulo}>Relatórios</h1>
          <p className={c.paginaSubtitulo}>
            {frota
              ? [
                  `${milhar(frota.resumo.sessoes)} ${frota.resumo.sessoes === 1 ? "sessão" : "sessões"}`,
                  `${milhar(frota.resumo.veiculos)} ${frota.resumo.veiculos === 1 ? "veículo" : "veículos"}`,
                  `${duracao(frota.resumo.tempo_total_s)} gravados`,
                ].join(" · ")
              : "carregando…"}
          </p>
        </div>
      </header>

      <div className={c.filtros}>
        <label className={c.grupoFiltro}>
          <span className={c.rotuloFiltro}>Veículo</span>
          <select
            className={c.selecao}
            value={filtro.veiculo_id}
            onChange={(e) => aplicar({ veiculo_id: e.target.value, a: "", b: "" })}
          >
            <option value="">Toda a frota</option>
            {veiculos.map((v) => (
              <option key={v.id} value={String(v.id)}>
                {placa(v.placa) || `${v.marca} ${v.modelo}`}
                {v.arquivado_em ? " (arquivado)" : ""}
              </option>
            ))}
          </select>
        </label>

        <FiltroPopover
          rotulo="Período"
          rotuloAcima={false}
          exclusivo
          opcoes={PERIODOS}
          valor={filtro.periodo}
          onChange={(valor) => aplicar({ periodo: valor })}
          resumo={filtro.periodo === PADROES.periodo ? "" : periodoEscolhido?.curto}
        />
      </div>

      {/* ------------------------------------------------------ evolucao */}
      <h2 className={s.secao}>Evolução do veículo</h2>
      {!filtro.veiculo_id ? (
        <p className={s.aviso}>
          Escolha um veículo acima para ver como as sessões dele evoluíram.
        </p>
      ) : serieEvolucao.length === 0 ? (
        <p className={s.aviso}>
          {placa(carro?.placa) || "Este veículo"} não tem sessão encerrada neste período.
        </p>
      ) : (
        <div className={s.graficos}>
          {SERIES.map((serie) => (
            <GraficoEvolucao key={serie.campo} dados={serieEvolucao} {...serie} />
          ))}
        </div>
      )}

      {/* ------------------------------------------------------- eventos */}
      <h2 className={s.secao}>Frequência de eventos</h2>
      <div className={s.duasColunas}>
        <section className={`${c.card} ${s.bloco}`}>
          <span className={c.cardRotulo}>Por tipo</span>
          {(eventos?.por_tipo || []).length === 0 ? (
            <p className={s.vazioNota}>Nenhum evento anômalo neste recorte.</p>
          ) : (
            <table className={s.tabelinha}>
              <thead>
                <tr>
                  <th>Evento</th>
                  <th>Ocorrências</th>
                  <th>Sessões</th>
                </tr>
              </thead>
              <tbody>
                {eventos.por_tipo.map((t) => (
                  <tr key={t.tipo}>
                    <td>{ROTULO_EVENTO[t.tipo] || t.tipo}</td>
                    <td className={c.mono}>{milhar(t.total)}</td>
                    <td className={c.mono}>{milhar(t.sessoes)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>

        <section className={`${c.card} ${s.bloco}`}>
          <span className={c.cardRotulo}>Por dia</span>
          {(eventos?.por_dia || []).length === 0 ? (
            <p className={s.vazioNota}>Nenhum evento anômalo neste recorte.</p>
          ) : (
            <div className={s.desenhoBarras}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={eventos.por_dia} margin={{ top: 12, right: 12, bottom: 0, left: 0 }}>
                  <CartesianGrid vertical={false} />
                  <XAxis dataKey="dia" tickMargin={8} minTickGap={20} />
                  <YAxis allowDecimals={false} tickMargin={6} width={40} />
                  <Tooltip cursor={{ className: s.cursorBarra }} isAnimationActive={false} />
                  <Bar dataKey="total" name="eventos" className={s.barra} fill="currentColor" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </section>
      </div>

      <section className={`${c.card} ${s.bloco}`}>
        <span className={c.cardRotulo}>Por veículo</span>
        {(frota?.por_veiculo || []).length === 0 ? (
          <p className={s.vazioNota}>Nenhum evento anômalo neste período.</p>
        ) : (
          <table className={s.tabelinha}>
            <thead>
              <tr>
                <th>Veículo</th>
                <th>Ocorrências</th>
                <th>Sessões</th>
              </tr>
            </thead>
            <tbody>
              {frota.por_veiculo.map((v) => (
                <tr key={v.veiculo_id}>
                  <td>
                    <span className={c.placaLinha}>
                      <Link className={s.link} to={`/veiculos/${v.veiculo_id}`}>
                        {placa(v.placa) || `${v.marca} ${v.modelo}`}
                      </Link>
                      {v.arquivado_em && <Chip>arquivado</Chip>}
                    </span>
                  </td>
                  <td className={c.mono}>{milhar(v.total)}</td>
                  <td className={c.mono}>{milhar(v.sessoes)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {/* ---------------------------------------------------- comparacao */}
      <h2 className={s.secao}>Comparar duas sessões</h2>
      {!filtro.veiculo_id ? (
        <p className={s.aviso}>
          Escolha um veículo acima. A comparação é sempre entre sessões do mesmo
          carro — pico de RPM de carros diferentes não diz nada.
        </p>
      ) : serieEvolucao.length < 2 ? (
        <p className={s.aviso}>
          {placa(carro?.placa) || "Este veículo"} precisa de pelo menos duas sessões
          encerradas neste período para haver o que comparar.
        </p>
      ) : (
        <>
          <div className={s.escolhaSessoes}>
            <SeletorSessao
              rotulo="Sessão A"
              sessoes={evolucao.sessoes}
              valor={filtro.a}
              onChange={(v) => aplicar({ a: v })}
            />
            <SeletorSessao
              rotulo="Sessão B"
              sessoes={evolucao.sessoes}
              valor={filtro.b}
              onChange={(v) => aplicar({ b: v })}
            />
          </div>

          {comparacao?.erro ? (
            <Aviso>{comparacao.erro}</Aviso>
          ) : !comparacao ? (
            <p className={s.aviso}>Escolha duas sessões diferentes.</p>
          ) : (
            <TabelaComparacao dados={comparacao} />
          )}
        </>
      )}
    </>
  );
}

function SeletorSessao({ rotulo, sessoes, valor, onChange }) {
  return (
    <label className={c.grupoFiltro}>
      <span className={c.rotuloFiltro}>{rotulo}</span>
      <select className={c.selecao} value={valor} onChange={(e) => onChange(e.target.value)}>
        <option value="">Escolher…</option>
        {sessoes.map((s2) => (
          <option key={s2.sessao_id} value={String(s2.sessao_id)}>
            {dataHora(s2.iniciada_em)} · {duracao(s2.duracao_s)}
          </option>
        ))}
      </select>
    </label>
  );
}

/**
 * A tabela lado a lado. A coluna de diferenca vem pronta do backend
 * (servicos/metricas.comparar) - aqui so se escolhe a cor do sinal.
 */
function TabelaComparacao({ dados }) {
  const [a, b] = dados.sessoes;

  const formatar = (valor, casas, unidade) => {
    if (valor === null || valor === undefined) return "—";
    const texto = casas ? Number(valor).toFixed(casas).replace(".", ",") : milhar(valor);
    return unidade ? `${texto} ${unidade}` : texto;
  };

  return (
    <div className={`${c.card} ${s.bloco}`}>
      <table className={`${s.tabelinha} ${s.tabelaComparacao}`}>
        <thead>
          <tr>
            <th />
            <th>{dataHora(a.sessao.iniciada_em)}</th>
            <th>{dataHora(b.sessao.iniciada_em)}</th>
            <th>Diferença</th>
          </tr>
        </thead>
        <tbody>
          {dados.comparacao.map((linha) => (
            <tr key={`${linha.grupo}-${linha.campo}`}>
              <td>
                {linha.rotulo}
                {/*
                  Limite diferente nos dois lados: a diferenca nao foi
                  calculada de proposito, e a nota diz por que. Sem ela o
                  travessao pareceria falta de medicao.
                */}
                {linha.limites_diferentes && (
                  <span className={s.notaLimite}>
                    limites diferentes: {formatar(linha.limite_a, 0, "")} ·{" "}
                    {formatar(linha.limite_b, 0, "")}
                  </span>
                )}
              </td>
              <td className={c.mono}>{formatar(linha.a, linha.casas, linha.unidade)}</td>
              <td className={c.mono}>{formatar(linha.b, linha.casas, linha.unidade)}</td>
              <td
                className={`${c.mono} ${
                  linha.diferenca === null || linha.diferenca === 0
                    ? s.difNeutra
                    : linha.diferenca > 0
                      ? s.difPositiva
                      : s.difNegativa
                }`}
              >
                {linha.diferenca === null
                  ? "—"
                  : `${linha.diferenca > 0 ? "+" : ""}${formatar(
                      linha.diferenca,
                      linha.casas,
                      linha.unidade
                    )}`}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className={s.vazioNota}>
        A diferença é a segunda sessão menos a primeira. Travessão significa que
        uma das duas não tem esse valor medido — não que sejam iguais. Onde as
        duas sessões usaram limites diferentes a diferença também fica em
        travessão: os dois lados responderam perguntas diferentes.
      </p>
    </div>
  );
}
