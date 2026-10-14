/*
  Campo de escolha com busca por digitacao, para o catalogo de marca e
  modelo (109 marcas; a maior marca tem 586 modelos).

  **So aceita o que esta na lista.** Controlado pelo id escolhido
  (`valor`); o texto da caixa e so a busca. Digitar nunca muda o valor -
  so escolher uma opcao. Ao sair do campo sem escolher, o texto volta ao
  nome do escolhido, ou fica vazio se nao havia.

  A lista mostra TODOS os resultados, com rolagem interna (cerca de 8
  itens visiveis). Sem corte e sem renderizacao virtual: 586 linhas
  desenham sem travar, e cortar esconderia justamente o modelo procurado.
  Se um dia travar de verdade, a virtualizacao entra aqui, sem mexer em
  quem usa.

  A busca ignora maiusculas e acentos e exige todas as palavras digitadas,
  em qualquer parte do nome e em qualquer ordem ("325 ia" acha "325iA
  2.5 24V"). O trecho que casou aparece destacado.

  Teclado: setas navegam, Enter escolhe - com exatamente um resultado,
  ou o item marcado pelas setas (com varios resultados e nada marcado,
  Enter nao escolhe nada: com 586 modelos, "o primeiro" seria um palpite).
  Esc fecha.

  Pecas fixas, fora do filtro e sempre visiveis no fim do painel:
  - `fixo`: uma opcao escolhivel, separada por uma linha (a marca "Outra").
  - `rodape`: uma acao ("Não encontrei meu modelo"), que recebe o texto
    digitado.
*/
import { useEffect, useId, useMemo, useRef, useState } from "react";
import { ChevronDown } from "lucide-react";
import c from "../../estilos/comum.module.css";
import s from "./Combobox.module.css";

const DIACRITICOS = /[̀-ͯ]/g;

/** Minusculo e sem acento, para comparar. Quem filtra a mesma lista em
 * outro lugar (as sugestoes do "Você quis dizer?") usa esta. */
export function chave(texto) {
  return (texto || "").normalize("NFD").replace(DIACRITICOS, "").toLowerCase();
}

/*
  A chave do texto e, para cada caractere dela, a posicao no original. Sem
  o mapa o destaque cairia no lugar errado: tirar o acento muda o tamanho
  do texto ("é" vira "e" + acento combinante, e o acento some).
*/
function chaveComMapa(texto) {
  let norm = "";
  const mapa = [];
  for (let i = 0; i < texto.length; i++) {
    const pedaco = chave(texto[i]);
    for (let j = 0; j < pedaco.length; j++) mapa.push(i);
    norm += pedaco;
  }
  return { norm, mapa };
}

/** O nome com os trechos que casaram com os termos marcados. */
function Destaque({ texto, termos }) {
  if (!termos.length) return texto;
  const { norm, mapa } = chaveComMapa(texto);
  const faixas = [];
  for (const termo of termos) {
    let de = norm.indexOf(termo);
    while (de !== -1) {
      faixas.push([mapa[de], mapa[de + termo.length - 1] + 1]);
      de = norm.indexOf(termo, de + termo.length);
    }
  }
  if (!faixas.length) return texto;
  faixas.sort((a, b) => a[0] - b[0]);
  const juntas = [faixas[0]];
  for (const [ini, fim] of faixas.slice(1)) {
    const ultima = juntas[juntas.length - 1];
    if (ini <= ultima[1]) ultima[1] = Math.max(ultima[1], fim);
    else juntas.push([ini, fim]);
  }
  const partes = [];
  let pos = 0;
  juntas.forEach(([ini, fim], i) => {
    if (ini > pos) partes.push(texto.slice(pos, ini));
    partes.push(
      <mark key={i} className={s.casou}>
        {texto.slice(ini, fim)}
      </mark>
    );
    pos = fim;
  });
  if (pos < texto.length) partes.push(texto.slice(pos));
  return partes;
}

export function Combobox({
  rotulo,
  opcoes,
  valor,
  aoEscolher,
  desabilitado = false,
  placeholder = "",
  erro,
  dica,
  contagem = { singular: "opção", plural: "opções" },
  vazio = "Nada encontrado.",
  fixo,
  rodape,
}) {
  const id = useId();
  const listaId = `${id}-lista`;
  const painel = useRef(null);

  // O escolhido pode ser o `fixo` (a "Outra"), que nao esta em `opcoes`.
  const escolhida =
    opcoes.find((o) => o.id === valor) || (fixo && fixo.id === valor ? fixo : null);

  const [aberto, setAberto] = useState(false);
  const [busca, setBusca] = useState(null); // null = mostrando o escolhido
  const [ativo, setAtivo] = useState(-1); // -1 = nada marcado pelas setas

  // A chave de cada opcao, calculada uma vez por lista, e nao por tecla.
  const comChave = useMemo(() => opcoes.map((o) => ({ ...o, _chave: chave(o.nome) })), [opcoes]);
  const termos = useMemo(() => chave(busca).split(/\s+/).filter(Boolean), [busca]);
  const filtradas = useMemo(
    () =>
      termos.length
        ? comChave.filter((o) => termos.every((t) => o._chave.includes(t)))
        : comChave,
    [comChave, termos]
  );

  // A ordem da navegacao por teclado: os resultados, o fixo, o rodape.
  const navegaveis = [
    ...filtradas.map((o) => ({ tipo: "opcao", opcao: o })),
    ...(fixo ? [{ tipo: "opcao", opcao: fixo }] : []),
    ...(rodape ? [{ tipo: "rodape" }] : []),
  ];

  // Ao abrir, a lista rola ate o escolhido; navegando, ate o marcado.
  useEffect(() => {
    if (!aberto || !painel.current) return;
    const alvo =
      ativo >= 0
        ? painel.current.querySelector(`#${CSS.escape(`${id}-op-${ativo}`)}`)
        : painel.current.querySelector("[data-escolhida='true']");
    alvo?.scrollIntoView({ block: "nearest" });
  }, [aberto, ativo, id]);

  function abrir() {
    if (desabilitado) return;
    setAberto(true);
    setAtivo(-1);
  }

  function fechar() {
    setAberto(false);
    setBusca(null);
    setAtivo(-1);
  }

  function escolher(opcao) {
    aoEscolher(opcao);
    fechar();
  }

  function acionarRodape() {
    const digitado = (busca || "").trim();
    fechar();
    rodape.aoEscolher(digitado);
  }

  function acionar(item) {
    if (item.tipo === "rodape") acionarRodape();
    else escolher(item.opcao);
  }

  function aoTeclar(e) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      if (!aberto) return abrir();
      setAtivo((a) => Math.min(a + 1, navegaveis.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setAtivo((a) => Math.max(a - 1, 0));
    } else if (e.key === "Enter" && aberto) {
      // Enter dentro do combobox nunca envia o formulario.
      e.preventDefault();
      if (ativo >= 0) acionar(navegaveis[ativo]);
      else if (filtradas.length === 1) escolher(filtradas[0]);
    } else if (e.key === "Escape" && aberto) {
      e.preventDefault();
      e.stopPropagation();
      fechar();
    }
  }

  // O fixo conta: "109 marcas" inclui a "Outra".
  const total = opcoes.length + (fixo ? 1 : 0);
  const nome = total === 1 ? contagem.singular : contagem.plural;
  const cabecalho = termos.length
    ? `${filtradas.length} de ${total} ${nome}`
    : `${total} ${nome} · digite para filtrar`;

  const texto = busca ?? (escolhida ? escolhida.nome : "");

  // Funcao, e nao componente: um componente declarado aqui dentro seria um
  // tipo novo a cada render, e o React remontaria as 586 linhas a cada
  // tecla ou passada do mouse.
  function item(opcao, indice) {
    const marcado = indice === ativo;
    return (
      <li
        key={opcao.id}
        id={`${id}-op-${indice}`}
        role="option"
        aria-selected={opcao.id === valor}
        data-escolhida={opcao.id === valor}
        className={`${s.opcao} ${marcado ? s.opcaoAtiva : ""} ${
          opcao.id === valor ? s.opcaoEscolhida : ""
        }`.trim()}
        // mousedown com preventDefault: o clique acontece antes do blur,
        // entao fechar no blur nao engole a escolha.
        onMouseDown={(e) => {
          e.preventDefault();
          escolher(opcao);
        }}
        onMouseEnter={() => setAtivo(indice)}
      >
        <span className={s.nome}>
          <Destaque texto={opcao.nome} termos={termos} />
        </span>
        {opcao.marcador && <span className={s.marcador}>{opcao.marcador}</span>}
      </li>
    );
  }

  return (
    <div className={c.campo}>
      <label className={c.campoRotulo} htmlFor={id}>
        {rotulo}
      </label>
      <div className={s.linha}>
        <input
          id={id}
          className={`${c.entrada} ${s.entrada} ${erro ? c.entradaInvalida : ""}`.trim()}
          role="combobox"
          aria-expanded={aberto}
          aria-controls={listaId}
          aria-autocomplete="list"
          aria-activedescendant={aberto && ativo >= 0 ? `${id}-op-${ativo}` : undefined}
          aria-invalid={erro ? true : undefined}
          value={texto}
          placeholder={placeholder}
          disabled={desabilitado}
          autoComplete="off"
          onChange={(e) => {
            setBusca(e.target.value);
            setAberto(true);
            setAtivo(-1);
          }}
          onFocus={abrir}
          onClick={abrir}
          // Sair sem escolher: `fechar` zera a busca, e o texto volta ao
          // escolhido (ou fica vazio). O campo nunca guarda texto solto.
          onBlur={fechar}
          onKeyDown={aoTeclar}
        />
        <ChevronDown
          className={`${s.seta} ${aberto ? s.setaAberta : ""}`.trim()}
          size={18}
          aria-hidden="true"
        />

        {/* O painel mora AQUI, junto da entrada, e nao na caixa do campo:
            a caixa estica com a linha da grade (texto de apoio ou erro de
            um campo vizinho), e o top: 100% dela descolava a lista. */}
        {aberto && (
          <div ref={painel} id={listaId} className={s.painel} role="listbox" aria-label={rotulo}>
            {/* Fixa e nao escolhivel: diz quantos ha e que da para digitar. */}
            <p className={s.cabecalho} aria-live="polite">
              {cabecalho}
            </p>

            <ul className={s.rolagem} role="presentation">
              {filtradas.map((o, i) => item(o, i))}
              {filtradas.length === 0 && <li className={s.vazio}>{vazio}</li>}
            </ul>

            {(fixo || rodape) && (
              <ul className={s.fixos} role="presentation">
                {fixo && item(fixo, filtradas.length)}
                {rodape && (
                  <li
                    id={`${id}-op-${navegaveis.length - 1}`}
                    role="option"
                    aria-selected={false}
                    className={`${s.opcao} ${s.rodape} ${
                      ativo === navegaveis.length - 1 ? s.opcaoAtiva : ""
                    }`.trim()}
                    onMouseDown={(e) => {
                      e.preventDefault();
                      acionarRodape();
                    }}
                    onMouseEnter={() => setAtivo(navegaveis.length - 1)}
                  >
                    {rodape.rotulo}
                  </li>
                )}
              </ul>
            )}
          </div>
        )}
      </div>

      {dica && !erro && <span className={s.dica}>{dica}</span>}
      {erro && <span className={c.campoErro}>{erro}</span>}
    </div>
  );
}
