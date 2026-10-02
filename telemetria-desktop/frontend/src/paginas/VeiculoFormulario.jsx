/*
  Formulario de cadastro e edicao de veiculo - a mesma tela para os dois.

  Mexe aqui quem acrescentar campo ao cadastro, junto com VeiculoEntrada
  no backend.
*/
import { useEffect, useState } from "react";
import { useAutenticacao } from "../hooks/useAutenticacao.js";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api.js";
import { MEUS_CARROS, dataHora } from "../formato.js";
import { Aviso } from "../componentes/ui/Aviso.jsx";
import { Migalha } from "../componentes/ui/Migalha.jsx";
import c from "../estilos/comum.module.css";
import s from "./VeiculoFormulario.module.css";

/*
  Cadastro e edicao na mesma tela; o id na URL decide qual. Placa repetida
  volta 409, e a de um carro arquivado oferece restaurar.
*/

/*
  Valor do <select> de dono para o carro da propria conta. Nao e um id:
  o front nao conhece o id do cliente implicito (ele pode nem existir
  ainda), e manda `meus_carros: true` no lugar.
*/
const MEUS = "meus";

const VAZIO = {
  placa: "",
  marca: "",
  modelo: "",
  ano: new Date().getFullYear(),
  cliente_id: "",
  motor: "",
  ecu: "MS41.1",
  protocolo: "DS2",
  quilometragem: 0,
};

/** Cadastro e edicao de veiculo - a mesma tela, com ou sem id na URL. */
export function VeiculoFormulario() {
  const { usuario } = useAutenticacao();
  // Cliente e coisa de PROFISSIONAL. A conta PARTICULAR nao escolhe: o
  // backend poe o carro novo no cliente implicito dela e, na edicao,
  // mantem o dono que o carro ja tinha. A palavra "cliente" nao aparece.
  const escolheCliente = usuario?.papel === "PROFISSIONAL";
  // So os ativos: cliente arquivado nao recebe carro.
  const [clientes, setClientes] = useState([]);
  // O cliente atual do carro quando ele esta arquivado. Entra no seletor
  // so para esta edicao: sem ele o <select> ficaria sem a opcao do valor
  // atual e o `required` travaria o salvar de qualquer outro campo.
  const [clienteArquivado, setClienteArquivado] = useState(null);

  const { id } = useParams();
  const navegar = useNavigate();
  const editando = Boolean(id);

  const [campos, setCampos] = useState(VAZIO);
  const [sessoesGravadas, setSessoesGravadas] = useState(0);
  const [confirmando, setConfirmando] = useState(false);
  // Corpo do 409 de placa arquivada: {veiculo_id, arquivado_em}.
  const [placaArquivada, setPlacaArquivada] = useState(null);
  const [carregando, setCarregando] = useState(editando);
  const [ocupado, setOcupado] = useState(false);
  const [erro, setErro] = useState("");

  useEffect(() => {
    if (!escolheCliente) return;
    api.listarClientes().then(setClientes).catch(() => setClientes([]));
  }, [escolheCliente]);

  useEffect(() => {
    if (!editando) return;
    api
      .lerVeiculo(id)
      .then(({ veiculo, cliente, total_sessoes }) => {
        const { id: _ignora, criado_em: _tambem, arquivado_em: _fora, ...resto } = veiculo;
        // O carro da propria conta aparece como "Meus carros", nao pelo id.
        const dono = cliente?.implicito ? MEUS : resto.cliente_id ?? "";
        setCampos({ ...VAZIO, ...resto, cliente_id: dono });
        setClienteArquivado(cliente && cliente.arquivado_em ? cliente : null);
        setSessoesGravadas(total_sessoes);
        setCarregando(false);
      })
      .catch((e) => {
        setErro(String(e.message || e));
        setCarregando(false);
      });
  }, [id, editando]);

  function mudar(campo) {
    return (e) => {
      const valor = e.target.type === "number" ? Number(e.target.value) : e.target.value;
      setCampos((atual) => ({ ...atual, [campo]: valor }));
    };
  }

  async function restaurarExistente() {
    setErro("");
    setOcupado(true);
    try {
      await api.restaurarVeiculo(placaArquivada.veiculo_id);
      navegar(`/veiculos/${placaArquivada.veiculo_id}`, { replace: true });
    } catch (erroRestaurar) {
      setErro(String(erroRestaurar.message || erroRestaurar));
    } finally {
      setOcupado(false);
    }
  }

  async function salvar(e) {
    e.preventDefault();
    setErro("");
    setPlacaArquivada(null);
    setOcupado(true);
    try {
      // `cliente_id` sai do <select> como texto: um id, ou MEUS para o
      // carro da propria conta. O backend recebe um dos dois - numero em
      // `cliente_id` ou `meus_carros: true`, nunca os dois (seria 422).
      // PARTICULAR nao manda nada: o dono e decidido la.
      const meus = escolheCliente && campos.cliente_id === MEUS;
      const corpo = {
        ...campos,
        cliente_id:
          escolheCliente && campos.cliente_id && !meus ? Number(campos.cliente_id) : null,
        meus_carros: meus,
      };
      const salvo = editando
        ? await api.editarVeiculo(id, corpo)
        : await api.criarVeiculo(corpo);
      navegar(`/veiculos/${salvo.id}`, { replace: true });
    } catch (erroSalvar) {
      // Placa de um veiculo arquivado: em vez de erro, oferece restaurar
      // com o historico em vez de criar um duplicado.
      if (erroSalvar.detalhe?.erro === "placa_arquivada") {
        setPlacaArquivada(erroSalvar.detalhe);
      } else {
        setErro(String(erroSalvar.message || erroSalvar));
      }
    } finally {
      setOcupado(false);
    }
  }

  async function arquivar() {
    setErro("");
    setOcupado(true);
    try {
      await api.arquivarVeiculo(id);
      navegar("/veiculos", { replace: true });
    } catch (erroArquivar) {
      // O backend recusa arquivar carro que esta gravando agora; a frase
      // que ele devolve ja explica o motivo, entao e ela que aparece.
      setConfirmando(false);
      setErro(String(erroArquivar.message || erroArquivar));
    } finally {
      setOcupado(false);
    }
  }

  if (carregando) return <p className={c.paginaVazia}>Carregando…</p>;

  return (
    <>
      <Migalha para={editando ? `/veiculos/${id}` : "/veiculos"}>
        {editando ? "Veículo" : "Veículos"}
      </Migalha>

      <header className={c.paginaTopo}>
        <h1 className={c.paginaTitulo}>{editando ? "Editar veículo" : "Novo veículo"}</h1>
      </header>

      <form className={c.formulario} onSubmit={salvar}>
        <Campo rotulo="Placa" valor={campos.placa} ao={mudar("placa")} largo />
        {escolheCliente && (
          <label className={`${c.campo} ${c.formularioLargo}`}>
            <span className={c.campoRotulo}>Cliente</span>
            <select
              className={c.selecao}
              value={campos.cliente_id ?? ""}
              onChange={mudar("cliente_id")}
              required
            >
              <option value="">escolha o cliente</option>
              {/* Sempre presente: o mecanico tambem tem carro proprio, e
                  sem esta opcao precisaria trocar de papel para cadastra-lo. */}
              <option value={MEUS}>{MEUS_CARROS}</option>
              {clienteArquivado && (
                <option value={clienteArquivado.id}>
                  {clienteArquivado.nome} (arquivado)
                </option>
              )}
              {clientes.map((cl) => (
                <option key={cl.id} value={cl.id}>
                  {cl.nome}
                </option>
              ))}
            </select>
            {clientes.length === 0 && (
              <span className={c.celulaNula}>
                Nenhum cliente ativo — para um carro de cliente, cadastre-o antes em Clientes.
              </span>
            )}
          </label>
        )}
        <Campo rotulo="Marca" valor={campos.marca} ao={mudar("marca")} obrigatorio />
        <Campo rotulo="Modelo" valor={campos.modelo} ao={mudar("modelo")} obrigatorio />
        <Campo rotulo="Ano" tipo="number" valor={campos.ano} ao={mudar("ano")} obrigatorio />
        <Campo rotulo="Motor" valor={campos.motor} ao={mudar("motor")} dica="M50B25" />
        <Campo rotulo="ECU" valor={campos.ecu} ao={mudar("ecu")} />
        <Campo rotulo="Protocolo" valor={campos.protocolo} ao={mudar("protocolo")} />
        <Campo
          rotulo="Quilometragem"
          tipo="number"
          valor={campos.quilometragem}
          ao={mudar("quilometragem")}
        />

        {erro && <Aviso className={c.formularioLargo}>{erro}</Aviso>}

        <div className={`${c.formularioAcoes} ${c.formularioLargo}`}>
          <button className={`${c.botao} ${c.botaoPrimario}`} type="submit" disabled={ocupado}>
            {editando ? "Salvar alterações" : "Cadastrar veículo"}
          </button>
          <button
            className={c.botao}
            type="button"
            onClick={() => navegar(editando ? `/veiculos/${id}` : "/veiculos")}
          >
            Cancelar
          </button>
          {editando && !confirmando && (
            <button
              className={`${c.botao} ${c.botaoRisco} ${c.botaoEmpurrado}`}
              type="button"
              onClick={() => setConfirmando(true)}
              disabled={ocupado}
            >
              Arquivar veículo
            </button>
          )}
        </div>

        {placaArquivada && (
          <div className={`${s.confirmacaoNeutra} ${c.formularioLargo}`}>
            <p className={s.pergunta}>
              Esse veículo foi arquivado em {dataHora(placaArquivada.arquivado_em)}.
              Restaurar com o histórico?
            </p>
            <p className={s.detalhe}>
              As sessões gravadas antes do arquivamento continuam lá. Restaurar
              é melhor que cadastrar de novo: um veículo novo com a mesma placa
              começaria sem histórico nenhum.
            </p>
            <div className={s.botoes}>
              <button
                className={`${c.botao} ${c.botaoPrimario}`}
                type="button"
                onClick={restaurarExistente}
                disabled={ocupado}
              >
                Restaurar veículo
              </button>
              <button
                className={c.botao}
                type="button"
                onClick={() => setPlacaArquivada(null)}
                disabled={ocupado}
              >
                Cancelar
              </button>
            </div>
          </div>
        )}

        {confirmando && (
          <div className={`${s.confirmacao} ${c.formularioLargo}`}>
            <p className={s.pergunta}>Arquivar {campos.placa || "este veículo"}?</p>
            <p className={s.detalhe}>
              O veículo sai das listas, mas nada é apagado:{" "}
              {sessoesGravadas === 1
                ? "a 1 sessão gravada continua"
                : `as ${sessoesGravadas} sessões gravadas continuam`}{" "}
              em Sessões, com as amostras e os eventos intactos. Dá para
              restaurar depois pela tela do veículo.
            </p>
            <div className={s.botoes}>
              <button
                className={`${c.botao} ${c.botaoRisco}`}
                type="button"
                onClick={arquivar}
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
      </form>
    </>
  );
}

function Campo({ rotulo, valor, ao, tipo = "text", largo, obrigatorio, dica }) {
  return (
    <label className={`${c.campo} ${largo ? c.formularioLargo : ""}`.trim()}>
      <span className={c.campoRotulo}>{rotulo}</span>
      <input
        className={c.entrada}
        type={tipo}
        value={valor}
        onChange={ao}
        required={obrigatorio}
        placeholder={dica}
      />
    </label>
  );
}
