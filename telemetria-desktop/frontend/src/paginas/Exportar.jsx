/*
  Tela de exportacao: escolher formato, recortar o conteudo do PDF e
  baixar.

  A previa mostra o que o relatorio vai conter de verdade, nao um enfeite.
*/
import { useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api.js";
import { dataHora, duracao, milhar, formatarPlaca } from "../formato.js";
import { Check, Download } from "lucide-react";
import { Aviso } from "../componentes/ui/Aviso.jsx";
import { FalhaDeCarga } from "../componentes/ui/FalhaDeCarga.jsx";
import { useCarga } from "../componentes/ui/useCarga.js";
import { Migalha } from "../componentes/ui/Migalha.jsx";
import { MiniaturaSerie, serieDaSessao } from "../componentes/telemetria/GraficoSessao.jsx";
import c from "../estilos/comum.module.css";
import s from "./Exportar.module.css";

/*
  Node 5:1365. A caixa de codigos de falha do Figma nao entrou - o firmware
  nao le DTC. As caixas de conteudo so valem para o PDF.
*/

/*
  As series que o PDF desenha, na ordem em que saem nele. Espelha
  SERIES_PDF de servicos/exportador.py - mexeu la, mexa aqui, senao a
  previa promete um grafico que o relatorio nao traz.
*/
const SERIES_PDF = [
  { campo: "rpm", nome: "RPM" },
  { campo: "vss", nome: "velocidade" },
  { campo: "ect", nome: "temperatura" },
];

/** "RPM, velocidade e temperatura" - lista com "e" antes do ultimo. */
function listar(nomes) {
  if (nomes.length <= 1) return nomes.join("");
  return `${nomes.slice(0, -1).join(", ")} e ${nomes[nomes.length - 1]}`;
}

const FORMATOS = [
  { id: "pdf", nome: "PDF", nota: "para o cliente" },
  { id: "csv", nome: "CSV", nota: "para planilha" },
  { id: "json", nome: "JSON", nota: "dados brutos" },
];

/** Escolha do formato e do conteudo, com previa do que sera gerado. */
export function Exportar() {
  const { id } = useParams();
  const navegar = useNavigate();
  const { dados, falha, tentarDeNovo } = useCarga(id, api.lerSessao);
  // O download e por fetch: erro dele vira aviso aqui, sem trocar a pagina.
  const [baixando, setBaixando] = useState(false);
  const [erroDownload, setErroDownload] = useState("");
  const [formato, setFormato] = useState("pdf");
  const [secoes, setSecoes] = useState({
    resumo: true,
    graficos: true,
    eventos: true,
    amostras: false,
  });

  const escolhidas = useMemo(
    () => Object.entries(secoes).filter(([, v]) => v).map(([k]) => k),
    [secoes]
  );

  const serie = useMemo(
    () => serieDaSessao(dados?.amostras, dados?.sessao?.iniciada_em),
    [dados]
  );

  /*
    So as series com leitura valida, como faz o exportador: prometer tres
    graficos e entregar dois seria a previa mentindo.
  */
  const seriesIncluidas = useMemo(
    () =>
      SERIES_PDF.filter(({ campo }) =>
        serie.some((linha) => linha[campo] !== null && linha[campo] !== undefined)
      ),
    [serie]
  );

  if (falha) return <FalhaDeCarga recurso="sessao" falha={falha} aoTentar={tentarDeNovo} />;
  if (!dados) return <p className={c.paginaVazia}>Carregando…</p>;

  const { sessao, veiculo, resumo } = dados;
  const ehPdf = formato === "pdf";
  const nada = ehPdf && escolhidas.length === 0;

  async function baixar() {
    setErroDownload("");
    setBaixando(true);
    try {
      await api.baixarExportacao(id, formato, escolhidas);
    } catch (falha) {
      setErroDownload(falha.message);
    } finally {
      setBaixando(false);
    }
  }

  const conteudo = [
    { id: "resumo", rotulo: "Resumo da sessão" },
    { id: "graficos", rotulo: "Gráficos de RPM, velocidade e temperatura" },
    { id: "eventos", rotulo: "Eventos registrados" },
    { id: "amostras", rotulo: `Todas as ${milhar(resumo?.amostras)} amostras` },
  ];

  return (
    <>
      <Migalha para={`/sessoes/${id}/analise`}>
        Análise da sessão
      </Migalha>

      <header className={c.paginaTopo}>
        <div>
          <h1 className={c.paginaTitulo}>Exportar relatório</h1>
          <p className={c.paginaSubtitulo}>
            {[formatarPlaca(veiculo?.placa), `sessão de ${dataHora(sessao.iniciada_em)}`]
              .filter(Boolean)
              .join(" · ")}
          </p>
        </div>
      </header>

      <div className={s.exportar}>
        <section className={`${c.card} ${c.cardExportar}`}>
          <span className={c.cardRotulo}>Formato</span>
          <div className={s.formatos}>
            {FORMATOS.map((f) => (
              <button
                key={f.id}
                type="button"
                className={`${s.formato} ${formato === f.id ? s.formatoAtivo : ""}`.trim()}
                onClick={() => setFormato(f.id)}
                aria-pressed={formato === f.id}
              >
                <span className={`${s.formatoNome} ${c.mono}`}>{f.nome}</span>
                <span className={s.formatoNota}>{f.nota}</span>
              </button>
            ))}
          </div>

          <span className={`${c.cardRotulo} ${s.rotuloSecao}`}>Conteúdo</span>
          {!ehPdf && (
            <p className={s.nota}>
              {formato === "csv"
                ? "O CSV sai com uma linha por amostra e as sete colunas do firmware."
                : "O JSON sai com veículo, sessão, resumo, amostras e eventos."}{" "}
              O recorte abaixo só vale para o PDF.
            </p>
          )}
          <ul className={s.opcoes}>
            {conteudo.map((item) => (
              <li key={item.id}>
                <label className={`${s.opcao} ${ehPdf ? "" : s.opcaoInativa}`.trim()}>
                  <input
                    type="checkbox"
                    checked={ehPdf && secoes[item.id]}
                    disabled={!ehPdf}
                    onChange={() =>
                      setSecoes((atual) => ({ ...atual, [item.id]: !atual[item.id] }))
                    }
                  />
                  <span className={s.caixa} aria-hidden="true">
                    <Check size={13} strokeWidth={3} />
                  </span>
                  {item.rotulo}
                </label>
              </li>
            ))}
          </ul>
        </section>

        <section className={`${c.card} ${c.cardExportar}`}>
          <span className={c.cardRotulo}>Prévia</span>
          <div className={s.previa}>
            <p className={s.previaTitulo}>Relatório de sessão</p>
            <p className={`${s.previaLegenda} ${c.mono}`}>
              {[formatarPlaca(veiculo?.placa), veiculo?.descricao,
                dataHora(sessao.iniciada_em)]
                .filter(Boolean)
                .join(" · ")}
            </p>
            <div className={s.previaRisco} />

            {(!ehPdf || secoes.resumo) && (
              <>
                <LinhaPrevia rotulo="Duração" valor={duracao(resumo?.duracao_s)} />
                <LinhaPrevia rotulo="RPM máximo" valor={milhar(resumo?.rpm_pico)} />
                <LinhaPrevia
                  rotulo="Temperatura máxima"
                  valor={
                    resumo?.ect_pico === null || resumo?.ect_pico === undefined
                      ? "—"
                      : `${resumo.ect_pico} °C`
                  }
                />
                <LinhaPrevia rotulo="Integridade" valor={`${resumo?.integridade_pct ?? 0}%`} />
                <LinhaPrevia rotulo="Eventos" valor={milhar(resumo?.eventos)} />
              </>
            )}

            {/*
              Miniatura de verdade, desenhada com a serie da sessao, e nao
              um retangulo decorativo: o que a previa mostra tem de ser o
              que o relatorio traz. Sem nenhuma serie valida sobra a frase,
              que e o que o PDF tambem faz nesse caso.
            */}
            {ehPdf && secoes.graficos && (
              <div className={s.previaGraficos}>
                {seriesIncluidas.length > 0 && (
                  <>
                    <MiniaturaSerie dados={serie} campo={seriesIncluidas[0].campo} />
                    <p className={s.previaGraficosNota}>
                      {seriesIncluidas.length === 1
                        ? `1 gráfico: ${seriesIncluidas[0].nome}`
                        : `${seriesIncluidas.length} gráficos: ${listar(
                            seriesIncluidas.map((x) => x.nome)
                          )}`}
                      <span className={s.previaGraficosDica}>
                        acima, {seriesIncluidas[0].nome}
                      </span>
                    </p>
                  </>
                )}
                {seriesIncluidas.length === 0 && (
                  <p className={s.previaGraficosNota}>
                    Nenhum gráfico: esta sessão não trouxe leitura válida de RPM,
                    velocidade nem temperatura.
                  </p>
                )}
              </div>
            )}

            {ehPdf && secoes.amostras && (
              <p className={s.nota}>
                A tabela de amostras acrescenta {milhar(resumo?.amostras)} linhas ao PDF.
              </p>
            )}
          </div>
        </section>
      </div>

      {erroDownload && <Aviso>{erroDownload}</Aviso>}

      <div className={s.acoes}>
        <button className={c.botao} type="button" onClick={() => navegar(`/sessoes/${id}/analise`)}>
          Cancelar
        </button>
        {nada ? (
          <button className={`${c.botao} ${c.botaoPrimario}`} type="button" disabled>
            Escolha ao menos uma seção
          </button>
        ) : (
          // O nome do arquivo e o que o backend manda no Content-Disposition
          // (o api.js o le); a tela nao monta nome nenhum.
          <button
            className={`${c.botao} ${c.botaoPrimario}`}
            type="button"
            onClick={baixar}
            disabled={baixando}
          >
            <Download className={c.botaoIcone} size={20} aria-hidden="true" />
            {baixando
              ? ehPdf
                ? "Gerando PDF…"
                : "Baixando…"
              : ehPdf
                ? "Gerar PDF"
                : `Baixar ${formato.toUpperCase()}`}
          </button>
        )}
      </div>
    </>
  );
}

function LinhaPrevia({ rotulo, valor }) {
  return (
    <div className={s.previaLinha}>
      <span>{rotulo}</span>
      <span className={s.previaValor}>{valor}</span>
    </div>
  );
}
