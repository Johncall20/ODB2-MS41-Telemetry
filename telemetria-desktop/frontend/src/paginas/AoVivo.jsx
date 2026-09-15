/*
  Painel ao vivo: o que a central esta respondendo agora.

  E a mesma tela nos dois estados, gravando ou nao - nao ha uma tela de
  "gravando" separada. Mexe aqui quem mudar o painel do mecanico.
*/
import { useCallback, useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useTelemetria } from "../hooks/useTelemetria.js";
import { api } from "../api.js";
import { cronometro, milhar, paraData, placa } from "../formato.js";
import { BarraGiro, Leitura } from "../componentes/telemetria/Leitura.jsx";
import { Traco } from "../componentes/telemetria/Traco.jsx";
import { Eventos } from "../componentes/telemetria/Eventos.jsx";
import { Circle, Square } from "lucide-react";
import { Aviso } from "../componentes/ui/Aviso.jsx";
import { Migalha } from "../componentes/ui/Migalha.jsx";
import c from "../estilos/comum.module.css";
import s from "./AoVivo.module.css";

/*
  Nodes 5:106 e 5:307 - a mesma tela nos dois estados. MAP, lambda e
  codigos de falha do Figma nao entraram: o firmware nao le nada disso.
*/

const JANELA_GRAFICO = 60; // "ultimos 60 s" do Figma, a 1 Hz nominal

const DESCRICAO_LEITOR = {
  DESLIGADO: "leitor parado",
  PROCURANDO: "procurando o módulo",
  CONECTADO: "adaptador conectado",
  ERRO: "falha no link",
};

function rotuloSinal(estado) {
  return estado === "CONECTADO" ? "Lendo · não gravando" : DESCRICAO_LEITOR[estado] || estado;
}

function classeSinal(gravando, estado) {
  if (gravando) return s.pontoGravando;
  if (estado === "CONECTADO") return s.pontoOk;
  if (estado === "ERRO") return s.pontoErro;
  return s.pontoProcurando;
}

/** O painel do mecanico: a leitura corrente, gravando ou nao. */
export function AoVivo() {
  const { amostra, historico, eventos, leitor, conectadoWs, status, gravadas, recarregarStatus } =
    useTelemetria();
  const [parametros] = useSearchParams();
  const navegar = useNavigate();

  const [veiculos, setVeiculos] = useState([]);
  const [veiculoId, setVeiculoId] = useState(parametros.get("veiculo") || "");
  const [limites, setLimites] = useState({ shift_light_rpm: 6200, rpm_alto: 6800 });
  const [ocupado, setOcupado] = useState(false);
  const [erro, setErro] = useState("");
  const [descarte, setDescarte] = useState("");
  const [agora, setAgora] = useState(Date.now());

  useEffect(() => {
    api
      .listarVeiculos()
      .then((lista) => {
        setVeiculos(lista);
        setVeiculoId((atual) => atual || (lista[0] ? String(lista[0].id) : ""));
      })
      .catch(() => {});
    fetch("/api/limites")
      .then((r) => r.json())
      .then(setLimites)
      .catch(() => {});
  }, []);

  const gravando = Boolean(status?.gravando);
  const sessao = status?.sessao;

  // Cronometro da sessao: so precisa de tique enquanto grava.
  useEffect(() => {
    if (!gravando) return undefined;
    const t = setInterval(() => setAgora(Date.now()), 1000);
    return () => clearInterval(t);
  }, [gravando]);

  const alternarGravacao = useCallback(async () => {
    setErro("");
    setDescarte("");
    setOcupado(true);
    try {
      if (gravando) {
        const resultado = await api.encerrarSessao();
        await recarregarStatus();
        // Sessao curta demais nao chega a existir: o backend apagou. Nao ha
        // tela de sessao encerrada para abrir, entao o aviso fica aqui.
        if (resultado.descartada) {
          setDescarte(
            `Sessão descartada, curta demais para análise — ${resultado.amostras} ` +
              `${resultado.amostras === 1 ? "amostra" : "amostras"}, o mínimo é ${resultado.minimo}.`
          );
          return;
        }
        // Encerrar leva para o resumo da sessao (node 5:529), como no Figma.
        navegar(`/sessoes/${resultado.sessao_id}`);
        return;
      } else {
        if (!veiculoId) {
          setErro("Cadastre um veículo antes de gravar.");
          return;
        }
        await api.iniciarSessao(Number(veiculoId));
      }
      await recarregarStatus();
    } catch (e) {
      setErro(String(e.message || e));
    } finally {
      setOcupado(false);
    }
  }, [gravando, veiculoId, recarregarStatus, navegar]);

  const invalidos = amostra?.invalidos || [];
  const parado = (campo) => invalidos.includes(campo);

  // Gravando, o carro e o da sessao; fora dela, o escolhido no seletor.
  const veiculoAtivo =
    veiculos.find((v) => v.id === (sessao?.veiculo_id ?? Number(veiculoId))) || null;

  const inicio = paraData(sessao?.iniciada_em);
  const decorrido = gravando && inicio ? (agora - inicio.getTime()) / 1000 : 0;
  const recentes = historico.slice(-JANELA_GRAFICO);

  return (
    <>
      <Migalha para={veiculoAtivo ? `/veiculos/${veiculoAtivo.id}` : "/veiculos"}>
        {veiculoAtivo
          ? placa(veiculoAtivo.placa) || `${veiculoAtivo.marca} ${veiculoAtivo.modelo}`
          : "Veículos"}
      </Migalha>

      <header className={c.painelTopo}>
        <div>
          <h1 className={`${s.titulo} ${c.mono}`}>{gravando ? cronometro(decorrido) : "Ao vivo"}</h1>
          <p className={c.paginaSubtituloPainel}>
            {gravando
              ? `Sessão em andamento · iniciada às ${inicio?.toLocaleTimeString("pt-BR", {
                  hour: "2-digit",
                  minute: "2-digit",
                })}`
              : [
                  veiculoAtivo && `${veiculoAtivo.marca} ${veiculoAtivo.modelo}`,
                  veiculoAtivo?.ano,
                  DESCRICAO_LEITOR[leitor.estado] || leitor.estado,
                ]
                  .filter(Boolean)
                  .join(" · ")}
          </p>
        </div>

        <div className={c.acoes}>
          <span className={s.sinal}>
            <span className={`${s.ponto} ${classeSinal(gravando, leitor.estado)}`} />
            {gravando ? `Gravando · ${milhar(gravadas)} amostras` : rotuloSinal(leitor.estado)}
          </span>

          {!gravando && (
            <select
              className={c.selecao}
              value={veiculoId}
              onChange={(e) => setVeiculoId(e.target.value)}
              aria-label="Veículo da sessão"
            >
              {veiculos.length === 0 && <option value="">nenhum veículo cadastrado</option>}
              {veiculos.map((v) => (
                <option key={v.id} value={v.id}>
                  {placa(v.placa) || `${v.marca} ${v.modelo}`}
                </option>
              ))}
            </select>
          )}

          <button
            className={`${c.botao} ${gravando ? c.botaoEncerrar : c.botaoPrimario}`}
            onClick={alternarGravacao}
            disabled={ocupado}
          >
            {gravando ? (
              <Square className={c.botaoIcone} size={20} aria-hidden="true" />
            ) : (
              <Circle className={c.botaoIcone} size={20} aria-hidden="true" />
            )}
            {gravando ? "Encerrar sessão" : "Gravar sessão"}
          </button>
        </div>
      </header>

      {!conectadoWs && (
        <Aviso>
          Sem ligação com o backend. Confira se o servidor está rodando; a página
          reconecta sozinha.
        </Aviso>
      )}
      {erro && <Aviso>{erro}</Aviso>}
      {descarte && <Aviso atencao>{descarte}</Aviso>}

      <div className={s.grade}>
        <Leitura rotulo="RPM" valor={amostra?.rpm} invalido={parado("rpm")} largo>
          <BarraGiro
            rpm={amostra?.rpm}
            invalido={parado("rpm")}
            shift={limites.shift_light_rpm}
            alto={limites.rpm_alto}
          />
        </Leitura>
        <Leitura rotulo="Velocidade" valor={amostra?.vss} unidade="km/h" invalido={parado("vss")} />
        <Leitura rotulo="Temp. do motor" valor={amostra?.ect} unidade="°C" invalido={parado("ect")} />
        <Leitura rotulo="TPS" valor={amostra?.tps} unidade="%" casas={1} invalido={parado("tps")} />
        {/*
          VANOS e IAT nao aparecem em tela nenhuma do Figma, mas o firmware
          entrega os dois. Ocupam o lugar que era de MAP e Lambda.
        */}
        <Leitura rotulo="VANOS" valor={amostra?.vanos} unidade="%" casas={1} invalido={parado("vanos")} />
        <Leitura rotulo="Temp. do ar" valor={amostra?.iat} unidade="°C" invalido={parado("iat")} />
        <Leitura rotulo="Bateria" valor={amostra?.vbat} unidade="V" casas={2} invalido={parado("vbat")} />
      </div>

      <div className={s.graficos}>
        <Grafico
          titulo={`RPM · últimos ${JANELA_GRAFICO} s`}
          atual={parado("rpm") ? "––" : milhar(amostra?.rpm ?? null)}
          historico={recentes}
          campo="rpm"
          teto={7000}
          classe={s.tracoRpm}
        />
        <Grafico
          titulo={`Velocidade · últimos ${JANELA_GRAFICO} s`}
          atual={parado("vss") ? "––" : `${amostra?.vss ?? 0} km/h`}
          historico={recentes}
          campo="vss"
          teto={240}
          classe={s.tracoVss}
        />
      </div>

      <section className={`${c.card} ${s.eventos}`}>
        <span className={c.cardRotulo}>Eventos</span>
        <Eventos eventos={eventos} iniciadaEm={sessao?.iniciada_em} />
      </section>
    </>
  );
}

function Grafico({ titulo, atual, historico, campo, teto, classe }) {
  return (
    <div className={c.card}>
      <div className={c.graficoTopo}>
        <span className={c.cardRotulo}>{titulo}</span>
        <span className={`${s.atual} ${c.mono}`}>{atual}</span>
      </div>
      <Traco historico={historico} campo={campo} teto={teto} classe={classe} />
    </div>
  );
}
