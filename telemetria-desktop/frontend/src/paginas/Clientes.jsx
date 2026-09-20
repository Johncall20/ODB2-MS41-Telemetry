/*
  Os clientes da conta: lista e cadastro na mesma tela.

  So a conta PROFISSIONAL chega aqui - a rota e o item da sidebar somem
  para o PARTICULAR, que tem um cliente implicito e nunca precisa ve-lo. A
  API, essa, e a mesma para os dois: o papel muda a interface, nao o
  modelo (ver "Propriedade" no CLAUDE.md).

  Sem node no Figma.
*/
import { useCallback, useEffect, useState } from "react";
import { api } from "../api.js";
import { Aviso } from "../componentes/ui/Aviso.jsx";
import c from "../estilos/comum.module.css";
import s from "./Clientes.module.css";

/** Lista e cadastro dos clientes da conta. */
export function Clientes() {
  const [clientes, setClientes] = useState(null);
  const [nome, setNome] = useState("");
  const [contato, setContato] = useState("");
  const [erro, setErro] = useState("");
  const [ocupado, setOcupado] = useState(false);

  const carregar = useCallback(() => {
    api
      .listarClientes()
      .then(setClientes)
      .catch((e) => setErro(String(e.message || e)));
  }, []);

  useEffect(carregar, [carregar]);

  async function cadastrar(e) {
    e.preventDefault();
    setErro("");
    setOcupado(true);
    try {
      await api.criarCliente({ nome, contato });
      setNome("");
      setContato("");
      carregar();
    } catch (falha) {
      setErro(String(falha.message || falha));
    } finally {
      setOcupado(false);
    }
  }

  if (erro && clientes === null) return <Aviso>{erro}</Aviso>;
  if (clientes === null) return <p className={c.paginaVazia}>Carregando…</p>;

  return (
    <>
      <header className={c.paginaTopo}>
        <div>
          <h1 className={c.paginaTitulo}>Clientes</h1>
          <p className={c.paginaSubtitulo}>
            Quem são os donos dos carros que você atende.
          </p>
        </div>
      </header>

      {erro && <Aviso>{erro}</Aviso>}

      <form className={s.formLinha} onSubmit={cadastrar}>
        <label className={s.formCampo}>
          <span className={c.campoRotulo}>Nome</span>
          <input
            className={c.entrada}
            value={nome}
            onChange={(ev) => setNome(ev.target.value)}
            placeholder="Nome do cliente"
            required
          />
        </label>
        <label className={s.formCampo}>
          <span className={c.campoRotulo}>Contato</span>
          <input
            className={c.entrada}
            value={contato}
            onChange={(ev) => setContato(ev.target.value)}
            placeholder="Telefone ou e-mail"
          />
        </label>
        <button
          className={`${c.botao} ${c.botaoPrimario}`}
          type="submit"
          disabled={ocupado || !nome.trim()}
        >
          Cadastrar
        </button>
      </form>

      {clientes.length === 0 ? (
        <p className={c.paginaVazia}>
          Nenhum cliente cadastrado ainda. Cadastre um acima para poder vincular
          veículos a ele.
        </p>
      ) : (
        <table className={c.tabela}>
          <thead>
            <tr>
              <th>Nome</th>
              <th>Contato</th>
              <th>Veículos</th>
            </tr>
          </thead>
          <tbody>
            {clientes.map((cliente) => (
              <tr key={cliente.id}>
                <td className={c.celulaForte}>{cliente.nome}</td>
                <td className={s.contato}>{cliente.contato || "—"}</td>
                {/*
                  Conta so os carros ativos: o arquivado nao some do banco,
                  mas somar os dois numeros faria a coluna nao bater com a
                  lista de veiculos ao lado.
                */}
                <td className={c.mono}>{cliente.veiculos}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  );
}
