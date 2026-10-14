/*
  Tela de uma sessao recem-encerrada: o resumo do que acabou de ser
  gravado, com o caminho para a analise e a exportacao.
*/
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api.js";
import { dataHora, duracao, milhar, formatarPlaca } from "../formato.js";
import { Eventos } from "../componentes/telemetria/Eventos.jsx";
import { segundosDesde } from "../componentes/telemetria/graficoApoio.js";
import { aplicarEdicao, KmENotas } from "../componentes/telemetria/KmENotas.jsx";
import { Check } from "lucide-react";
import { Chip } from "../componentes/ui/Chip.jsx";
import { FalhaDeCarga } from "../componentes/ui/FalhaDeCarga.jsx";
import { useCarga } from "../componentes/ui/useCarga.js";
import c from "../estilos/comum.module.css";
import s from "./Sessao.module.css";

/*
  Node 5:529. Sessao curta demais nao chega aqui: o backend a descarta ao
  encerrar, e a tela de AoVivo avisa no lugar.
*/
/** O resumo de uma sessao encerrada, com o caminho para a analise. */
export function Sessao() {
  const { id } = useParams();
  const navegar = useNavigate();
  const { dados, setDados, falha, tentarDeNovo } = useCarga(id, api.lerSessao);

  if (falha) return <FalhaDeCarga recurso="sessao" falha={falha} aoTentar={tentarDeNovo} />;
  if (!dados) return <p className={c.paginaVazia}>Carregando…</p>;

  const { sessao, veiculo, resumo, eventos } = dados;
  const encerrada = sessao.status === "ENCERRADA";

  // O PATCH devolve so o que mudou; a tela troca esses campos no lugar.
  function aplicar(resposta) {
    setDados((atual) => aplicarEdicao(atual, resposta));
  }

  const legenda = [
    formatarPlaca(veiculo?.placa),
    veiculo?.descricao,
    dataHora(sessao.iniciada_em),
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <div className={s.centralizado}>
      <section className={s.cartao}>
        {encerrada && (
          <span className={s.selo}>
            <Check className={s.seloIcone} size={26} aria-hidden="true" />
          </span>
        )}

        <h1 className={s.titulo}>
          {encerrada ? "Sessão encerrada" : "Sessão em andamento"}
        </h1>
        <div className={s.legendaLinha}>
          <p className={c.paginaSubtituloResumo}>{legenda}</p>
          {veiculo?.arquivado_em && <Chip>veículo arquivado</Chip>}
        </div>

        <div className={s.metricas}>
          <Metrica rotulo="Duração" valor={duracao(resumo?.duracao_s)} />
          <Metrica rotulo="RPM máx." valor={milhar(resumo?.rpm_pico)} />
          <Metrica
            rotulo="Vel. máx."
            valor={
              resumo?.vss_pico === null || resumo?.vss_pico === undefined
                ? "—"
                : `${resumo.vss_pico} km/h`
            }
          />
          <Metrica rotulo="Amostras" valor={milhar(resumo?.amostras)} />
        </div>

        <p className={s.secao}>
          {resumo?.eventos === 1 ? "1 evento registrado" : `${resumo?.eventos ?? 0} eventos registrados`}
          {" · "}
          <span className={c.celulaApagada}>
            integridade {resumo?.integridade_pct ?? 0}%
          </span>
        </p>

        <Eventos
          eventos={eventos}
          iniciadaEm={sessao.iniciada_em}
          vazio="Nenhum evento registrado nesta sessão."
          // Cada evento leva a Analise ja com ele escolhido e o zoom no
          // trecho dele. O `t` sozinho e o que os links antigos tinham.
          destino={(e) =>
            `/sessoes/${id}/analise?evento=${e.id}&t=${Math.round(segundosDesde(e.criado_em, sessao.iniciada_em) ?? 0)}`
          }
        />

        <div className={s.acoes}>
          <button
            className={`${c.botao} ${c.botaoCheio}`}
            onClick={() => navegar(veiculo ? `/veiculos/${veiculo.id}` : "/sessoes")}
          >
            {veiculo ? "Voltar ao veículo" : "Voltar às sessões"}
          </button>
          <button
            className={`${c.botao} ${c.botaoPrimario} ${c.botaoCheio}`}
            onClick={() => navegar(`/sessoes/${id}/analise`)}
          >
            Ver análise da sessão
          </button>
        </div>
      </section>

      {/*
        Km e notas, editaveis a qualquer momento: abaixo dos dados da
        sessao, no mesmo card do Ao vivo.
      */}
      <KmENotas
        sessao={sessao}
        kmDoCarro={veiculo?.quilometragem ?? null}
        maisRecente={dados.mais_recente}
        aoSalvar={aplicar}
        classe={s.dados}
      />
    </div>
  );
}

function Metrica({ rotulo, valor }) {
  return (
    <div className={s.metrica}>
      <span className={c.cartaoRotulo}>{rotulo}</span>
      <span className={`${s.metricaValor} ${c.mono}`}>{valor}</span>
    </div>
  );
}
