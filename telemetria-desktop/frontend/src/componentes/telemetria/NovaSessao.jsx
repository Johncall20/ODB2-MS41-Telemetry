/*
  O popup "Nova sessão": o que TRAVA quando a gravacao comeca - os limites
  e o km - e escolhido aqui. As notas continuam editaveis durante a
  gravacao, entao ficam na pagina e chegam por prop.

  `<dialog>` nativo com `showModal()`: o resto da pagina fica inerte (o
  Tab nao sai do popup), Esc dispara `cancel` e o foco volta sozinho ao
  botao que abriu. Nao ha prendedor de foco escrito a mao.

  O popup so existe enquanto esta aberto - quem usa o monta e desmonta. E
  isso que faz "Cancelar nao guarda nada": reabrir monta tudo de novo,
  no estado inicial do carro.
*/
import { useEffect, useRef, useState } from "react";
import { api } from "../../api.js";
import { anoVeiculo, formatarPlaca, milhar } from "../../formato.js";
import { Aviso } from "../ui/Aviso.jsx";
import { CampoKm } from "../ui/CampoKm.jsx";
import { LimitesSessao, limitesDePartida, numericos, seis } from "./LimitesSessao.jsx";
import c from "../../estilos/comum.module.css";
import s from "./NovaSessao.module.css";

export function NovaSessao({ veiculo, inicio, notas, aoIniciar, aoFechar }) {
  const dialogo = useRef(null);
  const principal = useRef(null);
  // Guarda contra envio duplo: Enter num input dispara o keydown E o
  // envio implicito do formulario no mesmo tique, antes de o estado
  // `ocupado` chegar.
  const enviando = useRef(false);

  const partida = limitesDePartida(inicio);
  const [origem, setOrigem] = useState(partida?.origem || "sugeridos");
  const [valores, setValores] = useState(partida?.valores || seis(inicio?.sugeridos));
  const kmDoCarro = inicio?.quilometragem ?? null;
  const [km, setKm] = useState(kmDoCarro);
  const [erros, setErros] = useState({});
  const [erroGeral, setErroGeral] = useState("");
  const [ocupado, setOcupado] = useState(false);

  // Abre como modal ao montar, com o foco no botao principal. O
  // `autoFocus` do React chega antes do showModal(), entao o foco e dado
  // a mao, depois dele.
  useEffect(() => {
    const el = dialogo.current;
    if (!el.open) el.showModal();
    principal.current?.focus();
    return () => {
      if (el.open) el.close();
    };
  }, []);

  const kmMenor = km !== null && kmDoCarro !== null && km < kmDoCarro;

  function escolherOrigem(nova) {
    setErros({});
    setOrigem(nova);
    // Personalizar parte do que esta na tela; as outras trocam pelos da fonte.
    if (nova === "ultima" && inicio?.ultima_sessao) setValores(seis(inicio.ultima_sessao));
    if (nova === "sugeridos" && inicio) setValores(seis(inicio.sugeridos));
  }

  async function iniciar(e) {
    e?.preventDefault();
    if (enviando.current) return;
    enviando.current = true;
    setErros({});
    setErroGeral("");
    setOcupado(true);
    try {
      await api.iniciarSessao(veiculo.id, numericos(valores), { km, observacao: notas });
      await aoIniciar();
    } catch (falha) {
      // 422: o popup fica aberto e cada erro vai para o seu campo. Os de
      // limite so tem input em "Personalizar", entao o popup passa para
      // la - partindo dos mesmos valores, que e o que o backend recusou.
      const campos = falha.campos || {};
      const { km: erroKm, observacao: erroNotas, ...limites } = campos;
      if (Object.keys(limites).length) setOrigem("personalizar");
      setErros({ ...limites, km: erroKm });
      if (erroNotas) setErroGeral(`Notas: ${erroNotas}`);
      else if (!Object.keys(campos).length) setErroGeral(String(falha.message || falha));
      setOcupado(false);
      enviando.current = false;
    }
  }

  // Enter confirma de qualquer lugar do popup, menos de um botao (Enter
  // em "Cancelar" e cancelar). Esc chega como `cancel`, abaixo.
  function aoTeclar(e) {
    if (e.key !== "Enter" || e.target.tagName === "BUTTON") return;
    iniciar(e);
  }

  const ano = anoVeiculo(veiculo);
  const carro = [
    veiculo?.descricao,
    formatarPlaca(veiculo?.placa),
    ano,
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <dialog
      ref={dialogo}
      className={s.dialogo}
      aria-labelledby="nova-sessao-titulo"
      onCancel={(e) => {
        e.preventDefault();
        if (!ocupado) aoFechar();
      }}
      onKeyDown={aoTeclar}
    >
      <form className={s.corpo} onSubmit={iniciar} noValidate>
        <header>
          <h2 id="nova-sessao-titulo" className={s.titulo}>
            Nova sessão
          </h2>
          <p className={s.carro}>{carro}</p>
        </header>

        <section className={s.secao} aria-labelledby="nova-sessao-limites">
          <h3 id="nova-sessao-limites" className={s.secaoTitulo}>
            Limites de alerta
          </h3>
          <LimitesSessao
            inicio={inicio}
            origem={origem}
            valores={valores}
            erros={erros}
            aoEscolherOrigem={escolherOrigem}
            aoMudar={(campo, texto) => {
              setErros((atual) => ({ ...atual, [campo]: undefined }));
              setValores((atual) => ({ ...atual, [campo]: texto }));
            }}
          />
        </section>

        <section className={s.secao} aria-labelledby="nova-sessao-km">
          <h3 id="nova-sessao-km" className={s.secaoTitulo}>
            Quilometragem
          </h3>
          <CampoKm
            className={s.km}
            rotulo="No painel"
            valor={km}
            aoMudar={(novo) => {
              setKm(novo);
              setErros((atual) => ({ ...atual, km: undefined }));
            }}
            erro={erros.km}
            dica="opcional"
          />
          <p className={s.apoio}>
            {kmDoCarro !== null && `No cadastro do carro: ${milhar(kmDoCarro)} km. `}
            Atualiza ao encerrar a sessão.
          </p>
          {kmMenor && (
            <p className={s.alerta} role="status">
              Menor que a quilometragem do carro ({milhar(kmDoCarro)} km). Se foi troca de
              painel ou correção, pode iniciar mesmo assim.
            </p>
          )}
        </section>

        {erroGeral && <Aviso>{erroGeral}</Aviso>}

        <footer className={s.rodape}>
          <button className={c.botao} type="button" onClick={aoFechar} disabled={ocupado}>
            Cancelar
          </button>
          <button
            ref={principal}
            className={`${c.botao} ${c.botaoPrimario}`}
            type="submit"
            disabled={ocupado}
          >
            {ocupado ? "Iniciando…" : kmMenor ? "Iniciar mesmo assim" : "Iniciar gravação"}
          </button>
        </footer>
      </form>
    </dialog>
  );
}
