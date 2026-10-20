/*
  Painel ao vivo: o que a central esta respondendo agora.

  E a mesma tela nos dois estados, gravando ou nao - nao ha uma tela de
  "gravando" separada. Mexe aqui quem mudar o painel do mecanico.

  O que TRAVA quando a gravacao comeca (limites e km) e escolhido no popup
  "Nova sessão", que abre ao clicar em "Gravar sessão". O que continua
  editavel (as notas) fica na pagina, nos dois estados.
*/
import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useTelemetria } from "../hooks/useTelemetria.js";
import { api } from "../api.js";
import {
  anoVeiculo,
  cronometro,
  formatarPlaca,
  milhar,
  paraData,
  resumoLimites,
} from "../formato.js";
import { BarraGiro, Leitura } from "../componentes/telemetria/Leitura.jsx";
import { Traco } from "../componentes/telemetria/Traco.jsx";
import { linhasDeLimite } from "../componentes/telemetria/graficoApoio.js";
import { Eventos } from "../componentes/telemetria/Eventos.jsx";
import {
  limitesDePartida,
  numericos,
  useInicioSessao,
} from "../componentes/telemetria/LimitesSessao.jsx";
import { NovaSessao } from "../componentes/telemetria/NovaSessao.jsx";
import { SeletorParametros } from "../componentes/telemetria/SeletorParametros.jsx";
import { PARAMETROS, escreverSelecao, lerSelecao } from "../parametros.js";
import { CampoNotas, NotasSessao } from "../componentes/telemetria/NotasSessao.jsx";
import { Circle, Square } from "lucide-react";
import { Aviso } from "../componentes/ui/Aviso.jsx";
import { Migalha } from "../componentes/ui/Migalha.jsx";
import c from "../estilos/comum.module.css";
import s from "./AoVivo.module.css";

/*
  Nodes 5:106 e 5:307 - a mesma tela nos dois estados. MAP e codigos de
  falha do Figma nao entraram: o firmware nao le nada disso. Os cards sao
  os parametros que o firmware publica (parametros.js), e quem esta na
  tela escolhe quais ver.
*/

const JANELA_GRAFICO = 60; // "ultimos 60 s" do Figma, a 1 Hz nominal

// Sem amostra nova por mais que isto, a leitura na tela e velha: a 1 Hz
// sao tres ciclos perdidos, o mesmo DT_MAXIMO_S do backend.
const LIMITE_PARADA_S = 3;

/** "8 s", "2 min": ha quanto tempo nao chega leitura. */
function haQuanto(segundos) {
  return segundos < 60 ? `${Math.floor(segundos)} s` : `${Math.floor(segundos / 60)} min`;
}

const DESCRICAO_LEITOR = {
  DESLIGADO: "leitor parado",
  PROCURANDO: "procurando o módulo",
  CONECTADO: "adaptador conectado",
  ERRO: "falha no link",
};

const ORIGEM_PARTIDA = {
  ultima: "da última sessão",
  sugeridos: "sugeridos",
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
  const {
    amostra,
    historico,
    eventos,
    leitor,
    conectadoWs,
    chegouEm,
    caiuEm,
    status,
    gravadas,
    recarregarStatus,
  } = useTelemetria();
  const [parametros, setParametros] = useSearchParams();
  const navegar = useNavigate();

  // null enquanto a lista nao chegou: "nenhum veiculo cadastrado" so vale
  // para a lista que veio vazia, nao para a que falhou.
  const [veiculos, setVeiculos] = useState(null);
  const [erroVeiculos, setErroVeiculos] = useState("");
  const [veiculoId, setVeiculoId] = useState(parametros.get("veiculo") || "");
  const [ocupado, setOcupado] = useState(false);
  const [erro, setErro] = useState("");
  const [descarte, setDescarte] = useState("");
  const [agora, setAgora] = useState(Date.now());
  // O popup "Nova sessão". So abre pelo botao, nunca ao entrar na tela ou
  // ao trocar de carro.
  const [abrindo, setAbrindo] = useState(false);
  // As notas da PROXIMA sessao, antes de gravar. Vao no POST que inicia;
  // gravando, a tela mostra as da sessao (status.sessao).
  const [notas, setNotas] = useState("");

  useEffect(() => {
    api
      .listarVeiculos()
      .then((lista) => {
        setVeiculos(lista);
        setVeiculoId((atual) => atual || (lista[0] ? String(lista[0].id) : ""));
      })
      .catch((falha) => {
        setVeiculos([]);
        setErroVeiculos(falha.message);
      });
  }, []);

  const gravando = Boolean(status?.gravando);
  const sessao = status?.sessao;

  /*
    O carro escolhido vai para a query, sem localStorage: voltar para
    /ao-vivo?veiculo=3 tem de reabrir no mesmo carro, e o link tem de
    poder ser mandado. `replace` porque trocar de carro no seletor nao e
    navegacao - senao o botao Voltar percorreria cada carro testado.
  */
  const escolherVeiculo = useCallback(
    (id) => {
      setVeiculoId(id);
      const proximos = new URLSearchParams(parametros);
      if (id) proximos.set("veiculo", id);
      else proximos.delete("veiculo");
      setParametros(proximos, { replace: true });
    },
    [parametros, setParametros]
  );

  // Quais cards o painel mostra. Na query, pelo mesmo motivo do carro: o
  // link reabre o mesmo painel. O padrao nao escreve nada na URL.
  const visiveis = lerSelecao(parametros.get("parametros"));
  const escolherParametros = useCallback(
    (chaves) => {
      const proximos = new URLSearchParams(parametros);
      const texto = escreverSelecao(chaves);
      if (texto === null) proximos.delete("parametros");
      else proximos.set("parametros", texto);
      setParametros(proximos, { replace: true });
    },
    [parametros, setParametros]
  );

  // De onde a proxima sessao parte (ultima sessao do carro ou sugeridos)
  // e o km do carro. Recarrega ao trocar de carro e ao comecar/terminar.
  const { inicio: inicioSessao, erro: erroInicio } = useInicioSessao(veiculoId, gravando);
  const partida = limitesDePartida(inicioSessao);

  // O perfil da ECU contra a fonte do processo, decidido pelo backend: com
  // o adaptador BLE, outro perfil nao grava (`bloqueia`) e o nao informado
  // so avisa. Com o simulador vem null. Gravando nao se repete o aviso.
  const perfil = gravando ? null : inicioSessao?.perfil_ecu || null;

  // A barra de giro marca o que dispara evento: gravando, os limites DA
  // SESSAO (o snapshot que o detector usa); antes, os de partida, que sao
  // os que o popup abre marcados.
  const limites = (gravando ? status?.limites : numericos(partida?.valores)) || null;

  // Um tique por segundo, sempre: e o cronometro da sessao e o relogio que
  // diz ha quanto tempo nao chega leitura.
  useEffect(() => {
    const t = setInterval(() => setAgora(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);

  // Gravando, encerra; fora da gravacao, so abre o popup - quem inicia e
  // ele.
  const alternarGravacao = useCallback(async () => {
    setErro("");
    setDescarte("");
    if (!gravando) {
      if (!veiculoId) {
        setErro("Cadastre um veículo antes de gravar.");
        return;
      }
      setAbrindo(true);
      return;
    }
    setOcupado(true);
    try {
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
    } catch (e) {
      setErro(String(e.message || e));
    } finally {
      setOcupado(false);
    }
  }, [gravando, veiculoId, recarregarStatus, navegar]);

  // O popup iniciou a sessao: fecha, e as notas ja estao nela.
  const aoIniciar = useCallback(async () => {
    setAbrindo(false);
    setNotas("");
    await recarregarStatus();
  }, [recarregarStatus]);

  // Notas da sessao em curso: PATCH explicito, e o status recarrega para a
  // tela continuar mostrando o que esta gravado.
  const salvarNotas = useCallback(
    async (texto) => {
      await api.editarSessao(sessao.id, { observacao: texto });
      await recarregarStatus();
    },
    [sessao?.id, recarregarStatus]
  );

  const invalidos = amostra?.invalidos || [];
  const parado = (campo) => invalidos.includes(campo);

  /*
    Leitura parada: a ultima amostra chegou ha mais de LIMITE_PARADA_S. Vale
    para o socket caido e para o BLE caido (o socket de pe, e nada vem):
    nos dois casos o numero na tela e velho, e a regra do `valid` vale
    igual - nao se mostra como medicao o que nao foi medido agora.
  */
  const idade = amostra && chegouEm ? (agora - chegouEm) / 1000 : null;
  const semLeitura = idade !== null && idade > LIMITE_PARADA_S ? `sem leitura há ${haQuanto(idade)}` : null;

  // Gravando sem socket: nada confirma que a gravacao continua (o servidor
  // pode ter caido com ela). O rotulo diz isso, o cronometro para no
  // momento da queda e a sidebar para de pulsar.
  const semConfirmacao = gravando && !conectadoWs;
  // Gravando com o socket de pe e o modulo sumido: a sessao continua
  // aberta, mas sem leitura - o trecho vira PERDA_CONEXAO na analise.
  const moduloCaiu = gravando && conectadoWs && leitor.estado !== "CONECTADO";
  const interrompida = !gravando ? status?.interrompida : null;

  // [o que se ve de longe, o motivo em letra menor embaixo (ou null)]
  let rotuloSituacao;
  if (semConfirmacao) rotuloSituacao = ["Gravação sem confirmação", "sem ligação com o servidor"];
  else if (moduloCaiu) rotuloSituacao = [`Gravando · ${DESCRICAO_LEITOR[leitor.estado] || leitor.estado}`, null];
  else if (gravando) rotuloSituacao = [`Gravando · ${milhar(gravadas)} amostras`, null];
  else rotuloSituacao = [rotuloSinal(leitor.estado), null];

  let classePonto;
  if (semConfirmacao) classePonto = "";
  else if (moduloCaiu) classePonto = s.pontoProcurando;
  else classePonto = classeSinal(gravando, leitor.estado);

  async function cienteDaInterrupcao() {
    try {
      await api.cienteInterrupcao();
    } catch (falha) {
      setErro(String(falha.message || falha));
    }
    await recarregarStatus();
  }

  // Gravando, o carro e o da sessao; fora dela, o escolhido no seletor.
  const veiculoAtivo =
    (veiculos || []).find((v) => v.id === (sessao?.veiculo_id ?? Number(veiculoId))) || null;

  const inicio = paraData(sessao?.iniciada_em);
  const fimDoCronometro = semConfirmacao && caiuEm ? caiuEm : agora;
  const decorrido = gravando && inicio ? (fimDoCronometro - inicio.getTime()) / 1000 : 0;
  const recentes = historico.slice(-JANELA_GRAFICO);

  return (
    <>
      <Migalha para={veiculoAtivo ? `/veiculos/${veiculoAtivo.id}` : "/veiculos"}>
        {veiculoAtivo
          ? formatarPlaca(veiculoAtivo.placa) || veiculoAtivo.descricao
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
                  veiculoAtivo?.descricao,
                  anoVeiculo(veiculoAtivo),
                  DESCRICAO_LEITOR[leitor.estado] || leitor.estado,
                ]
                  .filter(Boolean)
                  .join(" · ")}
          </p>
          {/*
            Gravando, o que travou no inicio - limites e km - fica a vista,
            so de leitura. Mudar, so na proxima sessao.
          */}
          {gravando && (
            <p className={s.travados}>
              {[
                resumoLimites(status?.limites, true),
                sessao?.km !== null && sessao?.km !== undefined
                  ? `${milhar(sessao.km)} km`
                  : "km não informado",
              ]
                .filter(Boolean)
                .join(" · ")}
            </p>
          )}
        </div>

        <div className={c.acoes}>
          <span className={s.sinal}>
            <span className={`${s.ponto} ${classePonto}`.trim()} />
            <span className={s.sinalTexto}>
              {rotuloSituacao[0]}
              {rotuloSituacao[1] && <span className={s.sinalDetalhe}>{rotuloSituacao[1]}</span>}
            </span>
          </span>

          {/*
            Travado enquanto grava, nao escondido: a sessao pertence a um
            carro, e sumir com o seletor deixaria a tela sem responder qual
            e. Desabilitado ele mostra o carro e recusa a troca.
          */}
          <select
            className={c.selecao}
            value={gravando ? String(sessao?.veiculo_id ?? "") : veiculoId}
            onChange={(e) => escolherVeiculo(e.target.value)}
            disabled={gravando}
            aria-label={gravando ? "Veículo da sessão em andamento" : "Veículo da sessão"}
          >
            {veiculos === null && <option value="">carregando…</option>}
            {veiculos?.length === 0 && (
              <option value="">
                {erroVeiculos ? "lista indisponível" : "nenhum veículo cadastrado"}
              </option>
            )}
            {(veiculos || []).map((v) => (
              <option key={v.id} value={v.id}>
                {formatarPlaca(v.placa) || v.descricao}
              </option>
            ))}
          </select>

          <button
            className={`${c.botao} ${gravando ? c.botaoEncerrar : c.botaoPrimario}`}
            onClick={alternarGravacao}
            disabled={ocupado || (!gravando && (!inicioSessao || perfil?.bloqueia))}
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

      {!conectadoWs &&
        (gravando ? (
          <Aviso>
            Sem ligação com o servidor. Não dá para confirmar se a gravação continua: o
            cronômetro parou no momento da queda. A página reconecta sozinha e mostra o estado
            real.
          </Aviso>
        ) : (
          <Aviso>
            Sem ligação com o servidor. Confira se ele está rodando; a página reconecta sozinha.
          </Aviso>
        ))}
      {moduloCaiu && (
        <Aviso atencao>
          O módulo parou de responder durante a gravação. A sessão continua aberta e o trecho sem
          leitura fica marcado na análise; a leitura volta sozinha quando o módulo reaparecer.
        </Aviso>
      )}
      {interrompida && (
        <Aviso atencao>
          {interrompida.descartada ? (
            <>
              A gravação anterior foi interrompida porque o servidor reiniciou. Ela tinha{" "}
              {milhar(interrompida.amostras)} {interrompida.amostras === 1 ? "amostra" : "amostras"}{" "}
              (o mínimo é {interrompida.minimo}) e foi descartada.{" "}
            </>
          ) : (
            <>
              A gravação anterior foi interrompida porque o servidor reiniciou. A sessão foi
              encerrada na última amostra recebida, com {milhar(interrompida.amostras)} amostras.{" "}
              <Link to={`/sessoes/${interrompida.sessao_id}`}>Ver a sessão</Link>{" "}
            </>
          )}
          <button type="button" className={s.entendi} onClick={cienteDaInterrupcao}>
            Entendi
          </button>
        </Aviso>
      )}
      {perfil && (
        <Aviso atencao={!perfil.bloqueia}>
          {perfil.mensagem}{" "}
          {veiculoId && <Link to={`/veiculos/${veiculoId}/editar`}>Editar o cadastro do carro</Link>}
        </Aviso>
      )}
      {erroVeiculos && (
        <Aviso>Não foi possível carregar a lista de veículos: {erroVeiculos}</Aviso>
      )}
      {erroInicio && !gravando && (
        <Aviso>Não foi possível preparar a gravação deste carro: {erroInicio}</Aviso>
      )}
      {erro && <Aviso>{erro}</Aviso>}
      {descarte && <Aviso atencao>{descarte}</Aviso>}

      <div className={s.gradeTopo}>
        <SeletorParametros selecionados={visiveis} aoMudar={escolherParametros} />
      </div>

      <div className={s.grade}>
        {/*
          Os cards saem do catalogo (parametros.js), na ordem dele, so os
          escolhidos. O RPM e o unico diferente: largo, com a barra de giro.
        */}
        {PARAMETROS.filter((p) => visiveis.includes(p.chave)).map((p) =>
          p.chave === "rpm" ? (
            <Leitura key="rpm" rotulo={p.rotulo} valor={amostra?.rpm} invalido={parado("rpm")} semLeitura={semLeitura} largo>
              <BarraGiro
                rpm={amostra?.rpm}
                // Leitura parada nao acende bloco: seria giro de segundos atras.
                invalido={parado("rpm") || Boolean(semLeitura)}
                shift={limites?.shift_light_rpm}
                alto={limites?.rpm_alto}
              />
              {/*
                Antes de gravar: o que a barra esta marcando e de onde vem. Sem
                controles - a escolha e feita no popup, ao clicar em gravar.
              */}
              {!gravando && partida && (
                <p className={s.limitesPartida}>
                  {resumoLimites(numericos(partida.valores))} · {ORIGEM_PARTIDA[partida.origem]}
                </p>
              )}
            </Leitura>
          ) : (
            <Leitura
              key={p.chave}
              rotulo={p.rotulo}
              valor={amostra?.[p.chave]}
              unidade={p.unidade}
              casas={p.casas}
              invalido={parado(p.chave)}
              semLeitura={semLeitura}
            />
          )
        )}
        {visiveis.length === 0 && (
          <p className={`${c.paginaVazia} ${s.gradeVazia}`}>
            Nenhum parâmetro escolhido. Use o botão Parâmetros para montar o painel.
          </p>
        )}
      </div>

      <div className={s.graficos}>
        <Grafico
          titulo={`RPM · últimos ${JANELA_GRAFICO} s`}
          atual={parado("rpm") || semLeitura ? "––" : milhar(amostra?.rpm ?? null)}
          historico={recentes}
          campo="rpm"
          teto={7000}
          // Os mesmos limites que a barra de giro marca: os da sessao em
          // curso, ou os de partida antes de gravar. Velocidade nao tem
          // limite, entao so o RPM ganha linhas.
          limites={linhasDeLimite("rpm", limites)}
          classe={s.tracoRpm}
          parado={semLeitura}
        />
        <Grafico
          titulo={`Velocidade · últimos ${JANELA_GRAFICO} s`}
          atual={parado("vss") || semLeitura ? "––" : `${amostra?.vss ?? 0} km/h`}
          historico={recentes}
          campo="vss"
          teto={240}
          classe={s.tracoVss}
          parado={semLeitura}
        />
      </div>

      <section className={`${c.card} ${s.eventos}`}>
        <span className={c.cardRotulo}>Eventos</span>
        <Eventos
          eventos={eventos}
          iniciadaEm={sessao?.iniciada_em}
          // Gravando, a lista vazia e "nada ate agora", nao "comece a gravar".
          vazio={gravando ? "Nenhum evento nesta sessão até agora." : undefined}
        />
      </section>

      {/*
        Notas: o que continua editavel durante a gravacao, por isso fica na
        pagina e nao no popup. Antes de gravar, o texto vai junto no inicio
        da sessao; gravando, salva por PATCH com botao explicito.
      */}
      {(gravando || veiculoId) && (
        <section className={`${c.card} ${s.notas}`} aria-label="Notas da sessão">
          {gravando ? (
            <NotasSessao salvo={sessao?.observacao} aoSalvar={salvarNotas} />
          ) : (
            <CampoNotas valor={notas} aoMudar={setNotas} rotulo="Notas da próxima sessão" />
          )}
        </section>
      )}

      {abrindo && veiculoAtivo && (
        <NovaSessao
          veiculo={veiculoAtivo}
          inicio={inicioSessao}
          notas={notas}
          aoIniciar={aoIniciar}
          aoFechar={() => setAbrindo(false)}
        />
      )}
    </>
  );
}

function Grafico({ titulo, atual, historico, campo, teto, limites, classe, parado }) {
  return (
    <div className={c.card}>
      <div className={c.graficoTopo}>
        <span className={c.cardRotulo}>{titulo}</span>
        <span className={`${s.atual} ${c.mono}`}>{atual}</span>
      </div>
      <Traco historico={historico} campo={campo} teto={teto} limites={limites} classe={classe} parado={parado} />
    </div>
  );
}
