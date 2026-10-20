/*
  Tela de Analise: UMA sessao por inteiro - graficos, eventos e metricas.

  O contraste e com /relatorios, que olha varias sessoes. Mexe aqui quem
  mudar como uma gravacao e apresentada.
*/
import { useCallback, useMemo } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api } from "../api.js";
import { dataHora, duracao, milhar, formatarPlaca } from "../formato.js";
import { serieDaSessao } from "../componentes/telemetria/GraficoSessao.jsx";
import { AnaliseGraficos } from "../componentes/telemetria/AnaliseGraficos.jsx";
import { SINAIS_PADRAO } from "../componentes/telemetria/graficoApoio.js";
import { escreverSelecao, lerSelecao } from "../parametros.js";
import { aplicarEdicao, KmENotas } from "../componentes/telemetria/KmENotas.jsx";
import { Metricas } from "../componentes/telemetria/Metricas.jsx";
import { Download } from "lucide-react";
import { Migalha } from "../componentes/ui/Migalha.jsx";
import { FalhaDeCarga } from "../componentes/ui/FalhaDeCarga.jsx";
import { useCarga } from "../componentes/ui/useCarga.js";
import c from "../estilos/comum.module.css";
import s from "./Analise.module.css";

/*
  Node 5:916. O card "Lambda medio" e o botao "Diagnostico" do Figma nao
  entraram: o firmware nao le DTC, e as sondas lambda so aparecem como
  sinal nos graficos (sessao gravada antes dos extras nao tem).
*/

/** Uma sessao inteira: graficos sincronizados, eventos e metricas. */
export function Analise() {
  const { id } = useParams();
  // `?evento=ID&t=SEGUNDOS`: a lista de eventos da tela da sessao manda
  // para ca com o evento escolhido e o zoom no trecho dele. Link antigo, so
  // com `t`: o evento mais perto daquele instante.
  const [parametros, setParametros] = useSearchParams();
  const foco = useMemo(() => {
    const numero = (nome) => {
      const v = parametros.has(nome) ? Number(parametros.get(nome)) : NaN;
      return Number.isFinite(v) ? v : null;
    };
    const evento = numero("evento");
    const t = numero("t");
    return evento === null && t === null ? null : { evento, t };
  }, [parametros]);

  // `?sinais=rpm,maf,lam1`: os sinais escolhidos no seletor da Analise, na
  // query como o resto - o link reabre os mesmos graficos. Vazio volta ao
  // padrao: a Analise precisa de um sinal em destaque.
  const escolhidos = lerSelecao(parametros.get("sinais"), SINAIS_PADRAO);
  const sinais = escolhidos.length ? escolhidos : SINAIS_PADRAO;
  const escolherSinais = useCallback(
    (chaves) => {
      const proximos = new URLSearchParams(parametros);
      const texto = escreverSelecao(chaves, SINAIS_PADRAO);
      if (texto === null) proximos.delete("sinais");
      else proximos.set("sinais", texto);
      setParametros(proximos, { replace: true });
    },
    [parametros, setParametros]
  );
  // Id invalido e 404 viram "esta sessao nao existe"; falha de carga,
  // "Tentar de novo" - o mesmo tratamento de toda tela com :id.
  const { dados, setDados, falha, tentarDeNovo } = useCarga(id, api.lerSessao);

  /*
    Uma serie so para todos os graficos: o cursor e o zoom procuram o
    instante nela, uma vez, e valem em todos. Depende so das amostras:
    salvar km ou notas troca `dados`, e nao pode redesenhar os graficos.
  */
  const amostras = dados?.amostras;
  const iniciadaEm = dados?.sessao?.iniciada_em;
  const serie = useMemo(() => serieDaSessao(amostras, iniciadaEm), [amostras, iniciadaEm]);

  if (falha) return <FalhaDeCarga recurso="sessao" falha={falha} aoTentar={tentarDeNovo} />;
  if (!dados) return <p className={c.paginaVazia}>Carregando…</p>;

  const { sessao, veiculo, resumo, eventos, metricas, limites, trechos } = dados;

  // Vermelho porque o backend registrou TEMP_ALTA nesta sessao, nao porque
  // a tela reavaliou o limite por conta propria.
  const aqueceu = eventos.some((e) => e.tipo === "TEMP_ALTA");

  const legenda = [
    veiculo?.descricao,
    duracao(resumo?.duracao_s),
    `${milhar(resumo?.amostras)} amostras`,
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <>
      <Migalha para={veiculo ? `/veiculos/${veiculo.id}` : "/sessoes"}>
        {formatarPlaca(veiculo?.placa) || "Sessões"}
      </Migalha>

      <header className={c.painelTopo}>
        <div>
          <h1 className={`${s.titulo} ${c.mono}`}>{dataHora(sessao.iniciada_em)}</h1>
          <p className={c.paginaSubtituloPainel}>{legenda}</p>
        </div>
        <div className={c.acoes}>
          <Link className={`${c.botao} ${c.botaoPrimario}`} to={`/sessoes/${id}/exportar`}>
            <Download className={c.botaoIcone} size={20} aria-hidden="true" />
            Exportar
          </Link>
        </div>
      </header>

      <div className={`${c.cartoes} ${c.cartoesAnalise}`}>
        <Cartao rotulo="RPM máx." valor={milhar(resumo?.rpm_pico)} />
        <Cartao
          rotulo="Vel. máx."
          valor={
            resumo?.vss_pico === null || resumo?.vss_pico === undefined
              ? "—"
              : `${resumo.vss_pico} km/h`
          }
        />
        <Cartao
          rotulo="Temp. máx."
          valor={
            resumo?.ect_pico === null || resumo?.ect_pico === undefined
              ? "—"
              : `${resumo.ect_pico} °C`
          }
          alerta={aqueceu}
        />
        <Cartao rotulo="Eventos" valor={milhar(resumo?.eventos)} />
      </div>

      {/*
        Barra de leitura, grafico em destaque com as trilhas, minimapa e,
        ao lado (ou embaixo, em tela estreita), eventos por tipo,
        qualidade do dado e as notas: tudo na mesma janela de tempo.
      */}
      <AnaliseGraficos
        serie={serie}
        eventos={eventos}
        inicio={sessao.iniciada_em}
        limites={limites}
        trechos={trechos}
        foco={foco}
        sinais={sinais}
        aoMudarSinais={escolherSinais}
        notas={
          <KmENotas
            sessao={sessao}
            kmDoCarro={veiculo?.quilometragem ?? null}
            maisRecente={dados.mais_recente}
            aoSalvar={(resposta) => setDados((atual) => aplicarEdicao(atual, resposta))}
          />
        }
      />

      {/*
        Metricas calculadas (servicos/metricas.py), nas quatro categorias
        que o backend agrupa. Vem no mesmo GET da sessao, que ja carrega a
        serie - nao ha chamada extra.
      */}
      <h2 className={s.secao}>Métricas da sessão</h2>
      <Metricas metricas={metricas} />
    </>
  );
}

function Cartao({ rotulo, valor, alerta }) {
  return (
    <div className={c.cartao}>
      <span className={c.cartaoRotulo}>{rotulo}</span>
      <span className={`${c.cartaoValor} ${c.mono} ${alerta ? s.valorAlerta : ""}`.trim()}>
        {valor}
      </span>
    </div>
  );
}
