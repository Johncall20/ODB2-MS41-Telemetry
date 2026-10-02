/*
  Formulario de cadastro e edicao de cliente - a mesma tela para os dois,
  como o VeiculoFormulario. O id na URL decide qual.

  So nome e contato: e tudo o que o cliente tem. Arquivar nao mora aqui,
  e sim na tela do cliente, que mostra os carros que o impediriam.

  Mexe aqui quem acrescentar campo ao cliente, junto com ClienteEntrada
  no backend. Sem node no Figma.
*/
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api.js";
import { Aviso } from "../componentes/ui/Aviso.jsx";
import { Migalha } from "../componentes/ui/Migalha.jsx";
import c from "../estilos/comum.module.css";

/** Cadastro e edicao de cliente - a mesma tela, com ou sem id na URL. */
export function ClienteFormulario() {
  const { id } = useParams();
  const navegar = useNavigate();
  const editando = Boolean(id);

  const [nome, setNome] = useState("");
  const [contato, setContato] = useState("");
  const [carregando, setCarregando] = useState(editando);
  const [ocupado, setOcupado] = useState(false);
  const [erro, setErro] = useState("");

  useEffect(() => {
    if (!editando) return;
    api
      .lerCliente(id)
      .then((cliente) => {
        setNome(cliente.nome);
        setContato(cliente.contato);
        setCarregando(false);
      })
      .catch((e) => {
        setErro(String(e.message || e));
        setCarregando(false);
      });
  }, [id, editando]);

  const voltar = editando ? `/clientes/${id}` : "/clientes";

  async function salvar(e) {
    e.preventDefault();
    setErro("");
    setOcupado(true);
    try {
      const salvo = editando
        ? await api.editarCliente(id, { nome, contato })
        : await api.criarCliente({ nome, contato });
      navegar(`/clientes/${salvo.id}`, { replace: true });
    } catch (falha) {
      setErro(String(falha.message || falha));
    } finally {
      setOcupado(false);
    }
  }

  if (carregando) return <p className={c.paginaVazia}>Carregando…</p>;

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
            className={c.entrada}
            value={nome}
            onChange={(e) => setNome(e.target.value)}
            placeholder="Nome do cliente"
            required
            autoFocus
          />
        </label>
        <label className={`${c.campo} ${c.formularioLargo}`}>
          <span className={c.campoRotulo}>Contato</span>
          <input
            className={c.entrada}
            value={contato}
            onChange={(e) => setContato(e.target.value)}
            placeholder="Telefone ou e-mail"
          />
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
