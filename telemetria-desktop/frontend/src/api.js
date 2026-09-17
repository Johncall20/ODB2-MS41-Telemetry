/*
  Camada fina sobre o fetch. Existe so para nao repetir o mesmo tratamento
  de erro em cada tela: o FastAPI devolve {"detail": "..."} nos 4xx e e essa
  frase que a interface precisa mostrar.
*/

/** Faz a chamada e devolve o JSON, ou levanta Error com a frase do backend. */
async function pedir(caminho, opcoes = {}) {
  const r = await fetch(caminho, {
    headers: opcoes.corpo ? { "Content-Type": "application/json" } : undefined,
    method: opcoes.metodo || "GET",
    body: opcoes.corpo ? JSON.stringify(opcoes.corpo) : undefined,
  });
  if (!r.ok) {
    let bruto = null;
    try {
      bruto = (await r.json()).detail;
    } catch {
      /* resposta sem json, fica so o status */
    }
    // O detail as vezes e objeto: o 409 de placa arquivada carrega o id e a
    // data para a tela poder oferecer a restauracao. A mensagem legivel vai
    // no Error, e o corpo inteiro fica pendurado em .detalhe.
    const erro = new Error(
      (bruto && (bruto.mensagem || (typeof bruto === "string" ? bruto : null))) ||
        `HTTP ${r.status}`
    );
    erro.status = r.status;
    erro.detalhe = bruto;
    throw erro;
  }
  return r.status === 204 ? null : r.json();
}

/*
  Monta a query string. Valor vazio, nulo ou false nao entra; array vira
  parametro repetido.
*/
/** Monta a query string a partir de um objeto de filtros. */
function _query(filtros) {
  const query = new URLSearchParams();
  for (const [chave, valor] of Object.entries(filtros)) {
    if (Array.isArray(valor)) {
      for (const item of valor) {
        if (item !== undefined && item !== null && item !== "") query.append(chave, String(item));
      }
      continue;
    }
    if (valor === undefined || valor === null || valor === "" || valor === false) continue;
    query.set(chave, String(valor));
  }
  const cauda = query.toString();
  return cauda ? `?${cauda}` : "";
}

export const api = {
  listarVeiculos: (filtros = {}) => pedir(`/api/veiculos${_query(filtros)}`),
  lerVeiculo: (id) => pedir(`/api/veiculos/${id}`),
  criarVeiculo: (dados) => pedir("/api/veiculos", { metodo: "POST", corpo: dados }),
  editarVeiculo: (id, dados) => pedir(`/api/veiculos/${id}`, { metodo: "PUT", corpo: dados }),
  // DELETE arquiva; nao remove linha nenhuma. Ver rotas/veiculos.py.
  arquivarVeiculo: (id) => pedir(`/api/veiculos/${id}`, { metodo: "DELETE" }),
  restaurarVeiculo: (id) => pedir(`/api/veiculos/${id}/restaurar`, { metodo: "POST" }),

  listarSessoes: (filtros = {}) => pedir(`/api/sessoes${_query(filtros)}`),
  lerSessao: (id) => pedir(`/api/sessoes/${id}`),

  // Downloads sao links diretos, nao fetch: quem monta o arquivo e o
  // backend e o Content-Disposition dele e que dispara o "salvar como".
  //
  // O NOME do arquivo tambem vem de la (`exportador.nome_arquivo`). Por
  // isso o link nao leva o atributo `download`: ele sobrescreveria o nome
  // do servidor e passariam a existir duas fontes, que divergem na
  // primeira vez que uma das duas mudar.
  enderecoExportacao: (id, formato, secoes) =>
    formato === "pdf"
      ? `/api/sessoes/${id}/pdf?secoes=${secoes.join(",")}`
      : `/api/sessoes/${id}/${formato}`,

  // Relatorios: agregacoes que atravessam varias sessoes. Tudo somado e
  // contado no SQL do backend (repositorios/relatorios.py).
  lerFrota: (periodo) => pedir(`/api/relatorios/frota${_query({ periodo })}`),
  lerEvolucao: (veiculoId, periodo) =>
    pedir(`/api/relatorios/evolucao${_query({ veiculo_id: veiculoId, periodo })}`),
  lerEventosAgregados: (filtros = {}) =>
    pedir(`/api/relatorios/eventos${_query(filtros)}`),
  lerComparacao: (a, b) => pedir(`/api/relatorios/comparacao${_query({ a, b })}`),

  // Os limites de alerta de um carro - os unicos que existem. O GET devolve
  // os seis valores; o PUT exige os seis, porque nao ha heranca de onde
  // completar um campo ausente.
  lerLimitesVeiculo: (id) => pedir(`/api/veiculos/${id}/limites`),
  gravarLimitesVeiculo: (id, limites) =>
    pedir(`/api/veiculos/${id}/limites`, { metodo: "PUT", corpo: limites }),

  // O ponto de partida que o botao "Usar valores sugeridos" preenche. Nao
  // e limite de ninguem: so preenche o formulario, salvar e outro ato.
  lerLimitesSugeridos: () => pedir("/api/limites/sugeridos"),

  iniciarSessao: (veiculoId) =>
    pedir("/api/sessoes", { metodo: "POST", corpo: { veiculo_id: veiculoId } }),
  encerrarSessao: () => pedir("/api/sessoes/encerrar", { metodo: "POST" }),
};
