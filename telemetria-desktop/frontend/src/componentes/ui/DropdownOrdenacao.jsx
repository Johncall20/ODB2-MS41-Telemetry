import c from "../../estilos/comum.module.css";
import s from "./DropdownOrdenacao.module.css";

/**
 * Ordenacao num controle so: campo e sentido na mesma opcao. As opcoes
 * precisam cobrir os DOIS sentidos de cada campo que o header ordena,
 * senao o segundo clique cai num par sem opcao.
 */
export function DropdownOrdenacao({ opcoes, campo, direcao, onChange, rotulo = "Ordenar por" }) {
  const atual = `${campo}:${direcao}`;
  const conhecida = opcoes.some((o) => `${o.campo}:${o.direcao}` === atual);

  return (
    <label className={c.grupoFiltro}>
      <span className={c.rotuloFiltro}>{rotulo}</span>
      <select
        className={`${c.selecao} ${s.selecao}`}
        value={conhecida ? atual : ""}
        onChange={(e) => {
          const [novoCampo, novaDirecao] = e.target.value.split(":");
          onChange(novoCampo, novaDirecao);
        }}
      >
        {/*
          So aparece se a URL trouxer um par que nao esta na lista - link
          antigo, ou alguem editando a query na mao. Melhor mostrar
          "personalizada" que deixar o controle mentindo com a primeira
          opcao selecionada.
        */}
        {!conhecida && <option value="">Ordenação personalizada</option>}
        {opcoes.map((o) => (
          <option key={`${o.campo}:${o.direcao}`} value={`${o.campo}:${o.direcao}`}>
            {o.rotulo}
          </option>
        ))}
      </select>
    </label>
  );
}

/**
 * O sentido do primeiro clique no header: o primeiro da lista para aquele
 * campo. As opcoes ja estao na ordem util, entao data comeca pela mais
 * recente e texto em A-Z.
 */
export function direcaoInicial(opcoes, campo) {
  return opcoes.find((o) => o.campo === campo)?.direcao || "desc";
}
