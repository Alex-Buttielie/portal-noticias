/**
 * Consentimento de cookies (implementation-contract.md run
 * 20260903-1134-seo-lgpd-design-system, escopo B — LGPD).
 *
 * Categorias:
 * - "essenciais": sempre ativa, nunca é uma escolha do usuário (necessária
 *   para o site funcionar — ex.: token de sessão, tema, o próprio registro
 *   de consentimento). Não é armazenada como escolha porque não é opcional.
 * - "analytics" / "personalizacao": só carregam/gravam algo depois de
 *   consentimento explícito — nenhum código deste projeto pode inicializar
 *   um script dessas categorias sem antes checar `permiteCategoria`.
 *
 * Persistência: localStorage para QUALQUER visitante (anônimo ou logado) —
 * é a fonte da verdade imediata no navegador, funciona antes mesmo de saber
 * se há sessão. Se o usuário estiver autenticado, a escolha é replicada
 * também no backend (`api.atualizarPreferenciasCookies`) — ver
 * `sincronizarComBackendSeAutenticado` — para sobreviver a troca de
 * dispositivo/navegador; a leitura, porém, sempre parte do localStorage
 * local (evita depender de uma chamada de rede para decidir se pode
 * carregar um script no primeiro paint).
 */

import * as api from "./api";

export type CategoriaOpcional = "analytics" | "personalizacao";

export interface EscolhasCookies {
  analytics: boolean;
  personalizacao: boolean;
}

export interface ConsentimentoCookies {
  versao: 1;
  escolhas: EscolhasCookies;
  respondidoEm: string;
}

const CHAVE_CONSENTIMENTO = "portal_noticias_consentimento_cookies";
export const EVENTO_CONSENTIMENTO_ALTERADO = "portal_noticias:consentimento-cookies-alterado";

function emitirEventoAlteracao(): void {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent(EVENTO_CONSENTIMENTO_ALTERADO));
}

/** Lê a escolha salva, ou `null` se o visitante ainda não respondeu. */
export function obterConsentimento(): ConsentimentoCookies | null {
  if (typeof window === "undefined") return null;
  try {
    const bruto = window.localStorage.getItem(CHAVE_CONSENTIMENTO);
    if (!bruto) return null;
    const dados = JSON.parse(bruto) as unknown;
    if (
      dados &&
      typeof dados === "object" &&
      "escolhas" in dados &&
      "respondidoEm" in dados
    ) {
      return dados as ConsentimentoCookies;
    }
    return null;
  } catch {
    return null;
  }
}

export function consentimentoRespondido(): boolean {
  return obterConsentimento() !== null;
}

/**
 * Categoria "essenciais" nunca passa por aqui (sempre permitida, ver
 * cabeçalho do arquivo) — só use esta função para "analytics"/"personalizacao".
 * Sem resposta registrada ainda, o padrão é NEGAR (critério de aceite 3:
 * nenhum cookie não essencial antes do consentimento explícito).
 */
export function permiteCategoria(categoria: CategoriaOpcional): boolean {
  const consentimento = obterConsentimento();
  if (!consentimento) return false;
  return Boolean(consentimento.escolhas[categoria]);
}

function salvar(escolhas: EscolhasCookies): void {
  const registro: ConsentimentoCookies = {
    versao: 1,
    escolhas,
    respondidoEm: new Date().toISOString(),
  };
  try {
    window.localStorage.setItem(CHAVE_CONSENTIMENTO, JSON.stringify(registro));
  } catch {
    // localStorage indisponível (ex.: modo privado) — a escolha vale só
    // para esta sessão em memória; o banner reaparecerá na próxima visita.
  }
  emitirEventoAlteracao();
}

export function definirEscolhas(escolhas: EscolhasCookies): void {
  salvar(escolhas);
}

export function aceitarTodos(): void {
  salvar({ analytics: true, personalizacao: true });
}

export function recusarNaoEssenciais(): void {
  salvar({ analytics: false, personalizacao: false });
}

/**
 * Replica a escolha no backend quando há usuário autenticado — falha
 * silenciosamente (a fonte da verdade imediata é o localStorage; não vale a
 * pena incomodar o usuário com um erro por causa de uma réplica best-effort).
 */
export async function sincronizarComBackendSeAutenticado(token: string | null): Promise<void> {
  if (!token) return;
  const consentimento = obterConsentimento();
  if (!consentimento) return;
  try {
    await api.atualizarPreferenciasCookies(token, consentimento.escolhas);
  } catch {
    // best-effort — ver comentário acima.
  }
}

/**
 * Ao logar em um dispositivo novo (sem escolha local ainda salva), traz a
 * preferência já registrada no backend, se houver, para o localStorage —
 * evita reexibir o banner para quem já decidiu antes em outro dispositivo.
 */
export async function importarPreferenciasDoBackendSeNecessario(token: string | null): Promise<void> {
  if (!token || consentimentoRespondido()) return;
  try {
    const preferencias = await api.obterPreferenciasCookies(token);
    if (preferencias.atualizado_em) {
      salvar({ analytics: preferencias.analytics, personalizacao: preferencias.personalizacao });
    }
  } catch {
    // sem preferência registrada no backend ainda — segue mostrando o banner.
  }
}
