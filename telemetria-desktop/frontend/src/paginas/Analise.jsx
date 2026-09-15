/*
  Tela de Analise: UMA sessao por inteiro - graficos, eventos e metricas.

  O contraste e com /relatorios, que olha varias sessoes. Mexe aqui quem
  mudar como uma gravacao e apresentada.
*/
import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api.js";
import { dataHora, duracao, milhar, placa } from "../formato.js";
import {
  GraficoSessao,
  marcasDeEvento,
  serieDaSessao,
} from "../componentes/telemetria/GraficoSessao.jsx";
import { Metricas } from "../componentes/telemetria/Metricas.jsx";
import { Download } from "lucide-react";
import { Aviso } from "../componentes/ui/Aviso.jsx";
import { Migalha } from "../componentes/ui/Migalha.jsx";
import c from "../estilos/comum.module.css";
import s from "./Analise.module.css";

/*
  Node 5:916. O card "Lambda medio" e o botao "Diagnostico" do Figma nao
  entraram: o firmware nao le sonda nem DTC.
*/

// Um syncId por tela basta: os graficos que se sincronizam sao os desta.
const SYNC = "analise-sessao";

/** Uma sessao inteira: graficos sincronizados, eventos e metricas. */
export function Analise() {
  const { id } = useParams();
  const [dados, setDados] = useState(null);
  const [erro, setErro] = useState("");

  useEffect(() => {
    setDados(null);
    api
      .lerSessao(id)
      .then(setDados)
      .catch((e) => setErro(String(e.message || e)));
  }, [id]);

  /*
    Uma serie so para os tres graficos: e o que faz o tooltip e o zoom de
    um valerem nos outros.
  */
  const serie = useMemo(
    () => serieDaSessao(dados?.amostras, dados?.sessao?.iniciada_em),
    [dados]
  );
  const marcas = useMemo(
    () => marcasDeEvento(dados?.eventos, dados?.sessao?.iniciada_em),
    [dados]
  );

  if (erro) return <Aviso>{erro}</Aviso>;
  if (!dados) return <p className={c.paginaVazia}>Carregando…</p>;

  const { sessao, veiculo, resumo, eventos, metricas } = dados;

  // Vermelho porque o backend registrou TEMP_ALTA nesta sessao, nao porque
  // a tela reavaliou o limite por conta propria.
  const aqueceu = eventos.some((e) => e.tipo === "TEMP_ALTA");

  const legenda = [
    veiculo && `${veiculo.marca} ${veiculo.modelo}`,
    duracao(resumo?.duracao_s),
    `${milhar(resumo?.amostras)} amostras`,
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <>
      <Migalha para={veiculo ? `/veiculos/${veiculo.id}` : "/sessoes"}>
        {placa(veiculo?.placa) || "Sessões"}
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
        syncId igual nos tres: passar o mouse em um mostra o tooltip nos
        tres no mesmo instante da sessao, e o Brush do primeiro reenquadra
        os outros dois. O Brush fica so no primeiro de proposito - tres
        controles de zoom para uma escala de tempo so seriam tres jeitos de
        dizer a mesma coisa.
      */}
      <div className={s.graficos}>
        <GraficoSessao
          titulo="RPM"
          campo="rpm"
          dados={serie}
          marcas={marcas}
          syncId={SYNC}
          classe={s.rpm}
          brush
        />
        <GraficoSessao
          titulo="Velocidade"
          campo="vss"
          unidade="km/h"
          dados={serie}
          marcas={marcas}
          syncId={SYNC}
          classe={s.vss}
        />
        <GraficoSessao
          titulo="Temperatura do motor"
          campo="ect"
          unidade="°C"
          dados={serie}
          marcas={marcas}
          syncId={SYNC}
          classe={s.ect}
          legenda
        />
      </div>

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
