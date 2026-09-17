import { duracao, milhar } from "../../formato.js";
import c from "../../estilos/comum.module.css";
import s from "./Metricas.module.css";

/**
 * As metricas calculadas, nas quatro categorias do backend. Nada e
 * calculado aqui - ate a largura das barras sai de numeros ja prontos.
 * Travessao significa "sem leitura para dizer", nunca zero.
 */

const CAMPOS = {
  ect: "Água",
  rpm: "Giro",
  tps: "Borboleta",
  vanos: "VANOS",
  vbat: "Bateria",
  iat: "Ar admitido",
  vss: "Velocidade",
};

function num(valor, unidade = "", casas = null) {
  if (valor === null || valor === undefined) return "—";
  const texto =
    casas === null ? milhar(valor) : Number(valor).toFixed(casas).replace(".", ",");
  return unidade ? `${texto} ${unidade}` : texto;
}

function segundos(valor) {
  if (valor === null || valor === undefined) return "—";
  return duracao(valor);
}

function Linha({ rotulo, valor, nota }) {
  const vazio = valor === "—";
  return (
    <div className={s.linha}>
      <span className={s.rotulo}>
        {rotulo}
        {nota && <span className={s.nota}>{nota}</span>}
      </span>
      <span className={`${s.valor} ${c.mono} ${vazio ? s.valorVazio : ""}`.trim()}>
        {valor}
      </span>
    </div>
  );
}

function Grupo({ titulo, children }) {
  return (
    <section className={`${c.card} ${s.grupo}`}>
      <h2 className={s.titulo}>{titulo}</h2>
      {children}
    </section>
  );
}

/** Barra proporcional ao maior valor da lista. So leitura, sem eixo. */
function Barras({ itens }) {
  const maior = Math.max(...itens.map((i) => i.valor), 0);
  if (maior <= 0) return <p className={s.vazioNota}>Sem tempo medido nestas faixas.</p>;
  return (
    <div className={s.barras}>
      {itens.map((i) => (
        <div key={i.rotulo} className={s.barraLinha}>
          <span className={s.barraRotulo}>{i.rotulo}</span>
          <span className={s.barraTrilho}>
            <span className={s.barraCheia} style={{ width: `${(i.valor / maior) * 100}%` }} />
          </span>
          <span className={`${s.barraValor} ${c.mono}`}>{i.texto}</span>
        </div>
      ))}
    </div>
  );
}

export function Metricas({ metricas }) {
  if (!metricas) return null;
  const { desempenho = {}, motor = {}, saude = {}, qualidade = {}, cobertura = {} } = metricas;

  const descartado = cobertura.tempo_descartado_s;
  // Os limites que o backend usou nestas contas. Sao os da sessao, e
  // variam por carro, entao os rotulos citam o numero em vez de fixar
  // um valor no texto.
  const lim = metricas.limites || {};

  return (
    <div className={s.grade}>
      <Grupo titulo="Desempenho">
        <Linha rotulo="Distância percorrida" valor={num(desempenho.distancia_km, "km", 2)} />
        <Linha
          rotulo="0 a 100 km/h"
          valor={num(desempenho.zero_a_100_s, "s", 1)}
          nota={desempenho.zero_a_100_s === null ? "não ocorreu nesta sessão" : null}
        />
        <Linha
          rotulo="Aceleração máxima"
          valor={num(desempenho.aceleracao_maxima_ms2, "m/s²", 2)}
        />
        <Linha
          rotulo="Aceleração média"
          valor={num(desempenho.aceleracao_media_ms2, "m/s²", 2)}
          nota="só os trechos acelerando"
        />
        <Linha
          rotulo="Retomada de 80 a 120 km/h"
          valor={num(desempenho.retomada_80_120_s, "s", 1)}
          nota={
            desempenho.retomada_80_120_s === null ? "não ocorreu nesta sessão" : null
          }
        />
        <Linha
          rotulo="Velocidade média em movimento"
          valor={num(desempenho.velocidade_media_movimento, "km/h", 1)}
        />
        <Linha
          rotulo="Velocidade média total"
          valor={num(desempenho.velocidade_media_total, "km/h", 1)}
          nota="inclui o tempo parado com o motor ligado"
        />
        <Linha rotulo="Tempo em movimento" valor={segundos(desempenho.tempo_movimento_s)} />
      </Grupo>

      <Grupo titulo="Uso do motor">
        <Barras
          itens={(motor.tempo_por_faixa_rpm || []).map((f) => ({
            rotulo: f.ate === null ? `${milhar(f.de)}+` : `${milhar(f.de)}–${milhar(f.ate)}`,
            valor: f.segundos,
            texto: duracao(f.segundos),
          }))}
        />
        <Linha rotulo="Tempo com o motor ligado" valor={segundos(motor.tempo_motor_ligado_s)} />
        <Linha
          rotulo="Tempo em marcha lenta"
          valor={segundos(motor.tempo_marcha_lenta_s)}
          nota={lim.rpm_marcha_lenta ? `abaixo de ${milhar(lim.rpm_marcha_lenta)} rpm, parado` : null}
        />
        <Linha rotulo="Tempo com borboleta acima de 90%" valor={segundos(motor.tempo_tps_acima_90_s)} />
        <Linha
          rotulo="Borboleta média em movimento"
          valor={num(motor.tps_medio_movimento, "%", 1)}
        />
        <Linha
          rotulo="Tempo acima do shift light"
          valor={segundos(motor.tempo_acima_shift_light_s)}
          nota={lim.shift_light_rpm ? `acima de ${milhar(lim.shift_light_rpm)} rpm` : null}
        />
        <Linha
          rotulo="Tempo acima do giro alto"
          valor={segundos(motor.tempo_acima_rpm_alto_s)}
          nota={lim.rpm_alto ? `acima de ${milhar(lim.rpm_alto)} rpm` : null}
        />
        <Linha
          rotulo="Giro alto com o motor frio"
          valor={segundos(motor.tempo_giro_alto_motor_frio_s)}
          nota={
            lim.ect_operacao_c
              ? `acima de 3.000 rpm com a água abaixo de ${lim.ect_operacao_c} °C`
              : null
          }
        />
      </Grupo>

      <Grupo titulo="Saúde">
        <Linha
          rotulo={`Tempo até a água atingir ${saude.ect_alvo_c ?? "—"} °C`}
          valor={segundos(saude.aquecimento_s)}
          nota={
            saude.ja_estava_quente
              ? "o motor já subiu quente"
              : saude.aquecimento_s === null && saude.ect_inicial !== null
                ? `não chegou a ${saude.ect_alvo_c} °C nesta sessão`
                : null
          }
        />
        <Linha rotulo="Temperatura de estabilização" valor={num(saude.ect_estabilizada, "°C", 1)} />
        <Linha
          rotulo="Desvio depois de aquecida"
          valor={num(saude.ect_desvio, "°C", 2)}
          nota="quanto a água oscilou"
        />
        <Linha
          rotulo="Tempo com temperatura alta"
          valor={segundos(saude.tempo_temp_alta_s)}
          nota={lim.temp_alta_c ? `água em ${lim.temp_alta_c} °C ou mais` : null}
        />
        <Linha rotulo="Tensão média com o motor rodando" valor={num(saude.vbat_media_rodando, "V", 2)} />
        <Linha
          rotulo="Tensão em marcha lenta"
          valor={num(saude.vbat_marcha_lenta, "V", 2)}
          nota={saude.vbat_marcha_lenta === null ? "a sessão não teve marcha lenta" : null}
        />
        <Linha
          rotulo="Tempo com tensão baixa rodando"
          valor={segundos(saude.tempo_vbat_baixa_rodando_s)}
          nota={lim.vbat_baixa ? `${String(lim.vbat_baixa).replace(".", ",")} V ou menos` : null}
        />
        <Linha
          rotulo="Queda de tensão sob carga"
          valor={num(saude.queda_sob_carga_v, "V", 2)}
          nota={
            saude.queda_sob_carga_v === null
              ? "faltou pedal solto ou pedal fundo"
              : `${num(saude.vbat_sem_carga, "V", 2)} → ${num(saude.vbat_com_carga, "V", 2)}`
          }
        />

        <Linha rotulo="Temperatura média do ar admitido" valor={num(saude.iat_media, "°C", 1)} />
        <Linha rotulo="Temperatura máxima do ar admitido" valor={num(saude.iat_max, "°C")} />
        <Linha
          rotulo="Elevação do ar admitido"
          valor={num(saude.iat_elevacao, "°C")}
          nota="máxima menos a primeira leitura"
        />

        <h3 className={s.subtitulo}>
          Atuação do VANOS
          <span className={s.nota}>por faixa de giro</span>
        </h3>
        <table className={s.tabelinha}>
          <thead>
            <tr>
              <th>Faixa</th>
              <th>Mín.</th>
              <th>Máx.</th>
              <th>Média</th>
            </tr>
          </thead>
          <tbody>
            {(saude.vanos_por_faixa_rpm || []).map((f) => (
              <tr key={f.faixa}>
                <td className={c.mono}>
                  {f.ate === null ? `${milhar(f.de)}+` : `${milhar(f.de)}–${milhar(f.ate)}`}
                </td>
                <td className={c.mono}>{num(f.minimo, "", 1)}</td>
                <td className={c.mono}>{num(f.maximo, "", 1)}</td>
                <td className={c.mono}>{num(f.media, "", 1)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Grupo>

      <Grupo titulo="Qualidade da captura">
        <Linha
          rotulo="Taxa efetiva de amostragem"
          valor={num(qualidade.taxa_hz, "Hz", 2)}
          nota="nominal 1 Hz"
        />
        <Linha rotulo="Amostras gravadas" valor={num(qualidade.amostras)} />
        {descartado > 0 && (
          <Linha
            rotulo="Tempo fora das contas"
            valor={segundos(descartado)}
            nota="buracos longos demais para atribuir"
          />
        )}

        <h3 className={s.subtitulo}>
          Integridade por campo
          <span className={s.nota}>amostras em que a central respondeu</span>
        </h3>
        <Barras
          itens={(qualidade.integridade_por_campo || []).map((f) => ({
            rotulo: CAMPOS[f.campo] || f.campo,
            valor: f.pct ?? 0,
            texto: num(f.pct, "%", 1),
          }))}
        />
      </Grupo>
    </div>
  );
}
