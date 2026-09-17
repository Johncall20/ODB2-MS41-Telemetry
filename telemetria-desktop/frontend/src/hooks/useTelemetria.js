/*
  O que esta acontecendo agora no carro: amostra, evento e estado do
  leitor.

  Nao abre socket. A conexao e uma so, do TelemetriaProvider montado no
  Shell, e este hook e a janela para ela - por isso qualquer numero de
  telas pode chamar sem multiplicar conexao. A assinatura de retorno e a
  mesma de quando o hook abria o socket sozinho.
*/
import { useContext } from "react";
import { ContextoTelemetria } from "./TelemetriaProvider.jsx";

/** Le a telemetria do provider. Toda tela que mostra dado ao vivo usa isto. */
export function useTelemetria() {
  const valor = useContext(ContextoTelemetria);
  if (valor === null) {
    // Erro explicito em vez de devolver undefined: sem o provider o
    // componente quebraria depois, com um "cannot read property of
    // undefined" longe da causa.
    throw new Error(
      "useTelemetria() usado fora do TelemetriaProvider - ele e montado no Shell."
    );
  }
  return valor;
}
