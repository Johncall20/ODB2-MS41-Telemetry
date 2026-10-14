/*
  O unico websocket do app, montado uma vez no Shell.

  Antes cada chamada de useTelemetria() abria um socket proprio: com a
  sidebar tambem consumindo telemetria seriam dois ou mais, recebendo as
  mesmas mensagens e dobrando o trabalho do backend a toa. Agora a conexao
  vive aqui e o hook so le o que ela produziu.

  Como o provider fica FORA das rotas, o estado sobrevive a navegacao - e
  isso muda o que cada coisa significa; ver os comentarios de `sessao`.
*/
import { createContext, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, avisarSessaoExpirada } from "../api.js";

const TAMANHO_HISTORICO = 180; // 3 minutos a 1 Hz

// 1008 e o fechamento que o backend usa para "sem login" (no handshake ou
// quando o token vence com o socket aberto). Reconectar nao adianta.
const SEM_LOGIN = 1008;

export const ContextoTelemetria = createContext(null);

/** Abre o socket e reparte o que chega. Um por app, no Shell. */
export function TelemetriaProvider({ children }) {
  const [amostra, setAmostra] = useState(null);
  const [historico, setHistorico] = useState([]);
  const [eventos, setEventos] = useState([]);
  const [leitor, setLeitor] = useState({ estado: "DESLIGADO", detalhe: "" });
  const [conectadoWs, setConectadoWs] = useState(false);
  // Quando a ultima amostra CHEGOU, pelo relogio desta maquina (o `t_ms`
  // e o do ESP32). E dele que a tela tira "sem leitura ha X s": o socket
  // pode estar de pe com o BLE caido, e ai simplesmente nada chega.
  const [chegouEm, setChegouEm] = useState(null);
  // Quando o socket caiu (null com ele de pe): o cronometro da gravacao
  // para ali, porque dali em diante nada confirma que ela continua.
  const [caiuEm, setCaiuEm] = useState(null);
  const [gravadas, setGravadas] = useState(0);
  const [status, setStatus] = useState(null);
  const wsRef = useRef(null);
  // O status tambem em ref: o onmessage e criado uma vez e enxergaria
  // sempre o primeiro valor do state. A ref e o que esta valendo agora.
  const statusRef = useRef(null);

  /** Repuxa /api/status. O websocket avisa o que muda; isto e para o que
   *  ja tinha acontecido antes de a tela abrir. */
  const recarregarStatus = useCallback(async () => {
    // Pelo api.js, como toda chamada: um 401 aqui e sessao expirada (vai
    // ao login), e uma resposta de erro nunca vira o "status" da tela.
    try {
      const novo = await api.status();
      statusRef.current = novo;
      setStatus(novo);
    } catch {
      /* servidor fora do ar: o proprio ws ja sinaliza, e o api.js ja
         registrou o detalhe no console */
    }
  }, []);

  useEffect(() => {
    let vivo = true;
    let timer;

    function conectar() {
      const protocolo = location.protocol === "https:" ? "wss" : "ws";
      const ws = new WebSocket(`${protocolo}://${location.host}/ws`);
      wsRef.current = ws;

      ws.onopen = () => {
        setConectadoWs(true);
        setCaiuEm(null);
        recarregarStatus();
      };

      ws.onmessage = (ev) => {
        const { tipo, dados } = JSON.parse(ev.data);
        if (tipo === "amostra") {
          setAmostra(dados);
          setChegouEm(Date.now());
          setHistorico((h) => [...h, dados].slice(-TAMANHO_HISTORICO));
          // Conta aqui em vez de perguntar ao backend a cada ciclo: o
          // numero exato so importa ao encerrar, e ai o resumo manda.
          if (dados.gravando) setGravadas((n) => n + 1);

          // Cada amostra carrega `gravando`, entao ela e a fonte mais
          // fresca do estado da gravacao. Divergiu do status que a
          // sidebar mostra, o status e que esta velho: repuxa uma vez.
          // E o que corrige a sidebar quando a sessao termina por fora do
          // Ao vivo - backend reiniciado, por exemplo. Sem polling: so
          // dispara na divergencia, e a proxima amostra ja concorda.
          if (Boolean(dados.gravando) !== Boolean(statusRef.current?.gravando)) {
            recarregarStatus();
          }
        } else if (tipo === "evento") {
          setEventos((e) => [dados, ...e].slice(0, 60));
        } else if (tipo === "leitor") {
          setLeitor(dados);
        } else if (tipo === "sessao") {
          if (dados.status === "ATIVA") {
            // Os eventos sao da sessao: comecou outra, a lista zera, senao
            // a gravacao nova apareceria com as anomalias da anterior.
            setEventos([]);
            setGravadas(0);
            // O historico NAO zera. Ele e a faixa dos ultimos minutos de
            // leitura, nao um recorte da sessao - o painel ao vivo mostra
            // o carro, que continua o mesmo de um segundo para o outro.
          }
          recarregarStatus();
        }
      };

      const cair = (ev) => {
        setConectadoWs(false);
        setCaiuEm((antes) => antes ?? Date.now());
        if (!vivo) return;
        // Sessao vencida (ou logout em outra aba): reconectar daria 1008
        // de novo a cada 1,5 s, para sempre. Para, e o provider de
        // autenticacao leva ao login com "Sua sessão expirou".
        if (ev?.code === SEM_LOGIN) {
          avisarSessaoExpirada();
          return;
        }
        timer = setTimeout(conectar, 1500);
      };
      ws.onclose = cair;
      ws.onerror = () => ws.close();
    }

    conectar();
    recarregarStatus();
    return () => {
      vivo = false;
      clearTimeout(timer);
      wsRef.current?.close();
    };
  }, [recarregarStatus]);

  const valor = useMemo(
    () => ({
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
    }),
    [amostra, historico, eventos, leitor, conectadoWs, chegouEm, caiuEm, status, gravadas, recarregarStatus]
  );

  return <ContextoTelemetria.Provider value={valor}>{children}</ContextoTelemetria.Provider>;
}
