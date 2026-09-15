/*
  Os graficos da sessao gravada, em Recharts, e as funcoes que preparam a
  serie para eles.

  Mexe aqui quem mudar como a sessao e desenhada na tela de Analise.
*/
import {
  Area,
  AreaChart,
  Brush,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { cronometro, milhar, paraData } from "../../formato.js";
import c from "../../estilos/comum.module.css";
import s from "./GraficoSessao.module.css";

/*
  Amostra com `valid` apagado entra como null e a linha para ali. Os tres
  graficos da Analise usam o mesmo array, para o tooltip e o zoom de um
  valerem nos outros.
*/

// Os sete campos que o firmware publica. A serie carrega todos para os
// graficos poderem compartilhar um array so.
const CAMPOS = ["rpm", "ect", "iat", "vbat", "tps", "vanos", "vss"];

// Vermelho para o que pode danificar o motor ou invalidar a gravacao.
const GRAVES = new Set(["RPM_ALTO", "TEMP_ALTA", "BATERIA_BAIXA", "PERDA_CONEXAO"]);
const ROTINA = new Set(["INICIO_SESSAO", "FIM_SESSAO"]);

const ROTULO_MARCA = {
  SHIFT_LIGHT: "Shift light",
  RPM_ALTO: "Giro acima do limite",
  TEMP_ALTA: "Temperatura alta",
  BATERIA_BAIXA: "Bateria baixa",
  PERDA_CONEXAO: "Perda de conexão",
  LEITURA_INCOMPLETA: "Leitura incompleta",
};

/**
 * Uma linha por amostra: tempo decorrido e cada campo nulo onde `valid`
 * estava apagado. Montada uma vez e passada aos tres graficos, que e o
 * que garante os indices batendo entre eles.
 */
export function serieDaSessao(amostras, inicio) {
  const t0 = paraData(inicio)?.getTime();
  return (amostras || []).map((a) => {
    const d = paraData(a.recebida_em);
    const linha = { t: d && t0 !== undefined ? (d.getTime() - t0) / 1000 : 0 };
    const invalidos = a.invalidos || [];
    for (const campo of CAMPOS) {
      linha[campo] = invalidos.includes(campo) ? null : a[campo];
    }
    return linha;
  });
}

/**
 * Eventos anomalos como posicao no eixo X, em segundos desde o inicio.
 * Os de rotina (inicio e fim da sessao) ficam de fora: eles existem em
 * toda sessao e nao dizem nada sobre o motor.
 */
export function marcasDeEvento(eventos, inicio) {
  const t0 = paraData(inicio)?.getTime();
  if (t0 === undefined) return [];
  return (eventos || [])
    .filter((e) => !ROTINA.has(e.tipo))
    .map((e) => {
      const d = paraData(e.criado_em);
      return d ? { tipo: e.tipo, t: (d.getTime() - t0) / 1000 } : null;
    })
    .filter(Boolean);
}

function Dica({ active, payload, label, titulo, unidade }) {
  if (!active || !payload || payload.length === 0) return null;
  const valor = payload[0].value;
  const ausente = valor === null || valor === undefined;
  return (
    <div className={s.dica}>
      <span className={`${s.dicaInstante} ${c.mono}`}>{cronometro(label)}</span>
      <span className={s.dicaCampo}>{titulo}</span>
      <span className={`${s.dicaValor} ${c.mono} ${ausente ? s.dicaAusente : ""}`.trim()}>
        {ausente ? "sem resposta" : `${milhar(valor)}${unidade ? ` ${unidade}` : ""}`}
      </span>
    </div>
  );
}

/**
 * A serie sem eixo, tooltip nem Brush - a miniatura da previa de
 * exportacao. Campo sem leitura valida devolve null, para quem chama
 * escrever texto no lugar de uma faixa vazia.
 */
export function MiniaturaSerie({ dados, campo, altura = 54 }) {
  const temLeitura = (dados || []).some(
    (linha) => linha[campo] !== null && linha[campo] !== undefined
  );
  if (!temLeitura) return null;

  return (
    <div className={s.miniatura} style={{ height: altura }}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={dados} margin={{ top: 2, right: 0, bottom: 0, left: 0 }}>
          <XAxis dataKey="t" type="number" domain={["dataMin", "dataMax"]} hide />
          <YAxis hide />
          <Area
            type="linear"
            dataKey={campo}
            className={s.serie}
            stroke="currentColor"
            strokeWidth={1.2}
            fill="currentColor"
            isAnimationActive={false}
            dot={false}
            activeDot={false}
            connectNulls={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

export function GraficoSessao({
  titulo,
  campo,
  unidade = "",
  dados,
  marcas = [],
  syncId,
  classe = "",
  legenda = false,
  brush = false,
}) {
  const valores = (dados || [])
    .map((linha) => linha[campo])
    .filter((v) => v !== null && v !== undefined);

  if (valores.length === 0) {
    return (
      <section className={`${c.card} ${c.cardGrafico} ${classe}`}>
        <div className={c.graficoTopo}>
          <span className={s.titulo}>{titulo}</span>
        </div>
        <p className={s.vazio}>
          Nenhuma amostra desta sessão trouxe leitura válida deste campo.
        </p>
      </section>
    );
  }

  let minimo = Math.min(...valores);
  let maximo = Math.max(...valores);
  if (maximo === minimo) {
    // Serie constante: abre um respiro para a linha nao colar na borda.
    minimo -= 1;
    maximo += 1;
  }

  const tiposMarcados = [...new Set(marcas.map((m) => m.tipo))];
  const faixa = `${milhar(minimo)} – ${milhar(maximo)}${unidade ? ` ${unidade}` : ""}`;

  return (
    <section className={`${c.card} ${c.cardGrafico} ${classe}`}>
      <div className={c.graficoTopo}>
        <span className={s.titulo}>{titulo}</span>
        <span className={`${s.faixa} ${c.mono}`}>{faixa}</span>
      </div>

      <div className={`${s.desenho} ${brush ? s.desenhoComBrush : ""}`.trim()}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart
            data={dados}
            syncId={syncId}
            margin={{ top: 14, right: 12, bottom: 0, left: 0 }}
          >
            <CartesianGrid vertical={false} />
            <XAxis
              dataKey="t"
              type="number"
              // O dominio acompanha a fatia visivel, entao o Brush de um
              // grafico reenquadra os tres.
              domain={["dataMin", "dataMax"]}
              tickFormatter={cronometro}
              tickMargin={8}
              minTickGap={40}
            />
            <YAxis
              // Dominio da sessao inteira, e nao da fatia: dar zoom no
              // tempo nao pode reescalar o eixo do valor por baixo, senao
              // o mesmo pico parece maior so porque a janela encolheu. E
              // o que mantem a faixa do cabecalho valendo para o desenho.
              domain={[minimo, maximo]}
              tickFormatter={milhar}
              tickMargin={6}
              width={58}
            />
            <Tooltip
              content={<Dica titulo={titulo} unidade={unidade} />}
              cursor={{ className: s.cursor }}
              isAnimationActive={false}
            />

            {marcas.map((m, i) => (
              <ReferenceLine
                key={`${m.tipo}-${i}`}
                x={m.t}
                className={`${s.marca} ${GRAVES.has(m.tipo) ? s.marcaGrave : ""}`.trim()}
                strokeDasharray="4 4"
                label={{
                  value: ROTULO_MARCA[m.tipo] || m.tipo,
                  position: "top",
                  className: s.marcaRotulo,
                }}
              />
            ))}

            <Area
              type="linear"
              dataKey={campo}
              className={s.serie}
              stroke="currentColor"
              strokeWidth={1.5}
              fill="currentColor"
              isAnimationActive={false}
              dot={false}
              activeDot={{ r: 3, strokeWidth: 0 }}
              // Buraco na leitura e buraco no desenho.
              connectNulls={false}
            />

            {brush && (
              <Brush
                dataKey="t"
                tickFormatter={cronometro}
                height={26}
                travellerWidth={8}
                className={s.brush}
              />
            )}
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {legenda && tiposMarcados.length > 0 && (
        <div className={s.legenda}>
          {tiposMarcados.map((tipo) => (
            <span key={tipo} className={s.legendaItem}>
              <span
                className={`${s.legendaLinha} ${GRAVES.has(tipo) ? s.marcaGrave : ""}`.trim()}
              />
              {ROTULO_MARCA[tipo] || tipo}
            </span>
          ))}
        </div>
      )}
    </section>
  );
}
