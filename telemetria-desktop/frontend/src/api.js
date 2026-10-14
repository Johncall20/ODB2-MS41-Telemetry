/*
  Camada fina sobre o fetch, e o UNICO lugar que transforma falha em frase.
  Toda tela recebe um Error com `.message` em portugues para quem usa o
  app - nunca codigo de status, nunca objeto, nunca texto em ingles do
  navegador. O detalhe tecnico (metodo, rota, status, corpo) vai para o
  console.

  - o backend mandou frase (`detail`): e ela;
  - nao houve resposta (rede, servidor fora do ar, 502/503/504):
    FRASE_SEM_CONEXAO;
  - 500, ou resposta que nao e JSON: FRASE_INESPERADO;
  - 4xx sem frase: uma generica por status, sem o numero.

  401 fora do login avisa o AutenticacaoProvider (`quandoSessaoExpirar`),
  que zera o usuario - e a guarda leva ao /login com "sessão expirou".
*/

export const FRASE_SEM_CONEXAO =
  "Não foi possível conectar ao servidor. Verifique sua conexão e tente de novo.";
export const FRASE_INESPERADO = "Ocorreu um erro inesperado. Tente de novo em instantes.";

const FRASE_POR_STATUS = {
  400: "Não foi possível concluir a ação. Confira os dados e tente de novo.",
  401: "Sua sessão expirou. Entre de novo para continuar.",
  403: "Você não tem permissão para esta ação.",
  404: "Não encontramos o que você procurava. Ele pode ter sido removido.",
  409: "A ação não pôde ser concluída no estado atual. Recarregue a página e tente de novo.",
  422: "Confira os dados informados e tente de novo.",
};

let _aoExpirar = null;

/** Quem deve saber que a sessao expirou (o AutenticacaoProvider). */
export function quandoSessaoExpirar(funcao) {
  _aoExpirar = funcao;
}

/**
 * A sessao expirou por um caminho que nao passa por aqui: o websocket
 * fechado com 1008 pelo backend. Mesmo aviso de um 401, entao a mesma
 * tela de login com "Sua sessão expirou".
 */
export function avisarSessaoExpirada() {
  _aoExpirar?.();
}

function _falha(frase, extra = {}) {
  const erro = new Error(frase);
  Object.assign(erro, { status: null, detalhe: null, campos: {} }, extra);
  return erro;
}

/*
  Faz a chamada e devolve a Response JA conferida, ou levanta o Error com
  a frase. `semExpirar`: 401 desta rota nao e sessao expirada (login com
  senha errada, a pergunta "quem esta logado?" ao abrir o app).
*/
async function requisitar(caminho, opcoes = {}) {
  const metodo = opcoes.metodo || "GET";
  let r;
  try {
    r = await fetch(caminho, {
      headers: opcoes.corpo ? { "Content-Type": "application/json" } : undefined,
      method: metodo,
      body: opcoes.corpo ? JSON.stringify(opcoes.corpo) : undefined,
      // O cookie de sessao e httpOnly: o JS nao o le nem o anexa a mao, e e
      // isto que manda o navegador envia-lo. "include" e nao "same-origin"
      // porque o `npm run dev` sem proxy chama a 8000 de outra origem.
      credentials: "include",
    });
  } catch (causa) {
    console.error(`[api] ${metodo} ${caminho}: sem resposta`, causa);
    throw _falha(FRASE_SEM_CONEXAO);
  }
  if (r.ok) return r;

  const texto = await r.text().catch(() => "");
  let bruto = null;
  let ehJson = false;
  try {
    bruto = JSON.parse(texto).detail ?? null;
    ehJson = true;
  } catch {
    /* sem JSON: so a frase generica */
  }
  console.error(`[api] ${metodo} ${caminho}: ${r.status}`, texto);

  if (r.status === 401 && !opcoes.semExpirar) _aoExpirar?.();

  let frase;
  if ([502, 503, 504].includes(r.status)) frase = FRASE_SEM_CONEXAO;
  else if (r.status >= 500 || !ehJson) frase = FRASE_INESPERADO;
  else frase = _frase(bruto) || FRASE_POR_STATUS[r.status] || FRASE_INESPERADO;

  throw _falha(frase, { status: r.status, detalhe: bruto, campos: _campos(bruto) });
}

/** Faz a chamada e devolve o JSON, ou levanta Error com a frase. */
async function pedir(caminho, opcoes = {}) {
  const r = await requisitar(caminho, opcoes);
  if (r.status === 204) return null;
  try {
    return await r.json();
  } catch (causa) {
    console.error(`[api] ${opcoes.metodo || "GET"} ${caminho}: resposta sem JSON`, causa);
    throw _falha(FRASE_INESPERADO, { status: r.status });
  }
}

/*
  Baixa um arquivo da exportacao. Por fetch e nao por link: com link, um
  erro do servidor abria no navegador uma pagina com o corpo cru. O NOME
  continua sendo o do backend - lido do Content-Disposition, que
  `exportador.nome_arquivo()` monta. O front nao inventa nome nenhum.
*/
async function baixar(caminho) {
  const r = await requisitar(caminho);
  const blob = await r.blob();
  const cabecalho = r.headers.get("Content-Disposition") || "";
  const nome = /filename="?([^";]+)"?/i.exec(cabecalho)?.[1];
  if (!nome) console.error(`[api] GET ${caminho}: sem Content-Disposition`, cabecalho);
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = nome || "";
  document.body.appendChild(link);
  link.click();
  link.remove();
  // Revogar ja no proximo tique pode cortar o download em alguns
  // navegadores; um minuto sobra.
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

/*
  O UNICO lugar que le o `detail` do backend. Ele chega em tres formas, e
  nenhuma tela pode acabar mostrando objeto cru:

  - texto: a frase pronta (404, a maioria dos 409 e alguns 422);
  - objeto com `mensagem`: o 409 de placa arquivada, que carrega o id e a
    data para oferecer restauracao, e o 422 de validacao, que traz
    `campos` com um erro por campo;
  - lista: o 422 cru do FastAPI. O backend ja o converte no objeto acima;
    se uma lista escapar, as frases dela sao do Pydantic, em ingles, e a
    tela fica com a frase generica do 422.
*/
function _frase(bruto) {
  if (!bruto) return "";
  if (typeof bruto === "string") return bruto;
  if (Array.isArray(bruto)) return "";
  return typeof bruto.mensagem === "string" ? bruto.mensagem : "";
}

/** Erro por campo do 422 ({campo: frase}), ou objeto vazio. */
function _campos(bruto) {
  if (!bruto || typeof bruto !== "object" || Array.isArray(bruto)) return {};
  return bruto.campos && typeof bruto.campos === "object" ? bruto.campos : {};
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
  // --- autenticacao. O token nunca aparece aqui: vive no cookie httpOnly
  // que o backend define, e o navegador o manda sozinho.
  cadastro: (dados) =>
    pedir("/api/auth/cadastro", { metodo: "POST", corpo: dados, semExpirar: true }),
  // 401 no login e senha errada, e no `eu` e "ninguem logado" - nenhum
  // dos dois e sessao expirada.
  login: (credenciais) =>
    pedir("/api/auth/login", { metodo: "POST", corpo: credenciais, semExpirar: true }),
  logout: () => pedir("/api/auth/logout", { metodo: "POST", semExpirar: true }),
  eu: () => pedir("/api/auth/eu", { semExpirar: true }),

  trocarPapel: (papel) => pedir("/api/auth/eu", { metodo: "PUT", corpo: { papel } }),
  // A tela de Conta. Senha atual errada volta 403 (a pessoa esta logada),
  // e-mail em uso 409 - as duas com `mensagem` para o Aviso.
  editarPerfil: (dados) => pedir("/api/auth/eu/perfil", { metodo: "PUT", corpo: dados }),
  trocarSenha: (dados) => pedir("/api/auth/eu/senha", { metodo: "PUT", corpo: dados }),
  dadosDaConta: () => pedir("/api/auth/eu/dados"),
  // POST e nao DELETE: leva corpo (senha e confirmacao).
  excluirConta: (dados) => pedir("/api/auth/eu/excluir", { metodo: "POST", corpo: dados }),

  // Ler cliente vale para as duas contas; escrever, so para a
  // PROFISSIONAL - o backend responde 403 ao PARTICULAR.
  listarClientes: (filtros = {}) => pedir(`/api/clientes${_query(filtros)}`),
  lerCliente: (id) => pedir(`/api/clientes/${id}`),
  criarCliente: (dados) => pedir("/api/clientes", { metodo: "POST", corpo: dados }),
  editarCliente: (id, dados) =>
    pedir(`/api/clientes/${id}`, { metodo: "PUT", corpo: dados }),
  // DELETE arquiva, como no veiculo. 409 se o cliente tem carro ativo.
  arquivarCliente: (id) => pedir(`/api/clientes/${id}`, { metodo: "DELETE" }),
  restaurarCliente: (id) => pedir(`/api/clientes/${id}/restaurar`, { metodo: "POST" }),

  // O catalogo de marca e modelo (FIPE + os modelos customizados da
  // conta). Criar modelo com nome que ja existe devolve o existente.
  listarMarcas: () => pedir("/api/marcas"),
  listarModelos: (marcaId) => pedir(`/api/marcas/${marcaId}/modelos`),
  criarModelo: (marcaId, nome) =>
    pedir(`/api/marcas/${marcaId}/modelos`, { metodo: "POST", corpo: { nome } }),

  listarVeiculos: (filtros = {}) => pedir(`/api/veiculos${_query(filtros)}`),
  lerVeiculo: (id) => pedir(`/api/veiculos/${id}`),
  criarVeiculo: (dados) => pedir("/api/veiculos", { metodo: "POST", corpo: dados }),
  editarVeiculo: (id, dados) => pedir(`/api/veiculos/${id}`, { metodo: "PUT", corpo: dados }),
  // DELETE arquiva; nao remove linha nenhuma. Ver rotas/veiculos.py.
  arquivarVeiculo: (id) => pedir(`/api/veiculos/${id}`, { metodo: "DELETE" }),
  restaurarVeiculo: (id) => pedir(`/api/veiculos/${id}/restaurar`, { metodo: "POST" }),

  status: () => pedir("/api/status"),
  listarSessoes: (filtros = {}) => pedir(`/api/sessoes${_query(filtros)}`),
  lerSessao: (id) => pedir(`/api/sessoes/${id}`),

  // Downloads por fetch (`baixar`): erro vira frase na tela, e o nome do
  // arquivo e o do Content-Disposition do backend (`exportador.nome_arquivo`)
  // - o front nao monta nome, para nao existirem duas fontes que divergem.
  baixarExportacao: (id, formato, secoes) =>
    baixar(
      formato === "pdf"
        ? `/api/sessoes/${id}/pdf?secoes=${secoes.join(",")}`
        : `/api/sessoes/${id}/${formato}`
    ),

  // Relatorios: agregacoes que atravessam varias sessoes. Tudo somado e
  // contado no SQL do backend (repositorios/relatorios.py).
  lerFrota: (periodo) => pedir(`/api/relatorios/frota${_query({ periodo })}`),
  lerEvolucao: (veiculoId, periodo) =>
    pedir(`/api/relatorios/evolucao${_query({ veiculo_id: veiculoId, periodo })}`),
  lerEventosAgregados: (filtros = {}) =>
    pedir(`/api/relatorios/eventos${_query(filtros)}`),
  lerComparacao: (a, b) => pedir(`/api/relatorios/comparacao${_query({ a, b })}`),

  // De onde partir os limites da proxima sessao do carro: os da ultima
  // sessao dele com snapshot (ou null) e os sugeridos. Nao ha limite do
  // carro - eles sao escolhidos ao iniciar e ficam so na sessao.
  lerInicioSessao: (veiculoId) => pedir(`/api/veiculos/${veiculoId}/inicio-sessao`),

  // Os sugeridos sozinhos. O Ao vivo usa o `inicio-sessao`, que ja os
  // traz; esta continua para quem so precisa deles.
  lerLimitesSugeridos: () => pedir("/api/limites/sugeridos"),

  // Os seis limites vao planos no corpo, ao lado do veiculo: viram o
  // snapshot da sessao, sem edicao depois. `extra` leva `km` e
  // `observacao`, tambem planos. 422 traz o erro por campo.
  iniciarSessao: (veiculoId, limites, extra = {}) =>
    pedir("/api/sessoes", {
      metodo: "POST",
      corpo: { veiculo_id: veiculoId, ...limites, ...extra },
    }),
  // Notas e km de uma sessao, a qualquer momento (antes, durante e depois
  // da gravacao). So o que vier no objeto muda. A resposta traz a
  // quilometragem do carro depois da edicao.
  editarSessao: (id, dados) => pedir(`/api/sessoes/${id}`, { metodo: "PATCH", corpo: dados }),
  encerrarSessao: () => pedir("/api/sessoes/encerrar", { metodo: "POST" }),
  // O aviso de gravacao interrompida pelo reinicio do servidor foi visto.
  cienteInterrupcao: () => pedir("/api/status/ciente", { metodo: "POST" }),
};
