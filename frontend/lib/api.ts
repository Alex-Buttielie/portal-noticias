/**
 * Cliente de API central (implementation-contract.md run
 * 20260902-1448-frontend-mvp-web) — todas as chamadas ao backend Django
 * passam por aqui. Nomes de campo em português, espelhando exatamente os
 * serializers do backend (identidade/serializers.py, feed/serializers.py,
 * assinatura/serializers.py) — conferidos por leitura direta desses
 * arquivos antes de escrever este cliente, não adivinhados.
 */

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

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
    if (typeof objeto.detail === "string") {
      return objeto.detail;
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
  } catch {
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
}): Promise<FeedResposta> {
  const query = new URLSearchParams();
  if (params.categoria) query.set("categoria", params.categoria);
  if (params.busca) query.set("busca", params.busca);
  if (params.page) query.set("page", String(params.page));
  const qs = query.toString();
  return request(`/api/feed/${qs ? `?${qs}` : ""}`, { method: "GET" });
}

export interface FonteDetalhe {
  nome_fonte: string;
  url_fonte_original: string;
  resumo: string;
}

export interface FeedDetalhe {
  tipo: "cluster" | "item";
  id: number;
  titulo: string;
  categoria: string;
  urgente: boolean;
  timestamp: string;
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
// assinatura/
// ---------------------------------------------------------------------------

export interface Plano {
  id: number;
  nome: string;
  preco: string;
  duracao_dias: number;
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
  autor_email: string;
  titulo: string;
  conteudo: string;
  tipo: TipoPublicacao;
  status: StatusPublicacao;
  categoria: string;
  tags: string[];
  news_cluster: number | null;
  news_item: number | null;
  destaque: boolean;
  criado_em: string;
  publicado_em: string | null;
}

export interface Comentario {
  id: number;
  autor: number;
  autor_email: string;
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
}

export function obterPublicacoes(params: { destaque?: boolean; autor?: number } = {}): Promise<Publicacao[]> {
  const query = new URLSearchParams();
  if (params.destaque) query.set("destaque", "1");
  if (params.autor) query.set("autor", String(params.autor));
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

// ---------------------------------------------------------------------------
// metricas/ — campos conferidos em metricas/services.py (run
// 20260902-1521-painel-metricas-negocio). Só admin (papel === "admin").
// ---------------------------------------------------------------------------

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
}

export function obterPainelMetricas(token: string, dias = 30): Promise<PainelMetricas> {
  return request(`/api/metricas/painel/?dias=${dias}`, { method: "GET" }, token);
}
