/*
  A coluna esquerda do Login e do Criar conta (nodes 2:5 e 3:532): logo no
  topo, headline, paragrafo e a barra de giro decorativa.

  Fica em `ui/` porque as duas telas de fora do Shell usam exatamente o
  mesmo painel - repetir o markup faria as duas sairem do ar uma da outra
  no primeiro ajuste de texto.
*/
import logo from "../../assets/logo.svg";
import s from "./PainelMarca.module.css";

/*
  Os doze blocos sao a barra de shift light do painel, usada como enfeite:
  seis verdes, tres ambar, tres vermelhos. Mesma linguagem visual da
  BarraGiro do Ao vivo, mas aqui nao mede nada - por isso e markup fixo e
  nao o componente de verdade.
*/
const BLOCOS = [
  ...Array(6).fill("ok"),
  ...Array(3).fill("atencao"),
  ...Array(3).fill("risco"),
];

/** O painel da marca, a esquerda das telas de entrada. */
export function PainelMarca() {
  return (
    <aside className={s.painel}>
      <div className={s.marca}>
        <img className={s.logo} src={logo} alt="" width="60" height="34" />
        <span className={s.nome}>
          <span className={s.nome}>
            ODB2 + MS41
            <br />
            Telemetry
          </span>
        </span>
      </div>

      <div className={s.conteudo}>
        <h1 className={s.titulo}>
          Seu carro gera mais
          <br />
          dados do que exibe
        </h1>
        <p className={s.texto}>
          Leitura ao vivo, gravação de sessão e análise dos dados do veículo,
          direto da porta OBD-II.
        </p>
        <div className={s.blocos} role="presentation">
          {BLOCOS.map((tom, i) => (
            <span key={i} className={`${s.bloco} ${s[tom]}`} />
          ))}
        </div>
      </div>
    </aside>
  );
}
