/*
  Tela de um veiculo: os dados do carro e o historico de sessoes dele.

  E de onde se comeca a gravar, e onde se arquiva ou restaura o carro.
*/
import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api.js";
import {
  ROTULO_EVENTO,
  dataHora,
  duracao,
  milhar,
  placa,
  quilometragem,
} from "../formato.js";
import { Play, RotateCcw, SlidersHorizontal } from "lucide-react";
import { Aviso } from "../componentes/ui/Aviso.jsx";
import { Chip, Chips } from "../componentes/ui/Chip.jsx";
import { Migalha } from "../componentes/ui/Migalha.jsx";
import { Seta } from "../componentes/ui/Seta.jsx";
import c from "../estilos/comum.module.css";
import s from "./Veiculo.module.css";

/*
  Node 2:295. A ficha do carro em cima e o historico embaixo, na mesma
  tela: quem abre um veiculo quase sempre quer ver o que ele ja gravou.
*/
/** Ficha do carro e o historico de gravacoes dele. */
export function Veiculo() {
  const { id } = useParams();
  const navegar = useNavigate();
  const [dados, setDados] = useState(null);
  const [erro, setErro] = useState("");
  const [ocupado, setOcupado] = useState(false);

  const carregar = useCallback(() => {
    setDados(null);
    api
      .lerVeiculo(id)
      .then(setDados)
      .catch((e) => setErro(String(e.message || e)));
  }, [id]);

  useEffect(carregar, [carregar]);

  async function restaurar() {
    setErro("");
    setOcupado(true);
    try {
      await api.restaurarVeiculo(id);
      carregar();
    } catch (e) {
      setErro(String(e.message || e));
    } finally {
      setOcupado(false);
    }
  }

  if (erro) return <Aviso>{erro}</Aviso>;
  if (!dados) return <p className={c.paginaVazia}>Carregando…</p>;

  const { veiculo, sessoes, total_sessoes } = dados;
  const arquivado = Boolean(veiculo.arquivado_em);
  const legenda = [veiculo.marca && `${veiculo.marca} ${veiculo.modelo}`, veiculo.ano, veiculo.cliente]
    .filter(Boolean)
    .join(" · ");

  return (
    <>
      <Migalha para="/veiculos">
        Veículos
      </Migalha>

      <header className={c.paginaTopoVeiculo}>
        <div>
          <div className={s.placaLinha}>
            <h1 className={`${s.placa} ${c.mono}`}>{placa(veiculo.placa) || "sem placa"}</h1>
            {arquivado && <Chip>arquivado</Chip>}
          </div>
          <p className={c.paginaSubtituloVeiculo}>{legenda}</p>
        </div>
        <div className={c.acoes}>
          <button className={c.botao} onClick={() => navegar(`/veiculos/${id}/editar`)}>
            Editar
          </button>
          {/*
            Limite e por carro, entao a tela dele se alcanca pelo carro -
            nao ha ajuste global em lugar nenhum.
          */}
          <button className={c.botao} onClick={() => navegar(`/veiculos/${id}/limites`)}>
            <SlidersHorizontal className={c.botaoIcone} size={20} aria-hidden="true" />
            Limites de alerta
          </button>
          {/*
            Arquivado nao grava sessao nova - o backend recusa. No lugar do
            botao de gravar entra o de restaurar.
          */}
          {arquivado ? (
            <button
              className={`${c.botao} ${c.botaoPrimario}`}
              onClick={restaurar}
              disabled={ocupado}
            >
              <RotateCcw className={c.botaoIcone} size={20} aria-hidden="true" />
              Restaurar veículo
            </button>
          ) : (
            <button
              className={`${c.botao} ${c.botaoPrimario}`}
              onClick={() => navegar(`/ao-vivo?veiculo=${id}`)}
            >
              <Play className={c.botaoIcone} size={20} aria-hidden="true" />
              Nova sessão
            </button>
          )}
        </div>
      </header>

      <div className={c.cartoes}>
        <Cartao rotulo="Motor" valor={veiculo.motor} mono />
        <Cartao rotulo="ECU" valor={veiculo.ecu} />
        <Cartao rotulo="Protocolo" valor={veiculo.protocolo} />
        <Cartao rotulo="Quilometragem" valor={quilometragem(veiculo.quilometragem)} mono />
        <Cartao rotulo="Sessões" valor={String(total_sessoes)} mono />
      </div>

      <div className={s.secaoTopo}>
        <h2 className={s.secaoTitulo}>Sessões</h2>
        <Link className={s.secaoLink} to="/sessoes">
          Ver todas
        </Link>
      </div>

      {sessoes.length === 0 ? (
        <p className={c.paginaVazia}>Este veículo ainda não tem sessão gravada.</p>
      ) : (
        <table className={`${c.tabela} ${c.tabelaAposSecao} ${s.tabela}`}>
          <thead>
            <tr>
              <th>Data</th>
              <th>Duração</th>
              <th>RPM máx.</th>
              <th>Vel. máx.</th>
              <th>Eventos</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {sessoes.map((sessao) => (
              <tr key={sessao.id} onClick={() => navegar(`/sessoes/${sessao.id}`)} tabIndex={0}
                  onKeyDown={(e) => e.key === "Enter" && navegar(`/sessoes/${sessao.id}`)}>
                <td className={c.mono}>{dataHora(sessao.iniciada_em)}</td>
                <td className={`${c.mono} ${c.celulaApagada}`}>{duracao(sessao.resumo?.duracao_s)}</td>
                {/*
                  Pico nulo quer dizer que nenhuma amostra da sessao trouxe o
                  bit de valid ligado para esse campo. Nao ha numero para
                  mostrar, entao mostra travessao.
                */}
                <td className={c.mono}>{milhar(sessao.resumo?.rpm_pico)}</td>
                <td className={c.mono}>
                  {sessao.resumo?.vss_pico === null || sessao.resumo?.vss_pico === undefined
                    ? "—"
                    : `${sessao.resumo.vss_pico} km/h`}
                </td>
                <td>
                  <Eventos tipos={sessao.eventos_notaveis} />
                </td>
                <td>
                  <Seta />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  );
}

function Cartao({ rotulo, valor, mono }) {
  const vazio = !valor;
  return (
    <div className={c.cartao}>
      <span className={c.cartaoRotulo}>{rotulo}</span>
      <span
        className={`${c.cartaoValor} ${mono ? c.mono : ""} ${vazio ? c.celulaNula : ""}`.trim()}
      >
        {vazio ? "não informado" : valor}
      </span>
    </div>
  );
}

function Eventos({ tipos }) {
  if (!tipos || tipos.length === 0) return <span className={c.celulaApagada}>—</span>;
  const [primeiro, ...resto] = tipos;
  return (
    <Chips>
      <Chip tom="alerta">{ROTULO_EVENTO[primeiro] || primeiro}</Chip>
      {resto.length > 0 && <Chip>+{resto.length}</Chip>}
    </Chips>
  );
}
