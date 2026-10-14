/*
  O que uma tela com `:id` mostra quando nao tem o que mostrar (ver
  `useCarga`): a migalha para a lista, a frase e a saida - "Voltar a lista"
  quando o registro nao existe, "Tentar de novo" quando a carga falhou.
  As frases moram aqui, uma por tipo de registro, e nao em cada tela.
*/
import { Link } from "react-router-dom";
import { Aviso } from "./Aviso.jsx";
import { Migalha } from "./Migalha.jsx";
import s from "./FalhaDeCarga.module.css";

const RECURSOS = {
  sessao: {
    lista: "/sessoes",
    nomeLista: "Sessões",
    naoExiste: "Esta sessão não existe ou não está na sua conta.",
    voltar: "Voltar às sessões",
  },
  veiculo: {
    lista: "/veiculos",
    nomeLista: "Veículos",
    naoExiste: "Este veículo não existe ou não está na sua conta.",
    voltar: "Voltar aos veículos",
  },
  cliente: {
    lista: "/clientes",
    nomeLista: "Clientes",
    naoExiste: "Este cliente não existe ou não está na sua conta.",
    voltar: "Voltar aos clientes",
  },
};

/** `recurso`: sessao, veiculo ou cliente. `falha` e `aoTentar` vem do useCarga. */
export function FalhaDeCarga({ recurso, falha, aoTentar }) {
  const r = RECURSOS[recurso];
  return (
    <>
      <Migalha para={r.lista}>{r.nomeLista}</Migalha>
      <Aviso className={s.aviso}>
        {falha.naoExiste ? (
          <>
            {r.naoExiste} <Link to={r.lista}>{r.voltar}</Link>
          </>
        ) : (
          <>
            {falha.frase}{" "}
            <button type="button" className={s.tentar} onClick={aoTentar}>
              Tentar de novo
            </button>
          </>
        )}
      </Aviso>
    </>
  );
}
