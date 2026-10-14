/*
  Formulario de cadastro e edicao de cliente - a mesma tela para os dois,
  como o VeiculoFormulario. O id na URL decide qual.

  So nome e contato: e tudo o que o cliente tem. Arquivar nao mora aqui,
  e sim na tela do cliente, que mostra os carros que o impediriam.

  Mexe aqui quem acrescentar campo ao cliente, junto com ClienteEntrada
  no backend. Sem node no Figma.
*/
import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api.js";
import { Aviso } from "../componentes/ui/Aviso.jsx";
import { Migalha } from "../componentes/ui/Migalha.jsx";
import { FalhaDeCarga } from "../componentes/ui/FalhaDeCarga.jsx";
import { useCarga } from "../componentes/ui/useCarga.js";
import c from "../estilos/comum.module.css";

/** Cadastro e edicao de cliente - a mesma tela, com ou sem id na URL. */
export function ClienteFormulario() {
  const { id } = useParams();
  const navegar = useNavigate();
  const editando = Boolean(id);

  const [nome, setNome] = useState("");
  const [contato, setContato] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const [erro, setErro] = useState("");
  // Erro por campo do 422 ({nome, contato}), escrito embaixo de cada um.
  const [errosCampo, setErrosCampo] = useState({});

  // Editando, o cliente vem pela URL: id invalido ou 404 nao abre um
  // formulario vazio (salvar daria outro 404), mostra a falha.
  const carga = useCarga(id, api.lerCliente, {
    ativo: editando,
    aoCarregar: (cliente) => {
      setNome(cliente.nome);
      // Contato vazio chega null; o <input> controlado quer "".
      setContato(cliente.contato ?? "");
    },
  });

  const voltar = editando ? `/clientes/${id}` : "/clientes";

  async function salvar(e) {
    e.preventDefault();
    setErro("");
    setErrosCampo({});
    setOcupado(true);
    try {
      const salvo = editando
        ? await api.editarCliente(id, { nome, contato })
        : await api.criarCliente({ nome, contato });
      navegar(`/clientes/${salvo.id}`, { replace: true });
    } catch (falha) {
      const campos = falha.campos || {};
      setErrosCampo(campos);
      // Sem campo conhecido, a frase vai para o Aviso.
      if (!campos.nome && !campos.contato) setErro(String(falha.message || falha));
    } finally {
      setOcupado(false);
    }
  }

  if (carga.falha) return <FalhaDeCarga recurso="cliente" falha={carga.falha} aoTentar={carga.tentarDeNovo} />;
  if (carga.carregando) return <p className={c.paginaVazia}>Carregando…</p>;

  return (
    <>
      <Migalha para={voltar}>{editando ? "Cliente" : "Clientes"}</Migalha>

      <header className={c.paginaTopo}>
        <h1 className={c.paginaTitulo}>{editando ? "Editar cliente" : "Novo cliente"}</h1>
      </header>

      <form className={c.formulario} onSubmit={salvar}>
        <label className={`${c.campo} ${c.formularioLargo}`}>
          <span className={c.campoRotulo}>Nome</span>
          <input
            className={`${c.entrada} ${errosCampo.nome ? c.entradaInvalida : ""}`.trim()}
            value={nome}
            onChange={(e) => setNome(e.target.value)}
            placeholder="Nome do cliente"
            required
            autoFocus
          />
          {errosCampo.nome && <span className={c.campoErro}>{errosCampo.nome}</span>}
        </label>
        <label className={`${c.campo} ${c.formularioLargo}`}>
          <span className={c.campoRotulo}>Contato</span>
          <input
            className={`${c.entrada} ${errosCampo.contato ? c.entradaInvalida : ""}`.trim()}
            value={contato}
            onChange={(e) => setContato(e.target.value)}
            placeholder="Telefone ou e-mail"
          />
          {errosCampo.contato && <span className={c.campoErro}>{errosCampo.contato}</span>}
        </label>

        {erro && <Aviso className={c.formularioLargo}>{erro}</Aviso>}

        <div className={`${c.formularioAcoes} ${c.formularioLargo}`}>
          <button
            className={`${c.botao} ${c.botaoPrimario}`}
            type="submit"
            disabled={ocupado || !nome.trim()}
          >
            {editando ? "Salvar alterações" : "Cadastrar cliente"}
          </button>
          <button className={c.botao} type="button" onClick={() => navegar(voltar)}>
            Cancelar
          </button>
        </div>
      </form>
    </>
  );
}
