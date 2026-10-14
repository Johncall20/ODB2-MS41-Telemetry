/*
  Formulario de cadastro e edicao de veiculo - a mesma tela para os dois.

  Mexe aqui quem acrescentar campo ao cadastro, junto com VeiculoEntrada
  no backend.
*/
import { useEffect, useMemo, useState } from "react";
import { useAutenticacao } from "../hooks/useAutenticacao.js";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api.js";
import {
  MEUS_CARROS,
  ROTULO_CAMBIO,
  ROTULO_COMBUSTIVEL,
  ROTULO_PERFIL_ECU,
  dataHora,
  formatarPlaca,
  mascaraPlaca,
} from "../formato.js";
import { Aviso } from "../componentes/ui/Aviso.jsx";
import { Combobox, chave } from "../componentes/ui/Combobox.jsx";
import { CampoKm } from "../componentes/ui/CampoKm.jsx";
import { Migalha } from "../componentes/ui/Migalha.jsx";
import { FalhaDeCarga } from "../componentes/ui/FalhaDeCarga.jsx";
import { useCarga } from "../componentes/ui/useCarga.js";
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

/*
  As opcoes dos dois selects de ano. A REGRA e do backend (422 por
  campo); isto so deixa de oferecer o que ele recusaria. O ano do modelo
  e a faixa do modelo escolhido (`ano_min`/`ano_max` da FIPE), ou do ano
  que vem ate 1950 quando a faixa e desconhecida (catalogo parcial,
  customizado, marca Outra); a fabricacao e o ano do modelo ou o
  anterior, sem passar do ano corrente nem do piso.
*/
const ANO_MINIMO = 1950;
const ANO_ATUAL = new Date().getFullYear();

/** A faixa de anos de modelo aceita: a da FIPE, ou a de sempre. */
function faixaDoModelo(modelo) {
  if (modelo?.ano_min == null || modelo?.ano_max == null) {
    return { de: ANO_MINIMO, ate: ANO_ATUAL + 1, conhecida: false };
  }
  return {
    de: Math.max(modelo.ano_min, ANO_MINIMO),
    ate: Math.min(modelo.ano_max, ANO_ATUAL + 1),
    conhecida: true,
  };
}

/** Do mais novo ao mais velho. `extra` e o ano que o carro ja tinha, fora
 * da faixa: o backend o aceita sem mudanca, entao o select o mostra. */
function anosModelo({ de, ate }, extra) {
  const anos = Array.from({ length: Math.max(ate - de + 1, 0) }, (_, i) => ate - i);
  if (extra && !anos.includes(extra)) anos.push(extra);
  return anos.sort((a, b) => b - a);
}

function anosFabricacao(modelo) {
  if (!modelo) return [];
  return [modelo, modelo - 1].filter((ano) => ano <= ANO_ATUAL && ano >= ANO_MINIMO);
}

// Os campos que tem lugar para escrever o proprio erro.
const CAMPOS_NA_TELA = new Set([
  "placa",
  "nome_outra",
  "modelo_id",
  "ano_modelo",
  "ano_fabricacao",
  "motor",
  "combustivel",
  "cambio",
  "perfil_ecu",
  "quilometragem",
]);

// Os campos que o formulario manda. Vazio ("") nao vai: o backend
// responde "preencha este campo" para o que faltar, em vez de reclamar do
// tipo de um texto vazio.
const ENVIADOS = [
  "placa",
  "modelo_id",
  "ano_modelo",
  "ano_fabricacao",
  "motor",
  "combustivel",
  "cambio",
  "perfil_ecu",
  "quilometragem",
];

const VAZIO = {
  placa: "",
  marca_id: "",
  modelo_id: "",
  ano_modelo: "",
  ano_fabricacao: "",
  cliente_id: "",
  motor: "",
  combustivel: "",
  cambio: "",
  perfil_ecu: "",
  // Nulo = nao informada; zero e zero km. O campo vazio manda null.
  quilometragem: null,
};

// O "Nao encontrei meu modelo" do fim da lista de modelos.
const NAO_ENCONTREI = "Não encontrei meu modelo";

// Quantas sugestoes do catalogo o "Você quis dizer?" mostra.
const SUGESTOES = 5;

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
  const [ocupado, setOcupado] = useState(false);
  const [erro, setErro] = useState("");
  // Erro por campo do 422 ({campo: frase}), escrito embaixo de cada um.
  const [errosCampo, setErrosCampo] = useState({});

  // O catalogo: todas as marcas, e os modelos da marca escolhida (catalogo
  // mais os customizados desta conta - quem recorta e o backend).
  const [marcas, setMarcas] = useState([]);
  const [modelos, setModelos] = useState([]);
  // O nome sendo digitado no "Nao encontrei meu modelo"; null = fechado.
  const [novoModelo, setNovoModelo] = useState(null);
  // O "Marca e modelo" da marca Outra (ex.: "Puma GTE"): vira um modelo
  // customizado da Outra ao salvar.
  const [nomeOutra, setNomeOutra] = useState("");
  // O par modelo + ano com que o carro abriu na edicao. O backend o aceita
  // mesmo fora da faixa (a faixa pode ter chegado depois do cadastro).
  const [original, setOriginal] = useState(null);

  // A "Outra" e marcada pela API (`outra: true`), nunca reconhecida pelo
  // nome. Ela sai da lista alfabetica e fica fixa no fim do combobox.
  const marcaOutra = useMemo(() => marcas.find((m) => m.outra) || null, [marcas]);
  const marcasDaLista = useMemo(() => marcas.filter((m) => !m.outra), [marcas]);
  // Memorizada: um array novo a cada render faria o combobox recalcular a
  // chave de busca dos ~600 modelos a cada tecla em qualquer campo.
  const opcoesModelo = useMemo(
    () => modelos.map((m) => ({ ...m, marcador: m.customizado ? "seu" : "" })),
    [modelos]
  );
  const naOutra = Boolean(marcaOutra) && campos.marca_id === marcaOutra.id;

  // O ano do modelo depende do modelo: desabilitado ate escolher um (ou a
  // Outra, que nao tem lista), e com so a faixa dele.
  const modeloEscolhido = modelos.find((m) => m.id === campos.modelo_id) || null;
  const faixa = faixaDoModelo(modeloEscolhido);
  const anoModeloLiberado = naOutra || Boolean(campos.modelo_id);
  const anoDoOriginal =
    original && original.modelo_id === campos.modelo_id ? original.ano_modelo : null;

  // "Você quis dizer?": modelos DO CATALOGO cujo nome contem o que se
  // digitou para criar - escolher um deles evita um customizado repetido.
  const termoNovo = chave((novoModelo || "").trim());
  const sugestoes =
    termoNovo.length >= 2
      ? modelos
          .filter((m) => !m.customizado && chave(m.nome).includes(termoNovo))
          .slice(0, SUGESTOES)
      : [];

  useEffect(() => {
    if (!escolheCliente) return;
    api
      .listarClientes()
      .then(setClientes)
      .catch((falha) => {
        setClientes([]);
        setErro(`Não foi possível carregar os clientes: ${falha.message}`);
      });
  }, [escolheCliente]);

  useEffect(() => {
    api
      .listarMarcas()
      .then(setMarcas)
      .catch((falha) => {
        setMarcas([]);
        setErro(`Não foi possível carregar as marcas: ${falha.message}`);
      });
  }, []);

  useEffect(() => {
    if (!campos.marca_id) {
      setModelos([]);
      return;
    }
    api
      .listarModelos(campos.marca_id)
      .then(setModelos)
      .catch((falha) => {
        setModelos([]);
        setErro(`Não foi possível carregar os modelos: ${falha.message}`);
      });
  }, [campos.marca_id]);

  // Editando, o carro vem pela URL: id invalido ou 404 nao abre um
  // formulario vazio (salvar daria outro 404), mostra a falha.
  const carga = useCarga(id, api.lerVeiculo, {
    ativo: editando,
    aoCarregar: ({ veiculo, cliente, total_sessoes }) => {
      const { id: _ignora, criado_em: _tambem, arquivado_em: _fora, ...resto } = veiculo;
      // O carro da propria conta aparece como "Meus carros", nao pelo id.
      const dono = cliente?.implicito ? MEUS : resto.cliente_id ?? "";
      // Opcional sem valor chega null; o <input> controlado quer "".
      // Carro de antes dos enums tem os tres nulos ("Nao informado"):
      // o select abre vazio, e salvar pede que se escolha.
      setCampos({
        ...VAZIO,
        ...resto,
        placa: resto.placa ?? "",
        motor: resto.motor ?? "",
        combustivel: resto.combustivel ?? "",
        cambio: resto.cambio ?? "",
        perfil_ecu: resto.perfil_ecu ?? "",
        cliente_id: dono,
      });
      // Carro da marca Outra: o campo "Marca e modelo" abre com o nome
      // que ele ja tem. Nos outros, o valor fica guardado sem uso.
      setNomeOutra(veiculo.modelo || "");
      setOriginal({ modelo_id: veiculo.modelo_id, ano_modelo: veiculo.ano_modelo });
      setClienteArquivado(cliente && cliente.arquivado_em ? cliente : null);
      setSessoesGravadas(total_sessoes);
    },
  });

  function mudar(campo) {
    return (e) => {
      const valor = e.target.type === "number" ? Number(e.target.value) : e.target.value;
      setCampos((atual) => ({ ...atual, [campo]: valor }));
    };
  }

  // Trocar a marca limpa o modelo: o modelo e de uma marca so.
  function escolherMarca(marca) {
    setNovoModelo(null);
    if (marca.id !== campos.marca_id) setNomeOutra("");
    setCampos((atual) =>
      atual.marca_id === marca.id ? atual : { ...atual, marca_id: marca.id, modelo_id: "" }
    );
  }

  /*
    Trocar o modelo limpa os dois anos se o do modelo cair fora da faixa
    nova - menos quando e o par que o carro ja tinha.
  */
  function escolherModelo(modelo) {
    setNovoModelo(null);
    const { de, ate } = faixaDoModelo(modelo);
    setCampos((atual) => {
      const ano = atual.ano_modelo;
      const doOriginal =
        original && original.modelo_id === modelo.id && original.ano_modelo === ano;
      const cabe = !ano || doOriginal || (ano >= de && ano <= ate);
      return cabe
        ? { ...atual, modelo_id: modelo.id }
        : { ...atual, modelo_id: modelo.id, ano_modelo: "", ano_fabricacao: "" };
    });
  }

  /*
    Cria o modelo customizado e ja o escolhe. Se o nome ja existe - no
    catalogo ou nos da conta -, o backend devolve o existente em vez de
    duplicar, e e esse que fica escolhido.
  */
  async function criarModelo() {
    setErrosCampo((atual) => ({ ...atual, modelo_id: undefined }));
    try {
      const modelo = await api.criarModelo(campos.marca_id, novoModelo);
      setModelos((atual) =>
        atual.some((m) => m.id === modelo.id) ? atual : [...atual, modelo]
      );
      escolherModelo(modelo);
    } catch (falha) {
      setErrosCampo((atual) => ({
        ...atual,
        modelo_id: falha.campos?.nome || String(falha.message || falha),
      }));
    }
  }

  function mudarPlaca(e) {
    const placa = mascaraPlaca(e.target.value);
    setCampos((atual) => ({ ...atual, placa }));
  }

  /*
    Trocar o modelo refaz as opcoes da fabricacao: a escolhida continua se
    ainda couber, e quando sobra uma so ela ja vem marcada.
  */
  function mudarAnoModelo(e) {
    const modelo = e.target.value ? Number(e.target.value) : "";
    setCampos((atual) => {
      const opcoes = anosFabricacao(modelo);
      let fabricacao = opcoes.includes(atual.ano_fabricacao) ? atual.ano_fabricacao : "";
      if (opcoes.length === 1) fabricacao = opcoes[0];
      return { ...atual, ano_modelo: modelo, ano_fabricacao: fabricacao };
    });
  }

  function mudarAnoFabricacao(e) {
    const fabricacao = e.target.value ? Number(e.target.value) : "";
    setCampos((atual) => ({ ...atual, ano_fabricacao: fabricacao }));
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
    setErrosCampo({});
    setPlacaArquivada(null);
    setOcupado(true);
    try {
      // `cliente_id` sai do <select> como texto: um id, ou MEUS para o
      // carro da propria conta. O backend recebe um dos dois - numero em
      // `cliente_id` ou `meus_carros: true`, nunca os dois (seria 422).
      // PARTICULAR nao manda nada: o dono e decidido la.
      const meus = escolheCliente && campos.cliente_id === MEUS;
      const preenchidos = Object.fromEntries(
        ENVIADOS.filter((k) => campos[k] !== "").map((k) => [k, campos[k]])
      );
      // Marca Outra: o texto "Marca e modelo" vira (ou acha) o modelo
      // customizado da Outra, e so o id dele vai para o veiculo. Texto
      // vazio volta 422 no `nome`, que cai embaixo do campo.
      if (naOutra) {
        try {
          const modelo = await api.criarModelo(marcaOutra.id, nomeOutra);
          preenchidos.modelo_id = modelo.id;
        } catch (falha) {
          setErrosCampo({ nome_outra: falha.campos?.nome || String(falha.message || falha) });
          return;
        }
      }
      const corpo = {
        ...preenchidos,
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
      } else if (Object.keys(erroSalvar.campos || {}).length) {
        // 422 por campo: a frase vai embaixo de cada campo. Campo que a
        // tela nao mostra cai no Aviso, para o erro nunca sumir calado.
        setErrosCampo(erroSalvar.campos);
        if (Object.keys(erroSalvar.campos).some((k) => !CAMPOS_NA_TELA.has(k))) {
          setErro(String(erroSalvar.message));
        }
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

  if (carga.falha) return <FalhaDeCarga recurso="veiculo" falha={carga.falha} aoTentar={carga.tentarDeNovo} />;
  if (carga.carregando) return <p className={c.paginaVazia}>Carregando…</p>;

  return (
    <>
      <Migalha para={editando ? `/veiculos/${id}` : "/veiculos"}>
        {editando ? "Veículo" : "Veículos"}
      </Migalha>

      <header className={c.paginaTopo}>
        <h1 className={c.paginaTitulo}>{editando ? "Editar veículo" : "Novo veículo"}</h1>
      </header>

      <form className={c.formulario} onSubmit={salvar}>
        <Campo
          rotulo="Placa"
          valor={campos.placa}
          ao={mudarPlaca}
          largo
          dica="ABC1234 ou ABC1D23"
          erro={errosCampo.placa}
        />
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
        <Combobox
          rotulo="Marca"
          opcoes={marcasDaLista}
          valor={campos.marca_id}
          aoEscolher={escolherMarca}
          placeholder="Buscar ou escolher marca"
          contagem={{ singular: "marca", plural: "marcas" }}
          vazio="Nenhuma marca encontrada. Use Outra."
          fixo={marcaOutra}
        />
        <div className={s.modeloBloco}>
          {naOutra ? (
            /* Marca fora da FIPE: nao ha lista de modelos para escolher. O
               texto vira um modelo customizado da Outra ao salvar. */
            <label className={c.campo}>
              <span className={c.campoRotulo}>Marca e modelo</span>
              <input
                className={`${c.entrada} ${errosCampo.nome_outra ? c.entradaInvalida : ""}`.trim()}
                value={nomeOutra}
                onChange={(e) => {
                  setNomeOutra(e.target.value);
                  setErrosCampo((atual) => ({ ...atual, nome_outra: undefined }));
                }}
                placeholder="Puma GTE"
              />
              {errosCampo.nome_outra ? (
                <span className={c.campoErro}>{errosCampo.nome_outra}</span>
              ) : (
                <span className={s.detalheCampo}>
                  Para carro de marca que não está na tabela FIPE.
                </span>
              )}
            </label>
          ) : (
            <Combobox
              rotulo="Modelo"
              opcoes={opcoesModelo}
              valor={campos.modelo_id}
              aoEscolher={escolherModelo}
              desabilitado={!campos.marca_id}
              placeholder={campos.marca_id ? "Buscar ou escolher modelo" : "Escolha a marca antes"}
              erro={novoModelo === null ? errosCampo.modelo_id : undefined}
              contagem={{ singular: "modelo", plural: "modelos" }}
              vazio="Nenhum modelo encontrado."
              rodape={{ rotulo: NAO_ENCONTREI, aoEscolher: (digitado) => setNovoModelo(digitado) }}
            />
          )}
          {novoModelo !== null && !naOutra && (
            <div className={s.novoModelo}>
              <label className={c.campo}>
                <span className={c.campoRotulo}>Nome do modelo</span>
                <input
                  className={`${c.entrada} ${
                    errosCampo.modelo_id ? c.entradaInvalida : ""
                  }`.trim()}
                  value={novoModelo}
                  onChange={(e) => setNovoModelo(e.target.value)}
                  onKeyDown={(e) => {
                    // Enter aqui cria o modelo, nao envia o formulario.
                    if (e.key === "Enter") {
                      e.preventDefault();
                      criarModelo();
                    }
                  }}
                  placeholder="Como o carro é chamado"
                  autoFocus
                />
                {errosCampo.modelo_id && (
                  <span className={c.campoErro}>{errosCampo.modelo_id}</span>
                )}
              </label>
              {sugestoes.length > 0 && (
                <div className={s.sugestoes}>
                  <span className={s.sugestoesTitulo}>Você quis dizer?</span>
                  <ul className={s.sugestoesLista}>
                    {sugestoes.map((m) => (
                      <li key={m.id}>
                        <button
                          className={s.sugestao}
                          type="button"
                          onClick={() => escolherModelo(m)}
                        >
                          {m.nome}
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              <div className={s.novoModeloAcoes}>
                <button className={`${c.botao} ${c.botaoPrimario}`} type="button" onClick={criarModelo}>
                  Criar e usar
                </button>
                <button className={c.botao} type="button" onClick={() => setNovoModelo(null)}>
                  Cancelar
                </button>
              </div>
            </div>
          )}
        </div>
        <label className={c.campo}>
          <span className={c.campoRotulo}>Ano do modelo</span>
          {/* Desabilitado ate escolher o modelo: as opcoes sao a faixa dele. */}
          <select
            className={`${c.selecao} ${errosCampo.ano_modelo ? c.entradaInvalida : ""}`.trim()}
            value={campos.ano_modelo}
            onChange={mudarAnoModelo}
            disabled={!anoModeloLiberado}
            required
          >
            <option value="">{anoModeloLiberado ? "escolha o ano" : "escolha o modelo antes"}</option>
            {anoModeloLiberado &&
              anosModelo(faixa, anoDoOriginal).map((ano) => (
                <option key={ano} value={ano}>
                  {ano}
                </option>
              ))}
          </select>
          {errosCampo.ano_modelo ? (
            <span className={c.campoErro}>{errosCampo.ano_modelo}</span>
          ) : (
            faixa.conhecida &&
            anoModeloLiberado && (
              <span className={s.detalheCampo}>
                De {faixa.de} a {faixa.ate}, os anos deste modelo na tabela FIPE. Se o ano do
                carro não aparece, use “{NAO_ENCONTREI}”.
              </span>
            )
          )}
        </label>
        <label className={c.campo}>
          <span className={c.campoRotulo}>Ano de fabricação</span>
          {/* Desabilitado ate escolher o modelo: as opcoes dependem dele. */}
          <select
            className={`${c.selecao} ${errosCampo.ano_fabricacao ? c.entradaInvalida : ""}`.trim()}
            value={campos.ano_fabricacao}
            onChange={mudarAnoFabricacao}
            disabled={!campos.ano_modelo}
            required
          >
            <option value="">{campos.ano_modelo ? "escolha o ano" : "escolha o modelo antes"}</option>
            {anosFabricacao(campos.ano_modelo).map((ano) => (
              <option key={ano} value={ano}>
                {ano}
              </option>
            ))}
          </select>
          {errosCampo.ano_fabricacao && (
            <span className={c.campoErro}>{errosCampo.ano_fabricacao}</span>
          )}
        </label>
        <Campo
          rotulo="Motor"
          valor={campos.motor}
          ao={mudar("motor")}
          dica="M50B25"
          erro={errosCampo.motor}
        />
        <Selecao
          rotulo="Combustível"
          mapa={ROTULO_COMBUSTIVEL}
          valor={campos.combustivel}
          ao={mudar("combustivel")}
          erro={errosCampo.combustivel}
        />
        <Selecao
          rotulo="Câmbio"
          mapa={ROTULO_CAMBIO}
          valor={campos.cambio}
          ao={mudar("cambio")}
          erro={errosCampo.cambio}
        />
        {/* O protocolo nao e campo: vem do perfil, e o rotulo ja o diz. */}
        <Selecao
          rotulo="ECU"
          mapa={ROTULO_PERFIL_ECU}
          valor={campos.perfil_ecu}
          ao={mudar("perfil_ecu")}
          erro={errosCampo.perfil_ecu}
        />
        {/* Opcional. Uma sessao encerrada com km tambem atualiza este
            valor, quando e a mais recente do carro. */}
        <CampoKm
          rotulo="Quilometragem atual"
          valor={campos.quilometragem}
          aoMudar={(km) => setCampos((atual) => ({ ...atual, quilometragem: km }))}
          erro={errosCampo.quilometragem}
          dica="opcional"
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
            <p className={s.pergunta}>Arquivar {formatarPlaca(campos.placa) || "este veículo"}?</p>
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

/** Select de um dos enums do veiculo, com as opcoes do mapa de rotulos. */
function Selecao({ rotulo, mapa, valor, ao, erro }) {
  return (
    <label className={c.campo}>
      <span className={c.campoRotulo}>{rotulo}</span>
      <select
        className={`${c.selecao} ${erro ? c.entradaInvalida : ""}`.trim()}
        value={valor}
        onChange={ao}
        required
      >
        <option value="">escolha</option>
        {Object.entries(mapa).map(([chave, texto]) => (
          <option key={chave} value={chave}>
            {texto}
          </option>
        ))}
      </select>
      {erro && <span className={c.campoErro}>{erro}</span>}
    </label>
  );
}

function Campo({ rotulo, valor, ao, tipo = "text", largo, obrigatorio, dica, erro }) {
  return (
    <label className={`${c.campo} ${largo ? c.formularioLargo : ""}`.trim()}>
      <span className={c.campoRotulo}>{rotulo}</span>
      <input
        className={`${c.entrada} ${erro ? c.entradaInvalida : ""}`.trim()}
        type={tipo}
        value={valor}
        onChange={ao}
        required={obrigatorio}
        placeholder={dica}
        aria-invalid={erro ? true : undefined}
      />
      {erro && <span className={c.campoErro}>{erro}</span>}
    </label>
  );
}
