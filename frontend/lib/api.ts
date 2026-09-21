/**
 * Cliente de API central (implementation-contract.md run
 * 20260902-1448-frontend-mvp-web) — todas as chamadas ao backend Django
 * passam por aqui. Nomes de campo em português, espelhando exatamente os
 * serializers do backend (identidade/serializers.py, feed/serializers.py,
 * assinatura/serializers.py) — conferidos por leitura direta desses
 * arquivos antes de escrever este cliente, não adivinhados.
 */

// Navegador em produção usa a MESMA ORIGEM (`/api/...`): o Nginx de cada
// ambiente (`infra/nginx/portal-{dev,homolog,prod}.conf`) já roteia `/api/`
// para a API local — assim o bundle funciona via domínio, IP ou localhost
// sem precisar rebakear a URL a cada deploy (incidente 2026-09-18/19:
// "Não foi possível conectar ao servidor" com domínio ainda sem DNS).
// Servidor (SSR) e `next dev` mantêm a URL absoluta de antes.
export const API_BASE_URL =
  typeof window !== "undefined" && process.env.NODE_ENV === "production"
    ? ""
    : process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, detail: unknown, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

function extrairMensagemDeErro(corpo: unknown, status: number): string {
  if (corpo && typeof corpo === "object") {
    const objeto = corpo as Record<string, unknown>;
    if (typeof objeto.detail === "string" && objeto.detail.trim().length > 0) {
      const extra = typeof objeto.request_id === "string" && objeto.request_id ? ` (id: ${String(objeto.request_id).slice(0, 8)})` : "";
      return objeto.detail + extra;
    }
    // DRF costuma devolver erros de validação como {campo: ["mensagem"]}
    const primeiraChave = Object.keys(objeto)[0];
    if (primeiraChave) {
      const valor = objeto[primeiraChave];
      if (Array.isArray(valor) && typeof valor[0] === "string") {
        return valor[0];
      }
    }
  }
  if (status === 504 || status === 502) {
    return "Tempo esgotado ao executar a ingestão — o servidor ainda pode estar processando. Aguarde e recarregue o Histórico.";
  }
  return `Erro inesperado (status ${status}).`;
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  token?: string | null
): Promise<T> {
  // Upload de arquivo (ex.: credenciamento/solicitar/) usa FormData — nunca
  // definir Content-Type manualmente nesse caso, o navegador precisa gerar o
  // boundary do multipart sozinho.
  const ehFormData = typeof FormData !== "undefined" && options.body instanceof FormData;
  const headers: Record<string, string> = {
    ...(ehFormData ? {} : { "Content-Type": "application/json" }),
    ...((options.headers as Record<string, string>) || {}),
  };
  if (token) {
    headers["Authorization"] = `Token ${token}`;
  }

  let resposta: Response;
  try {
    resposta = await fetch(`${API_BASE_URL}${path}`, { ...options, headers });
  } catch (err) {
    console.error("[api] fetch falhou", err);
    throw new ApiError(
      0,
      null,
      "Não foi possível conectar ao servidor. Verifique sua conexão e tente novamente."
    );
  }

  let corpo: unknown = null;
  const texto = await resposta.text();
  if (texto) {
    try {
      corpo = JSON.parse(texto);
    } catch {
      corpo = null;
    }
  }

  if (!resposta.ok) {
    throw new ApiError(resposta.status, corpo, extrairMensagemDeErro(corpo, resposta.status));
  }

  return corpo as T;
}

// ---------------------------------------------------------------------------
// identidade/
// ---------------------------------------------------------------------------

export interface Usuario {
  id: number;
  email: string;
  nome: string;
  papel: "free" | "premium" | "admin";
  email_verificado: boolean;
  interesses: string[];
  localidade: string;
  canal_preferido: string;
  onboarding_concluido: boolean;
  onboarding_pulado: boolean;
  consentimento_aceito_em: string | null;
  consentimento_versao_termos: string;
  deve_trocar_senha: boolean;
  date_joined: string;
}

export interface LoginResposta {
  token: string;
  usuario: Usuario;
}

export function cadastrar(dados: {
  email: string;
  senha: string;
  nome?: string;
  aceite_termos: boolean;
}): Promise<{ detail: string; usuario: Usuario }> {
  return request("/api/auth/cadastro/", {
    method: "POST",
    body: JSON.stringify(dados),
  });
}

export function verificarEmail(token: string): Promise<{ detail: string }> {
  return request("/api/auth/verificar-email/", {
    method: "POST",
    body: JSON.stringify({ token }),
  });
}

export function login(email: string, senha: string): Promise<LoginResposta> {
  return request("/api/auth/login/", {
    method: "POST",
    body: JSON.stringify({ email, senha }),
  });
}

export function logout(token: string): Promise<{ detail: string }> {
  return request("/api/auth/logout/", { method: "POST" }, token);
}

export function recuperarSenha(email: string): Promise<{ detail: string }> {
  return request("/api/auth/recuperar-senha/", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
}

export function redefinirSenha(
  uid: string,
  token: string,
  nova_senha: string
): Promise<{ detail: string }> {
  return request("/api/auth/redefinir-senha/", {
    method: "POST",
    body: JSON.stringify({ uid, token, nova_senha }),
  });
}

export function trocarSenha(
  token: string,
  dados: { senha_atual: string; nova_senha: string }
): Promise<{ detail: string; token: string }> {
  return request(
    "/api/auth/trocar-senha/",
    { method: "POST", body: JSON.stringify(dados) },
    token
  );
}

export interface OnboardingDados {
  interesses: string[];
  localidade: string;
  canal_preferido: string;
  onboarding_concluido: boolean;
  onboarding_pulado: boolean;
}

export interface PreferenciasCookies {
  analytics: boolean;
  personalizacao: boolean;
  atualizado_em: string | null;
}

// Preferências de cookies (implementation-contract.md run
// 20260903-1134-seo-lgpd-design-system, escopo B) — só existe para usuário
// AUTENTICADO; visitante anônimo usa somente localStorage
// (ver lib/cookie-consent.ts). Lacuna de backend encontrada e corrigida
// nesta run: endpoint não existia antes.
export function obterPreferenciasCookies(token: string): Promise<PreferenciasCookies> {
  return request("/api/preferencias-cookies/", { method: "GET" }, token);
}

export function atualizarPreferenciasCookies(
  token: string,
  dados: { analytics: boolean; personalizacao: boolean }
): Promise<PreferenciasCookies> {
  return request(
    "/api/preferencias-cookies/",
    { method: "PUT", body: JSON.stringify(dados) },
    token
  );
}

export function obterOnboarding(token: string): Promise<OnboardingDados> {
  return request("/api/onboarding/", { method: "GET" }, token);
}

export function atualizarOnboarding(
  token: string,
  dados: Partial<{
    interesses: string[];
    localidade: string;
    canal_preferido: string;
    pular: boolean;
  }>
): Promise<OnboardingDados> {
  return request(
    "/api/onboarding/",
    { method: "PATCH", body: JSON.stringify(dados) },
    token
  );
}

// ---------------------------------------------------------------------------
// feed/
// ---------------------------------------------------------------------------

export interface FeedEntrada {
  tipo: "cluster" | "item";
  id: number;
  titulo: string;
  resumo: string;
  categoria: string;
  urgente: boolean;
  numero_fontes: number;
  timestamp: string;
  imagem_url?: string;
  // Localidade best-effort do backend (NewsItem.pais/estado/cidade) — vazia
  // quando o pipeline não inferiu. O frontend só exibe quando existir,
  // nunca inventa.
  pais?: string;
  estado?: string;
  cidade?: string;
  // Fonte representante (rastreabilidade BRD seção 18) — exibida como
  // "Fonte: X"; nunca inventar autor/colunista.
  nome_fonte?: string;
  // FRENTE 3 — autor/colunista creditado no RSS (best-effort). Preferido a
  // nome_fonte na linha de autoria; nunca inventado.
  autor?: string;
}

export interface FeedResposta {
  count: number;
  next: string | null;
  previous: string | null;
  results: FeedEntrada[];
  exibir_publicidade: boolean;
}

export function obterFeed(params: {
  categoria?: string;
  busca?: string;
  page?: number;
  page_size?: number;
}): Promise<FeedResposta> {
  const query = new URLSearchParams();
  if (params.categoria) query.set("categoria", params.categoria);
  if (params.busca) query.set("busca", params.busca);
  if (params.page) query.set("page", String(params.page));
  if (params.page_size) query.set("page_size", String(params.page_size));
  const qs = query.toString();
  return request(`/api/feed/${qs ? `?${qs}` : ""}`, { method: "GET" });
}

export function obterUrgentes(limite = 6): Promise<FeedEntrada[]> {
  return request(`/api/feed/urgentes/?limite=${limite}`, { method: "GET" });
}
export function obterMaisLidas(limite = 5): Promise<FeedEntrada[]> {
  return request(`/api/feed/mais-lidas/?limite=${limite}`, { method: "GET" });
}
export async function assinarNewsletterPublica(email: string, categoria = "geral"): Promise<{ detail: string }> {
  try {
    return await request("/api/newsletter/inscrever-publica/", { method: "POST", body: JSON.stringify({ email, categoria }) });
  } catch {
    return request("/api/landing/lista-espera/", { method: "POST", body: JSON.stringify({ nome: email.split("@")[0], email, interesses: [categoria], aceite_comunicacao: true }) });
  }
}

export interface FonteDetalhe {
  nome_fonte: string;
  url_fonte_original: string;
  resumo: string;
  imagem_url?: string;
  conteudo?: string;
}

export interface FeedDetalhe {
  tipo: "cluster" | "item";
  id: number;
  titulo: string;
  categoria: string;
  urgente: boolean;
  timestamp: string;
  pais?: string;
  estado?: string;
  cidade?: string;
  fontes: FonteDetalhe[];
  exibir_publicidade: boolean;
}

export function obterDetalheCluster(id: number | string): Promise<FeedDetalhe> {
  return request(`/api/feed/cluster/${id}/`, { method: "GET" });
}

export function obterDetalheItem(id: number | string): Promise<FeedDetalhe> {
  return request(`/api/feed/item/${id}/`, { method: "GET" });
}

// ---------------------------------------------------------------------------
// feed/ — FRENTE 3 (algoritmos + busca + agrupamento). Transporte puro: todo
// score/ranking/seção vem pronto do backend (feed/recomendacao.py,
// feed/busca.py); aqui só tipos + chamadas.
// ---------------------------------------------------------------------------

export interface EntradaRanqueda extends FeedEntrada {
  score?: number;
  motivo?: string;
  override?: string | null;
}

export type NomeSecaoHome = "manchetes" | "curadoria" | "para_voce" | "populares" | "tendencia" | "recentes";

export type SecoesHome = Record<NomeSecaoHome, EntradaRanqueda[]>;

export interface HomeSecoesResposta extends SecoesHome {
  exibir_publicidade: boolean;
}

export function obterHomeSecoes(params: {
  limite?: number;
  pais?: string;
  estado?: string;
  cidade?: string;
} = {}): Promise<HomeSecoesResposta> {
  const query = new URLSearchParams();
  if (params.limite) query.set("limite", String(params.limite));
  if (params.pais) query.set("pais", params.pais);
  if (params.estado) query.set("estado", params.estado);
  if (params.cidade) query.set("cidade", params.cidade);
  const qs = query.toString();
  return request(`/api/feed/home/${qs ? `?${qs}` : ""}`, { method: "GET" });
}

export function obterDestaquesDia(params: {
  limite?: number;
  pais?: string;
  estado?: string;
  cidade?: string;
} = {}): Promise<EntradaRanqueda[]> {
  const query = new URLSearchParams();
  if (params.limite) query.set("limite", String(params.limite));
  if (params.pais) query.set("pais", params.pais);
  if (params.estado) query.set("estado", params.estado);
  if (params.cidade) query.set("cidade", params.cidade);
  const qs = query.toString();
  return request(`/api/feed/destaques/${qs ? `?${qs}` : ""}`, { method: "GET" });
}

export interface ResultadoBusca extends EntradaRanqueda {
  relevancia?: number;
  trecho?: string;
}

export interface BuscaResposta {
  query: string;
  count: number;
  total_candidatos: number;
  results: ResultadoBusca[];
  sugestao?: string;
}

export function buscarNoticias(params: {
  q: string;
  categoria?: string;
  autor?: string;
  pais?: string;
  estado?: string;
  cidade?: string;
  data_de?: string;
  data_ate?: string;
  limite?: number;
}): Promise<BuscaResposta> {
  const query = new URLSearchParams();
  query.set("q", params.q);
  if (params.categoria) query.set("categoria", params.categoria);
  if (params.autor) query.set("autor", params.autor);
  if (params.pais) query.set("pais", params.pais);
  if (params.estado) query.set("estado", params.estado);
  if (params.cidade) query.set("cidade", params.cidade);
  if (params.data_de) query.set("data_de", params.data_de);
  if (params.data_ate) query.set("data_ate", params.data_ate);
  if (params.limite) query.set("limite", String(params.limite));
  return request(`/api/feed/busca/?${query.toString()}`, { method: "GET" });
}

export function autocompleteBusca(q: string): Promise<{ query: string; sugestoes: string[] }> {
  return request(`/api/feed/busca/autocomplete/?q=${encodeURIComponent(q)}`, { method: "GET" });
}

export function termosPopularesBusca(): Promise<{ termos: { termo: string; total: number }[] }> {
  return request("/api/feed/busca/populares/", { method: "GET" });
}

export function historicoBusca(): Promise<{ historico: string[] }> {
  return request("/api/feed/busca/historico/", { method: "GET" });
}

export interface AtualizacaoCobertura {
  nome_fonte: string;
  url_fonte_original: string;
  titulo: string;
  timestamp: string;
}

export interface CoberturaCompleta extends FeedDetalhe {
  total_atualizacoes: number;
  numero_fontes: number;
  atualizacoes: AtualizacaoCobertura[];
  relacionadas: ResultadoBusca[];
}

export function obterCobertura(tipo: "cluster" | "item", id: number | string): Promise<CoberturaCompleta> {
  return request(`/api/feed/cobertura/${tipo}/${id}/`, { method: "GET" });
}

export function registrarInteracaoFeed(dados: {
  tipo: "view" | "click" | "read" | "save" | "unsave" | "share" | "search_click";
  entry_tipo: "cluster" | "item";
  entry_id: number;
  tempo_leitura_seg?: number;
  query?: string;
}): Promise<{ detail: string }> {
  return request("/api/feed/interacoes/", { method: "POST", body: JSON.stringify(dados) });
}

export function obterRadarParaVoce(params: {
  pais?: string;
  estado?: string;
  cidade?: string;
  limite?: number;
} = {}): Promise<{ aviso_metodologia: string; localidade: { pais: string | null; estado: string | null; cidade: string | null }; secoes: SecoesHome }> {
  const query = new URLSearchParams();
  if (params.pais) query.set("pais", params.pais);
  if (params.estado) query.set("estado", params.estado);
  if (params.cidade) query.set("cidade", params.cidade);
  if (params.limite) query.set("limite", String(params.limite));
  const qs = query.toString();
  return request(`/api/radar/para-voce/${qs ? `?${qs}` : ""}`, { method: "GET" });
}

// ---------------------------------------------------------------------------
// assinatura/
// ---------------------------------------------------------------------------

export interface Plano {
  id: number;
  nome: string;
  preco: string;
  duracao_dias: number;
  ativo?: boolean;
}

export type StatusAssinatura =
  | "teste"
  | "ativa"
  | "pagamento_pendente"
  | "inadimplente"
  | "cancelada"
  | "expirada"
  | "encerrada";

export interface Assinatura {
  id: number;
  plan: Plano;
  status: StatusAssinatura;
  preco_cobrado: string;
  duracao_dias_no_momento: number;
  inicio: string | null;
  vencimento: string | null;
  renovacao_automatica: boolean;
  grace_period_termina_em: string | null;
  checkout_url?: string;
}

export interface Pagamento {
  id: number;
  valor: string;
  status: "aprovado" | "recusado" | "pendente" | "estornado";
  criado_em: string;
}

export function obterPlanos(): Promise<Plano[]> {
  return request("/api/assinatura/planos/", { method: "GET" });
}

export function assinarPlano(token: string, planId: number): Promise<Assinatura> {
  return request(
    "/api/assinatura/assinar/",
    { method: "POST", body: JSON.stringify({ plan_id: planId }) },
    token
  );
}

export function cancelarAssinatura(token: string): Promise<Assinatura> {
  return request("/api/assinatura/cancelar/", { method: "POST" }, token);
}

export async function obterMinhaAssinatura(token: string): Promise<Assinatura | null> {
  try {
    return await request<Assinatura>("/api/assinatura/minha/", { method: "GET" }, token);
  } catch (erro) {
    if (erro instanceof ApiError && erro.status === 404) {
      return null;
    }
    throw erro;
  }
}

export function obterHistoricoPagamentos(token: string): Promise<Pagamento[]> {
  return request("/api/assinatura/historico-pagamentos/", { method: "GET" }, token);
}

// ---------------------------------------------------------------------------
// credenciamento/ — campos conferidos em credenciamento/serializers.py e
// views.py (run 20260902-1503-credenciamento-jornalistas).
// ---------------------------------------------------------------------------

export type StatusCredenciamento = "pendente" | "aprovado" | "reprovado" | "info_solicitada";

export interface SolicitacaoCredenciamento {
  id: number;
  telefone: string;
  cidade: string;
  uf: string;
  foto: string | null;
  mini_bio: string;
  dados_profissionais: string;
  documento: string;
  status: StatusCredenciamento;
  criado_em: string;
  decidido_em: string | null;
  motivo_decisao: string;
}

export function solicitarCredenciamento(
  token: string,
  dados: {
    cidade: string;
    uf: string;
    mini_bio: string;
    dados_profissionais: string;
    documento: File;
    telefone?: string;
  }
): Promise<SolicitacaoCredenciamento> {
  const formData = new FormData();
  formData.append("cidade", dados.cidade);
  formData.append("uf", dados.uf);
  formData.append("mini_bio", dados.mini_bio);
  formData.append("dados_profissionais", dados.dados_profissionais);
  formData.append("documento", dados.documento);
  if (dados.telefone) formData.append("telefone", dados.telefone);
  return request("/api/credenciamento/solicitar/", { method: "POST", body: formData }, token);
}

export async function obterMinhaSolicitacaoCredenciamento(
  token: string
): Promise<SolicitacaoCredenciamento | null> {
  try {
    return await request<SolicitacaoCredenciamento>(
      "/api/credenciamento/minha-solicitacao/",
      { method: "GET" },
      token
    );
  } catch (erro) {
    if (erro instanceof ApiError && erro.status === 404) {
      return null;
    }
    throw erro;
  }
}

export interface PerfilJornalista {
  foto: string | null;
  mini_bio: string;
  dados_profissionais: string;
  selo_ativo: boolean;
  suspenso: boolean;
  credenciado_em: string;
}

export async function obterMeuPerfilJornalista(token: string): Promise<PerfilJornalista | null> {
  try {
    return await request<PerfilJornalista>("/api/credenciamento/meu-perfil/", { method: "GET" }, token);
  } catch (erro) {
    if (erro instanceof ApiError && erro.status === 404) {
      return null;
    }
    throw erro;
  }
}

export function atualizarMeuPerfilJornalista(
  token: string,
  dados: { mini_bio?: string; dados_profissionais?: string; foto?: File }
): Promise<PerfilJornalista> {
  const formData = new FormData();
  if (dados.mini_bio !== undefined) formData.append("mini_bio", dados.mini_bio);
  if (dados.dados_profissionais !== undefined) formData.append("dados_profissionais", dados.dados_profissionais);
  if (dados.foto) formData.append("foto", dados.foto);
  return request("/api/credenciamento/meu-perfil/", { method: "PATCH", body: formData }, token);
}

// ---------------------------------------------------------------------------
// comunidade/ — campos conferidos em comunidade/serializers.py e views.py
// (run 20260902-1506-comunidade-blog).
// ---------------------------------------------------------------------------

export type TipoPublicacao = "opiniao" | "analise";
export type StatusPublicacao = "rascunho" | "enviado" | "publicado";

export interface Publicacao {
  id: number;
  autor: number;
  autor_nome: string;
  titulo: string;
  conteudo: string;
  tipo: TipoPublicacao;
  status: StatusPublicacao;
  categoria: string;
  tags: string[];
  news_cluster: number | null;
  news_item: number | null;
  destaque: boolean;
  /** FRENTE 4 (Comunidade viva): nº de comentários visíveis (backend anotado; mock local pode omitir). */
  numero_comentarios?: number;
  criado_em: string;
  publicado_em: string | null;
}

export interface Comentario {
  id: number;
  autor: number;
  autor_nome: string;
  conteudo: string;
  publicacao: number | null;
  news_item: number | null;
  resposta_de: number | null;
  criado_em: string;
}

export interface PerfilAutorPublico {
  id: number;
  nome: string;
  credenciado: boolean;
  numero_seguidores: number;
  publicacoes: Publicacao[];
  foto_url?: string | null;
  mini_bio?: string;
}

export function obterPublicacoes(params: {
  destaque?: boolean;
  autor?: number;
  categoria?: string;
  tipo?: string;
  busca?: string;
  ordenar?: "recentes" | "discutidos" | "destaques";
} = {}): Promise<Publicacao[]> {
  const query = new URLSearchParams();
  if (params.destaque) query.set("destaque", "1");
  if (params.autor) query.set("autor", String(params.autor));
  if (params.categoria) query.set("categoria", params.categoria);
  if (params.tipo) query.set("tipo", params.tipo);
  if (params.busca) query.set("busca", params.busca);
  if (params.ordenar) query.set("ordenar", params.ordenar);
  const qs = query.toString();
  return request(`/api/comunidade/publicacoes/${qs ? `?${qs}` : ""}`, { method: "GET" });
}

export async function obterPublicacao(token: string | null, publicacaoId: number): Promise<Publicacao | null> {
  try {
    return await request<Publicacao>(
      `/api/comunidade/publicacoes/${publicacaoId}/`,
      { method: "GET" },
      token || undefined
    );
  } catch (erro) {
    if (erro instanceof ApiError && erro.status === 404) {
      return null;
    }
    throw erro;
  }
}

export function criarRascunhoPublicacao(
  token: string,
  dados: { titulo: string; conteudo: string; tipo: TipoPublicacao; categoria?: string; tags?: string[] }
): Promise<Publicacao> {
  return request("/api/comunidade/publicacoes/", { method: "POST", body: JSON.stringify(dados) }, token);
}

export function enviarPublicacao(token: string, publicacaoId: number): Promise<Publicacao> {
  return request(
    `/api/comunidade/publicacoes/${publicacaoId}/enviar/`,
    { method: "POST" },
    token
  );
}

export function editarPublicacao(
  token: string,
  publicacaoId: number,
  dados: { titulo?: string; conteudo?: string; categoria?: string; tags?: string[] }
): Promise<Publicacao> {
  return request(
    `/api/comunidade/publicacoes/${publicacaoId}/`,
    { method: "PATCH", body: JSON.stringify(dados) },
    token
  );
}

export function excluirPublicacao(token: string, publicacaoId: number): Promise<void> {
  return request(`/api/comunidade/publicacoes/${publicacaoId}/`, { method: "DELETE" }, token);
}

export function obterComentarios(params: {
  publicacao?: number;
  news_item?: number;
}): Promise<Comentario[]> {
  const query = new URLSearchParams();
  if (params.publicacao) query.set("publicacao", String(params.publicacao));
  if (params.news_item) query.set("news_item", String(params.news_item));
  return request(`/api/comunidade/comentarios/?${query.toString()}`, { method: "GET" });
}

export function comentar(
  token: string,
  dados: { conteudo: string; publicacao?: number; news_item?: number; resposta_de?: number }
): Promise<Comentario> {
  return request("/api/comunidade/comentarios/", { method: "POST", body: JSON.stringify(dados) }, token);
}

export function excluirComentario(token: string, comentarioId: number): Promise<void> {
  return request(`/api/comunidade/comentarios/${comentarioId}/`, { method: "DELETE" }, token);
}

export function seguirAutor(token: string, autorId: number): Promise<void> {
  return request(`/api/comunidade/autores/${autorId}/seguir/`, { method: "POST" }, token);
}

export function deixarDeSeguirAutor(token: string, autorId: number): Promise<void> {
  return request(`/api/comunidade/autores/${autorId}/seguir/`, { method: "DELETE" }, token);
}

export function obterPerfilAutor(autorId: number): Promise<PerfilAutorPublico> {
  return request(`/api/comunidade/autores/${autorId}/perfil/`, { method: "GET" });
}

export function denunciar(
  token: string,
  dados: { motivo: string; comentario?: number; publicacao?: number }
): Promise<{ id: number; detail: string }> {
  return request("/api/comunidade/denunciar/", { method: "POST", body: JSON.stringify(dados) }, token);
}

// ---------------------------------------------------------------------------
// moderacao/ — paginas legais/editoriais publicas (Termos de Uso, Politica de
// Privacidade, Politica de Cookies, Politica Editorial — BRD secoes 17/18/25).
// ---------------------------------------------------------------------------

export interface PaginaEditorial {
  slug: string;
  titulo: string;
  conteudo: string;
  atualizado_em: string;
}

export function obterPaginaEditorial(slug: string): Promise<PaginaEditorial> {
  return request(`/api/moderacao/paginas/${slug}/`, { method: "GET" });
}

// ---------------------------------------------------------------------------
// radar/ — campos conferidos em radar/services.py e views.py (run
// 20260902-1513-radar-tendencias-localizacao).
// ---------------------------------------------------------------------------

export interface AssuntoEmAlta {
  categoria: string;
  numero_noticias: number;
  numero_fontes: number;
  cluster_id: number | null;
  item_id: number | null;
  // FRENTE 3 — crescimento 24h, buscas relacionadas e score (mesma lógica
  // da Home). Opcionais para compatibilidade com payloads antigos/cache.
  crescimento_24h?: number;
  buscas_relacionadas?: number;
  score?: number;
}

export interface RadarTendencias {
  aviso_metodologia: string;
  localidade: { pais: string | null; estado: string | null; cidade: string | null };
  assuntos_em_alta: AssuntoEmAlta[];
}

export interface RadarEvolucao {
  aviso_metodologia: string;
  categoria: string | null;
  serie: { dia: string; numero_noticias: number }[];
}

export interface LocalidadeSalva {
  pais: string;
  estado: string;
  cidade: string;
}

export function obterTendenciasRadar(params: {
  pais?: string;
  estado?: string;
  cidade?: string;
}): Promise<RadarTendencias> {
  const query = new URLSearchParams();
  if (params.pais) query.set("pais", params.pais);
  if (params.estado) query.set("estado", params.estado);
  if (params.cidade) query.set("cidade", params.cidade);
  const qs = query.toString();
  return request(`/api/radar/tendencias/${qs ? `?${qs}` : ""}`, { method: "GET" });
}

export function obterEvolucaoRadar(
  token: string,
  params: { categoria?: string; pais?: string; estado?: string; cidade?: string }
): Promise<RadarEvolucao> {
  const query = new URLSearchParams();
  if (params.categoria) query.set("categoria", params.categoria);
  if (params.pais) query.set("pais", params.pais);
  if (params.estado) query.set("estado", params.estado);
  if (params.cidade) query.set("cidade", params.cidade);
  const qs = query.toString();
  return request(`/api/radar/evolucao/${qs ? `?${qs}` : ""}`, { method: "GET" }, token);
}

export function obterLocalidadesSalvas(token: string): Promise<LocalidadeSalva[]> {
  return request("/api/radar/localidades-salvas/", { method: "GET" }, token);
}

export function salvarLocalidade(
  token: string,
  dados: { pais?: string; estado?: string; cidade?: string }
): Promise<{ id: number }> {
  return request(
    "/api/radar/localidades-salvas/",
    { method: "POST", body: JSON.stringify(dados) },
    token
  );
}

export function removerLocalidade(
  token: string,
  dados: { pais?: string; estado?: string; cidade?: string }
): Promise<void> {
  return request(
    "/api/radar/localidades-salvas/",
    { method: "DELETE", body: JSON.stringify(dados) },
    token
  );
}

// ---------------------------------------------------------------------------
// newsletter/ — campos conferidos em newsletter/views.py (run
// 20260902-1515-newsletter).
// ---------------------------------------------------------------------------

export type TipoNewsletter = "padrao" | "categoria" | "personalizada";
export type PeriodoNewsletter = "manha" | "noite";

export function inscreverNewsletter(
  token: string,
  dados: { tipo: TipoNewsletter; categorias?: string[]; periodo?: PeriodoNewsletter }
): Promise<{ tipo: TipoNewsletter; periodo: PeriodoNewsletter; ativa: boolean }> {
  return request("/api/newsletter/inscrever/", { method: "POST", body: JSON.stringify(dados) }, token);
}

export function cancelarNewsletter(token: string): Promise<void> {
  return request("/api/newsletter/inscrever/", { method: "DELETE" }, token);
}

// ---------------------------------------------------------------------------
// landing/ — campos conferidos em landing/serializers.py (run
// 20260902-1517-landing-lista-espera).
// ---------------------------------------------------------------------------

export function inscreverListaEspera(dados: {
  nome: string;
  email: string;
  interesses?: string[];
  localidade?: string;
  canal_preferido?: string;
  aceite_comunicacao: boolean;
}): Promise<{ detail: string }> {
  return request("/api/landing/lista-espera/", { method: "POST", body: JSON.stringify(dados) });
}

// ---------------------------------------------------------------------------
// b2b/ — campos conferidos em b2b/views.py, serializers.py e services.py
// (run 20260902-1519-b2b-corporativo e run 20260902-1600-frontend-b2b-metricas).
// ---------------------------------------------------------------------------

export type TipoCriterioMonitoramento = "empresa" | "concorrente" | "setor" | "palavra_chave";

export interface CriterioMonitoramento {
  id: number;
  tipo: TipoCriterioMonitoramento;
  valor: string;
  ativo: boolean;
  criado_em: string;
}

export interface MembroOrganizacao {
  id: number;
  email: string;
  papel_na_organizacao: "admin_organizacao" | "membro";
  criado_em: string;
}

export interface ItemMonitorado {
  id: number;
  titulo: string;
  url_fonte_original: string;
  nome_fonte: string;
}

export interface ResumoExecutivo {
  organizacao: string;
  criterios: { tipo: TipoCriterioMonitoramento; valor: string; numero_itens: number }[];
}

export function obterCriteriosB2B(token: string): Promise<CriterioMonitoramento[]> {
  return request("/api/b2b/criterios/", { method: "GET" }, token);
}

export function criarCriterioB2B(
  token: string,
  dados: { tipo: TipoCriterioMonitoramento; valor: string }
): Promise<CriterioMonitoramento> {
  return request("/api/b2b/criterios/", { method: "POST", body: JSON.stringify(dados) }, token);
}

export function obterItensMonitoradosB2B(
  token: string
): Promise<Record<string, { criterio: { tipo: string; valor: string }; itens: ItemMonitorado[] }>> {
  return request("/api/b2b/itens-monitorados/", { method: "GET" }, token);
}

export function obterResumoExecutivoB2B(token: string): Promise<ResumoExecutivo> {
  return request("/api/b2b/resumo-executivo/", { method: "GET" }, token);
}

export function obterMembrosB2B(token: string): Promise<MembroOrganizacao[]> {
  return request("/api/b2b/membros/", { method: "GET" }, token);
}

export function convidarMembroB2B(token: string, email: string): Promise<MembroOrganizacao> {
  return request("/api/b2b/membros/", { method: "POST", body: JSON.stringify({ email }) }, token);
}

export function removerMembroB2B(token: string, email: string): Promise<void> {
  return request("/api/b2b/membros/", { method: "DELETE", body: JSON.stringify({ email }) }, token);
}

export function excluirCriterioB2B(token: string, criterioId: number): Promise<void> {
  return request(`/api/b2b/criterios/${criterioId}/`, { method: "DELETE" }, token);
}

// ---------------------------------------------------------------------------
// metricas/ — campos conferidos em metricas/services.py (run
// 20260902-1521-painel-metricas-negocio). Só admin (papel === "admin").
// ---------------------------------------------------------------------------

export interface SeriePonto {
  dia: string;
  total: number;
}
export interface DistribuicaoItem {
  label: string;
  total: number;
}
export interface PainelMetricas {
  periodo_dias: number;
  usuarios_cadastrados_total: number;
  usuarios_cadastrados_periodo: number;
  usuarios_ativos_diarios: number;
  usuarios_ativos_mensais: number;
  retencao_periodo: number;
  assinaturas_ativas: number;
  conversao_free_premium: number;
  receita_recorrente_periodo: string;
  receita_media_por_assinante: string;
  churn_periodo: number;
  taxa_renovacao_periodo: number;
  organizacoes_b2b_ativas: number;
  custo_llm_hoje_usd?: number;
  teto_llm_diario_usd?: number;
  teto_llm_excedido_hoje?: boolean;
  series: Record<string, SeriePonto[]>;
  distribuicoes: Record<string, DistribuicaoItem[]>;
  kpis: {
    comunidade: { publicacoes_total: number; publicacoes_publicadas: number; comentarios_total: number; seguidores_total: number };
    moderacao: { denuncias_pendentes: number; denuncias_total: number; acoes_total: number };
    lista_espera: { total: number };
    newsletter: { ativas: number; total: number };
    b2b: { ativas: number; total: number; criterios_ativos: number };
    ingestao: { noticias_periodo: number; noticias_pendentes: number; taxa_aprovacao: number; custo_periodo: number };
  };
  funil: { lista_espera: number; cadastrados: number; assinantes: number; taxa_lista_para_cadastro: number; taxa_cadastro_para_premium: number };
}

export function obterPainelMetricas(token: string, dias = 30): Promise<PainelMetricas> {
  return request(`/api/metricas/painel/?dias=${dias}`, { method: "GET" }, token);
}

export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}
export interface AdminUsuario {
  id: number;
  email: string;
  nome: string;
  papel: string;
  is_active: boolean;
  email_verificado: boolean;
  date_joined: string;
}
export interface AdminFilaItem {
  tipo: string;
  id: number;
  titulo: string;
  categoria: string;
  status_revisao: string;
  nome_fonte: string;
  url_fonte_original: string;
  urgente: boolean;
  cluster: number | null;
  cluster_titulo: string;
  timestamp_ingestao: string;
}
export interface AdminAssinatura {
  id: number;
  user_email: string;
  user_nome: string;
  plan: Plano;
  status: string;
  preco_cobrado: string;
  criado_em: string;
}

export function adminListarUsuarios(token: string, params: { search?: string; papel?: string; page?: number } = {}): Promise<Paginated<AdminUsuario>> {
  const q = new URLSearchParams();
  if (params.search) q.set("search", params.search);
  if (params.papel) q.set("papel", params.papel);
  if (params.page) q.set("page", String(params.page));
  const qs = q.toString();
  return request(`/api/admin/usuarios/${qs ? `?${qs}` : ""}`, { method: "GET" }, token);
}
export function adminAtualizarUsuario(token: string, id: number, dados: { papel?: string; is_active?: boolean }): Promise<AdminUsuario> {
  return request(`/api/admin/usuarios/${id}/`, { method: "PATCH", body: JSON.stringify(dados) }, token);
}
export function adminListarFila(token: string, params: { status?: string; page?: number } = {}): Promise<Paginated<AdminFilaItem>> {
  const q = new URLSearchParams();
  if (params.status) q.set("status", params.status);
  if (params.page) q.set("page", String(params.page));
  const qs = q.toString();
  return request(`/api/admin/fila/${qs ? `?${qs}` : ""}`, { method: "GET" }, token);
}
export function adminDecidirFila(token: string, id: number, acao: "aprovar" | "rejeitar"): Promise<{ detail: string }> {
  return request(`/api/admin/fila/${id}/decisao/`, { method: "POST", body: JSON.stringify({ acao }) }, token);
}
export function adminListarPlanos(token: string): Promise<Paginated<Plano>> {
  return request("/api/admin/planos/", { method: "GET" }, token);
}
export function adminCriarPlano(token: string, dados: { nome: string; preco: string; duracao_dias: number; ativo?: boolean }): Promise<Plano> {
  return request("/api/admin/planos/", { method: "POST", body: JSON.stringify(dados) }, token);
}
export function adminAtualizarPlano(token: string, id: number, dados: Record<string, unknown>): Promise<Plano> {
  return request(`/api/admin/planos/${id}/`, { method: "PATCH", body: JSON.stringify(dados) }, token);
}

export function adminExcluirPlano(token: string, id: number): Promise<void> {
  return request(`/api/admin/planos/${id}/`, { method: "DELETE" }, token);
}
export function adminListarLimites(token: string): Promise<Paginated<{ id: number; chave: string; plano: string; valor: string; descricao: string }>> {
  return request("/api/admin/limites/", { method: "GET" }, token);
}
export function adminAtualizarLimite(token: string, id: number, dados: { valor: string; descricao?: string }): Promise<{ id: number; chave: string; plano: string; valor: string }> {
  return request(`/api/admin/limites/${id}/`, { method: "PATCH", body: JSON.stringify(dados) }, token);
}
export function adminListarAssinaturas(token: string, params: { status?: string; search?: string; page?: number } = {}): Promise<Paginated<AdminAssinatura>> {
  const q = new URLSearchParams();
  if (params.status) q.set("status", params.status);
  if (params.search) q.set("search", params.search);
  if (params.page) q.set("page", String(params.page));
  const qs = q.toString();
  return request(`/api/admin/assinaturas/${qs ? `?${qs}` : ""}`, { method: "GET" }, token);
}
export function adminObterAssinatura(token: string, id: number): Promise<AdminAssinatura & { pagamentos: { id: number; valor: string; status: string; criado_em: string }[] }> {
  return request(`/api/admin/assinaturas/${id}/`, { method: "GET" }, token);
}
export function adminListarDenuncias(token: string, params: { status?: string; page?: number } = {}): Promise<Paginated<{ id: number; motivo: string; detalhe: string; status: string; denunciante_email: string; criado_em: string; alvo_repr: string | null }>> {
  const q = new URLSearchParams();
  if (params.status) q.set("status", params.status);
  if (params.page) q.set("page", String(params.page));
  const qs = q.toString();
  return request(`/api/admin/moderacao/denuncias/${qs ? `?${qs}` : ""}`, { method: "GET" }, token);
}
export function adminAplicarAcaoDenuncia(token: string, id: number, dados: { tipo: string; motivo: string; procedente?: boolean }): Promise<{ detail: string }> {
  return request(`/api/admin/moderacao/denuncias/${id}/acao/`, { method: "POST", body: JSON.stringify(dados) }, token);
}

export interface FonteRobo { id: number; nome: string; url: string; ativo: boolean; categoria_padrao: string; criado_em: string; atualizado_em: string }
export interface ConfigRobo {
  intervalo_minutos: number; ativo: boolean; categorias_sensiveis: string; limiar_fontes_alta_relevancia: number;
  dedup_limiar_similaridade: number; dedup_janela_horas: number; dedup_max_itens: number;
  resumo_similaridade_maxima: number; resumo_trecho_copiado_maximo: number; dedup_cluster_sempre_exige_revisao: boolean;
  llm_model: string; llm_api_base_url: string; llm_tamanho_lote: number; llm_max_tokens_por_item: number;
  llm_teto_gasto_diario_usd: number; llm_preco_por_1k_tokens: number; llm_timeout_segundos: number; atualizado_em: string;
}
export interface ExecucaoRobo {
  id: number; executado_em: string; itens_por_fonte: Record<string, number>; erros_por_fonte: Record<string, string>;
  total_itens_ingeridos: number; total_grupos_formados: number; total_duplicatas_agrupadas: number;
  chamadas_summarization_provider: number; tokens_utilizados_summarization: number | null; custo_estimado_summarization_usd: number | null;
}
export function robosListarFontes(token: string): Promise<FonteRobo[]> { return request("/api/admin/robos/fontes/", { method: "GET" }, token); }
export function robosCriarFonte(token: string, dados: { nome: string; url: string; ativo?: boolean; categoria_padrao?: string }): Promise<FonteRobo> {
  return request("/api/admin/robos/fontes/", { method: "POST", body: JSON.stringify(dados) }, token);
}
export function robosAtualizarFonte(token: string, id: number, dados: Partial<FonteRobo>): Promise<FonteRobo> {
  return request(`/api/admin/robos/fontes/${id}/`, { method: "PATCH", body: JSON.stringify(dados) }, token);
}
export function robosRemoverFonte(token: string, id: number): Promise<void> { return request(`/api/admin/robos/fontes/${id}/`, { method: "DELETE" }, token); }
export function robosObterConfig(token: string): Promise<ConfigRobo> { return request("/api/admin/robos/config/", { method: "GET" }, token); }
export function robosSalvarConfig(token: string, dados: Partial<ConfigRobo>): Promise<ConfigRobo> {
  return request("/api/admin/robos/config/", { method: "PATCH", body: JSON.stringify(dados) }, token);
}
export function robosListarExecucoes(token: string): Promise<ExecucaoRobo[]> { return request("/api/admin/robos/execucoes/", { method: "GET" }, token); }
export function robosExecutar(token: string): Promise<ExecucaoRobo> { return request("/api/admin/robos/executar/", { method: "POST" }, token); }

// ---------------------------------------------------------------------------
// gating/sistema — flag Premium (fail-open: desligada = tudo liberado).
// ---------------------------------------------------------------------------

export interface StatusSistema {
  premium_ativo: boolean;
}

export function obterStatusSistema(): Promise<StatusSistema> {
  return request("/api/gating/status/", { method: "GET" });
}

export function obterConfigSistemaAdmin(
  token: string
): Promise<StatusSistema & { atualizado_em: string }> {
  return request("/api/admin/sistema/", { method: "GET" }, token);
}

export function atualizarConfigSistemaAdmin(
  token: string,
  dados: { premium_ativo: boolean }
): Promise<StatusSistema & { atualizado_em: string }> {
  return request(
    "/api/admin/sistema/",
    { method: "PATCH", body: JSON.stringify(dados) },
    token
  );
}

// ---------------------------------------------------------------------------
// FRENTE 6 — Central de Inteligência (métricas comportamentais + overrides).
// Só admin. Tipos espelham `metricas/services_inteligencia.py` e
// `painel_admin` (DestaqueEditorial / RegraCuradoria).
// ---------------------------------------------------------------------------

export type PeriodoInteligencia = "hoje" | "ontem" | "7d" | "30d" | "90d" | "custom";

export interface RotuloTotal {
  label: string;
  total: number;
}

export interface RankingNoticia {
  tipo: string;
  id: number;
  titulo: string;
  categoria: string;
  total: number;
}

export interface InsightEditorial {
  tipo: string;
  titulo: string;
  detalhe: string;
  base: Record<string, unknown>;
}

export interface CentralInteligencia {
  periodo: { chave: string; inicio: string; fim: string; dias: number };
  audiencia: {
    visitas: number;
    sessoes: number;
    usuarios_novos: number;
    sessoes_recorrentes: number;
    usuarios_recorrentes: number;
    taxa_retorno_pct: number;
    views_por_noticia: number;
    noticias_distintas_com_view: number;
    tempo_medio_leitura_seg: number;
    leituras_com_tempo: number;
    tempo_medio_pagina_seg: number;
    top_entradas: RotuloTotal[];
    top_saidas: RotuloTotal[];
  };
  trafego: { origens: RotuloTotal[]; dispositivos: RotuloTotal[] };
  conteudo: {
    mais_acessadas: RankingNoticia[];
    mais_clicadas: RankingNoticia[];
    mais_pesquisadas: { termo: string; total: number }[];
    buscas_sem_resultado: number;
    mais_compartilhadas: RankingNoticia[];
    mais_salvas: RankingNoticia[];
    maior_tempo_medio: { tipo: string; id: number; titulo: string; categoria: string; media_seg: number; leituras: number }[];
    categorias_top: RotuloTotal[];
    autores_top: RotuloTotal[];
    autores_sem_dados: boolean;
    colunistas_top: RotuloTotal[];
    urgentes_top: RankingNoticia[];
  };
  comportamento: {
    views_noticia: number;
    cliques_noticia: number;
    shares: number;
    salvos: number;
    scroll_medio_pct: number;
    buscas_total: number;
    termos_top: { termo: string; total: number }[];
    top_paths: RotuloTotal[];
    home: { views: number; cliques: number; por_secao: RotuloTotal[] };
    radar_views: number;
    comunidade: { views: number; interacoes: number };
    categorias_navegadas: RotuloTotal[];
    autores_vistos: RotuloTotal[];
  };
  localizacao: {
    nota: string;
    paises: RotuloTotal[];
    estados: RotuloTotal[];
    cidades: RotuloTotal[];
    regioes: RotuloTotal[];
    localidades_salvas_total: number;
  };
  series: Record<string, { dia: string; total: number }[]>;
  comparativo: Record<string, { atual: number; anterior: number; delta_pct: number | null } & Record<string, unknown>>;
  inteligencia: { sem_dados: boolean; mensagem?: string; total?: number; itens?: InsightEditorial[] };
}

export function obterCentralInteligencia(
  token: string,
  params: { periodo?: PeriodoInteligencia; inicio?: string; fim?: string } = {}
): Promise<CentralInteligencia> {
  const q = new URLSearchParams();
  if (params.periodo) q.set("periodo", params.periodo);
  if (params.inicio) q.set("inicio", params.inicio);
  if (params.fim) q.set("fim", params.fim);
  const qs = q.toString();
  return request(`/api/metricas/inteligencia/${qs ? `?${qs}` : ""}`, { method: "GET" }, token);
}

export interface DestaqueEditorial {
  id: number;
  tipo: "destaque" | "manchete" | "bloqueio";
  entry_tipo: "item" | "cluster";
  entry_id: number;
  titulo: string;
  posicao: number;
  ativo: boolean;
  inicio: string | null;
  fim: string | null;
  motivo: string;
  vigente?: boolean;
  criado_em?: string;
}

export interface RegraCuradoria {
  id: number;
  tipo: string;
  entry_tipo: string;
  entry_id: number | null;
  alvo: string;
  ordem: number;
  ativo: boolean;
  inicio: string | null;
  fim: string | null;
  motivo: string;
  vigente?: boolean;
  criado_em?: string;
}

export function adminListarDestaques(token: string, tipo?: string): Promise<DestaqueEditorial[]> {
  return request(`/api/admin/editoriais/${tipo ? `?tipo=${tipo}` : ""}`, { method: "GET" }, token);
}

export function adminCriarDestaque(
  token: string,
  dados: { tipo: string; entry_tipo: string; entry_id: number; posicao?: number; motivo?: string }
): Promise<DestaqueEditorial> {
  return request("/api/admin/editoriais/", { method: "POST", body: JSON.stringify(dados) }, token);
}

export function adminAtualizarDestaque(token: string, id: number, dados: Record<string, unknown>): Promise<DestaqueEditorial> {
  return request(`/api/admin/editoriais/${id}/`, { method: "PATCH", body: JSON.stringify(dados) }, token);
}

export function adminExcluirDestaque(token: string, id: number): Promise<void> {
  return request(`/api/admin/editoriais/${id}/`, { method: "DELETE" }, token);
}

export function adminListarRegras(token: string, tipo?: string): Promise<RegraCuradoria[]> {
  return request(`/api/admin/regras/${tipo ? `?tipo=${tipo}` : ""}`, { method: "GET" }, token);
}

export function adminCriarRegra(
  token: string,
  dados: { tipo: string; entry_tipo?: string; entry_id?: number; alvo?: string; ordem?: number; motivo?: string }
): Promise<RegraCuradoria> {
  return request("/api/admin/regras/", { method: "POST", body: JSON.stringify(dados) }, token);
}

export function adminAtualizarRegra(token: string, id: number, dados: Record<string, unknown>): Promise<RegraCuradoria> {
  return request(`/api/admin/regras/${id}/`, { method: "PATCH", body: JSON.stringify(dados) }, token);
}

export function adminExcluirRegra(token: string, id: number): Promise<void> {
  return request(`/api/admin/regras/${id}/`, { method: "DELETE" }, token);
}
