/*
  O unico websocket do app: amostra, evento e estado do leitor.

  Toda tela que mostra dado ao vivo usa este hook, nunca abre socket
  proprio - dois sockets receberiam as mesmas mensagens e dobrariam o
  trabalho do backend a toa.
*/
import { useCallback, useEffect, useRef, useState } from "react";

const TAMANHO_HISTORICO = 180; // 3 minutos a 1 Hz

/**
 * Liga no /ws e devolve o que esta acontecendo agora no carro. Reconecta
 * sozinho: o backend pode ser reiniciado no meio do uso.
 */
export function useTelemetria() {
  const [amostra, setAmostra] = useState(null);
  const [historico, setHistorico] = useState([]);
  const [eventos, setEventos] = useState([]);
  const [leitor, setLeitor] = useState({ estado: "DESLIGADO", detalhe: "" });
  const [conectadoWs, setConectadoWs] = useState(false);
  const [gravadas, setGravadas] = useState(0);
  const [status, setStatus] = useState(null);
  const wsRef = useRef(null);

  /** Repuxa /api/status. O websocket avisa o que muda; isto e para o que
   *  ja tinha acontecido antes de a tela abrir. */
  const recarregarStatus = useCallback(async () => {
    try {
      const r = await fetch("/api/status");
      setStatus(await r.json());
    } catch {
      /* backend fora do ar, o proprio ws ja sinaliza */
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
        recarregarStatus();
      };

      ws.onmessage = (ev) => {
        const { tipo, dados } = JSON.parse(ev.data);
        if (tipo === "amostra") {
          setAmostra(dados);
          setHistorico((h) => [...h, dados].slice(-TAMANHO_HISTORICO));
          // Conta aqui em vez de perguntar ao backend a cada ciclo: o
          // numero exato so importa ao encerrar, e ai o resumo manda.
          if (dados.gravando) setGravadas((n) => n + 1);
        } else if (tipo === "evento") {
          setEventos((e) => [dados, ...e].slice(0, 60));
        } else if (tipo === "leitor") {
          setLeitor(dados);
        } else if (tipo === "sessao") {
          if (dados.status === "ATIVA") {
            setHistorico([]);
            setEventos([]);
            setGravadas(0);
          }
          recarregarStatus();
        }
      };

      const cair = () => {
        setConectadoWs(false);
        if (vivo) timer = setTimeout(conectar, 1500);
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

  return {
    amostra,
    historico,
    eventos,
    leitor,
    conectadoWs,
    status,
    gravadas,
    recarregarStatus,
  };
}
