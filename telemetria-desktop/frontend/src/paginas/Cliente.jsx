/*
  Tela de um cliente: os dados dele e os carros que sao dele.

  E daqui que se arquiva e desarquiva o cliente; editar leva ao
  ClienteFormulario (/clientes/:id/editar). Arquivar mora aqui, e nao na
  lista, porque o 409 ("tem 2 carros ativos") precisa dos carros a vista
  para a pessoa decidir o que fazer com eles.

  Os carros vem do `GET /api/veiculos?cliente_id=`, a mesma consulta da
  tela de Veiculos: ativos por padrao, e os arquivados quando pedidos -
  pela URL, para voltar e recarregar reproduzirem a mesma lista.

  Sem node no Figma.
*/
import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { RotateCcw } from "lucide-react";
import { api } from "../api.js";
import { haQuantoTempo, placa } from "../formato.js";
import { Aviso } from "../componentes/ui/Aviso.jsx";
import { Chip } from "../componentes/ui/Chip.jsx";
import { FiltroPopover } from "../componentes/ui/FiltroPopover.jsx";
import { Migalha } from "../componentes/ui/Migalha.jsx";
import { Seta } from "../componentes/ui/Seta.jsx";
import { useFiltrosUrl } from "../componentes/ui/useFiltrosUrl.js";
import c from "../estilos/comum.module.css";
import s from "./Cliente.module.css";

const PADROES = { carros: "ativos" };

// O mesmo controle da lista de Clientes, para o mesmo tipo de recorte.
// "Todos" e nao "Arquivados": aqui os dois lados se misturam, e o chip da
// linha marca qual e qual.
const SITUACOES = [
  { valor: "ativos", rotulo: "Ativos" },
  { valor: "todos", rotulo: "Todos" },
];

/** Os dados de um cliente e a lista dos carros dele. */
export function Cliente() {
  const { id } = useParams();
  const navegar = useNavigate();
  const { filtro, aplicar } = useFiltrosUrl(PADROES);
  const comArquivados = filtro.carros === "todos";

  const [cliente, setCliente] = useState(null);
  const [veiculos, setVeiculos] = useState(null);
  // Erro de carregar troca a pagina pelo aviso; erro de acao (o 409 de
  // arquivar) aparece em cima da ficha, que continua a vista.
  const [erro, setErro] = useState("");
  const [erroAcao, setErroAcao] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const [confirmando, setConfirmando] = useState(false);

  const carregarCliente = useCallback(() => {
    api
      .lerCliente(id)
      .then(setCliente)
      .catch((e) => setErro(String(e.message || e)));
  }, [id]);

  const carregarVeiculos = useCallback(() => {
    api
      .listarVeiculos({
        cliente_id: id,
        incluir_arquivados: comArquivados,
        ordenar_por: "placa",
        direcao: "asc",
      })
      .then(setVeiculos)
      .catch((e) => setErro(String(e.message || e)));
  }, [id, comArquivados]);

  useEffect(carregarCliente, [carregarCliente]);
  useEffect(carregarVeiculos, [carregarVeiculos]);

  async function acao(fazer) {
    setErroAcao("");
    setOcupado(true);
    try {
      await fazer();
      carregarCliente();
      carregarVeiculos();
    } catch (falha) {
      setErroAcao(String(falha.message || falha));
    } finally {
      setOcupado(false);
      setConfirmando(false);
    }
  }

  if (erro) return <Aviso>{erro}</Aviso>;
  if (!cliente) return <p className={c.paginaVazia}>Carregando…</p>;

  const arquivado = Boolean(cliente.arquivado_em);
  const ativos = cliente.veiculos;

  return (
    <>
      <Migalha para="/clientes">Clientes</Migalha>

      <header className={c.paginaTopo}>
        <div>
          <div className={c.placaLinha}>
            <h1 className={c.paginaTitulo}>{cliente.nome}</h1>
            {arquivado && <Chip>arquivado</Chip>}
          </div>
          <p className={c.paginaSubtitulo}>
            {[
              cliente.contato || "sem contato",
              ativos === 1 ? "1 carro ativo" : `${ativos} carros ativos`,
            ].join(" · ")}
          </p>
        </div>
        <div className={c.acoes}>
          <button className={c.botao} onClick={() => navegar(`/clientes/${id}/editar`)}>
            Editar
          </button>
          {arquivado ? (
            <button
              className={`${c.botao} ${c.botaoPrimario}`}
              onClick={() => acao(() => api.restaurarCliente(id))}
              disabled={ocupado}
            >
              <RotateCcw className={c.botaoIcone} size={20} aria-hidden="true" />
              Desarquivar cliente
            </button>
          ) : (
            !confirmando && (
              <button
                className={`${c.botao} ${c.botaoRisco}`}
                onClick={() => {
                  setErroAcao("");
                  setConfirmando(true);
                }}
                disabled={ocupado}
              >
                Arquivar cliente
              </button>
            )
          )}
        </div>
      </header>

      {erroAcao && <Aviso>{erroAcao}</Aviso>}

      {confirmando && (
        <div className={s.confirmacao}>
          <p className={s.pergunta}>Arquivar {cliente.nome}?</p>
          <p className={s.detalhe}>
            O cliente sai da lista e do cadastro de veículos, mas nada é
            apagado: os carros arquivados continuam ligados a ele, com as
            sessões intactas. Só dá para arquivar cliente sem carro ativo, e
            dá para desarquivar depois por esta tela.
          </p>
          <div className={s.botoes}>
            <button
              className={`${c.botao} ${c.botaoRisco}`}
              type="button"
              onClick={() => acao(() => api.arquivarCliente(id))}
              disabled={ocupado}
            >
              Arquivar mesmo assim
            </button>
            <button
              className={c.botao}
              type="button"
              onClick={() => setConfirmando(false)}
              disabled={ocupado}
            >
              Cancelar
            </button>
          </div>
        </div>
      )}

      <div className={s.secaoTopo}>
        <h2 className={s.secaoTitulo}>Veículos</h2>
        <FiltroPopover
          rotulo="Situação"
          rotuloAcima={false}
          exclusivo
          opcoes={SITUACOES}
          valor={filtro.carros}
          padrao={PADROES.carros}
          onChange={(valor) => aplicar({ carros: valor }, { substituir: true })}
        />
      </div>

      {veiculos === null ? (
        <p className={c.paginaVazia}>Carregando…</p>
      ) : veiculos.length === 0 ? (
        <p className={c.paginaVazia}>
          {comArquivados
            ? "Este cliente não tem veículo, nem arquivado."
            : "Nenhum veículo ativo deste cliente."}
        </p>
      ) : (
        <table className={`${c.tabela} ${c.tabelaAposSecao}`}>
          <thead>
            <tr>
              <th>Placa</th>
              <th>Modelo</th>
              <th>Última sessão</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {veiculos.map((v) => (
              <tr
                key={v.id}
                onClick={() => navegar(`/veiculos/${v.id}`)}
                tabIndex={0}
                onKeyDown={(e) => e.key === "Enter" && navegar(`/veiculos/${v.id}`)}
              >
                <td>
                  <span className={c.placaLinha}>
                    <span className={c.mono}>{placa(v.placa) || "—"}</span>
                    {v.arquivado_em && <Chip>arquivado</Chip>}
                  </span>
                </td>
                <td>
                  <span className={c.celulaForte}>
                    {v.marca} {v.modelo}
                  </span>
                  <span className={c.celulaFraca}>
                    {[v.ano, v.motor].filter(Boolean).join(" · ")}
                  </span>
                </td>
                <td className={v.ultima_sessao ? c.celulaApagada : c.celulaNula}>
                  {haQuantoTempo(v.ultima_sessao) || "nenhuma ainda"}
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
