/**
 * Consentimento de cookies (implementation-contract.md run
 * 20260903-1134-seo-lgpd-design-system, escopo B — LGPD; estendido pela run
 * 20260925-1020-observabilidade com a categoria de diagnóstico técnico).
 *
 * Categorias:
 * - "essenciais": sempre ativa, nunca é uma escolha do usuário (necessária
 *   para o site funcionar — ex.: token de sessão, tema, o próprio registro
 *   de consentimento). Não é armazenada como escolha porque não é opcional.
 * - "analytics" / "personalizacao": só carregam/gravam algo depois de
 *   consentimento explícito — nenhum código deste projeto pode inicializar
 *   um script dessas categorias sem antes checar `permiteCategoria`.
 * - "tecnico": telemetria de DIAGNÓSTICO (erros de runtime, Web Vitals,
 *   identifier de requisição). É deliberadamente distinta de analytics e de
 *   personalização: não mede audiência, não mede comportamento de leitura e não
 *   é carregada junto com elas. O que a porta faz é enviar
 *   `X-Technical-Consent: 1` nas chamadas de API (critérios 5, 6 e 27) — sem
 *   esse header o backend descarta QUALQUER evento técnico (fail-closed).
 *
 * Persistência: localStorage para QUALQUER visitante (anônimo ou logado) —
 * é a fonte da verdade imediata no navegador, funciona antes mesmo de saber
 * se há sessão. Se o usuário estiver autenticado, a escolha é replicada
 * também no backend (`api.atualizarPreferenciasCookies`) — ver
 * `sincronizarComBackendSeAutenticado` — para sobreviver a troca de
 * dispositivo/navegador; a leitura, porém, sempre parte do localStorage
 * local (evita depender de uma chamada de rede para decidir se pode
 * carregar um script no primeiro paint).
 *
 * LIMITE CONHECIDO (run 20260925-1020-observabilidade): o endpoint de
 * preferências do backend (`PreferenciasCookiesSerializer` em
 * `backend/identidade/serializers.py`) aceita e devolve apenas `analytics` e
 * `personalizacao`. Como o backend está fora do escopo deste bloco, a categoria
 * `tecnico` NÃO é enviada na sincronização e volta como `false` ao importar de
 * outro dispositivo — fail-closed, e registrado como follow-up.
 */

import * as api from "./api";
import { CHAVE_CONSENTIMENTO, consentimentoTecnicoConcedido } from "./consento-local";

export type CategoriaOpcional = "analytics" | "personalizacao" | "tecnico";

export interface EscolhasCookies {
  analytics: boolean;
  personalizacao: boolean;
  tecnico: boolean;
}

export interface ConsentimentoCookies {
  versao: 2;
  escolhas: EscolhasCookies;
  respondidoEm: string;
}

/** Versão do formato persistido (1 = analytics + personalização). */
export const VERSAO_CONSENTIMENTO = 2;

export const EVENTO_CONSENTIMENTO_ALTERADO = "portal_noticias:consentimento-cookies-alterado";

/** Campos que o backend de preferências realmente aceita. */
const CAMPOS_SINCRONIZAVEIS = ["analytics", "personalizacao"] as const;

function emitirEventoAlteracao(): void {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent(EVENTO_CONSENTIMENTO_ALTERADO));
}

/**
 * Normaliza um registro lido do armazenamento. `versao: 1` (anterior a esta
 * run) não conhece a categoria técnica: ela entra como `false` — o usuário
 * precisa consentir de novo, em vez de ter o diagnóstico ligado por omissão de
 * quem apagou o dado.
 */
function normalizarRegistro(dados: unknown): ConsentimentoCookies | null {
  if (!dados || typeof dados !== "object") return null;
  const objeto = dados as Record<string, unknown>;
  if (!("escolhas" in objeto) || !("respondidoEm" in objeto)) return null;
  const escolhas = objeto.escolhas;
  if (!escolhas || typeof escolhas !== "object") return null;
  const bruto = escolhas as Record<string, unknown>;
  return {
    versao: VERSAO_CONSENTIMENTO,
    respondidoEm: typeof objeto.respondidoEm === "string" ? objeto.respondidoEm : "",
    escolhas: {
      analytics: bruto.analytics === true,
      personalizacao: bruto.personalizacao === true,
      tecnico: bruto.tecnico === true,
    },
  };
}

/** Lê a escolha salva, ou `null` se o visitante ainda não respondeu. */
export function obterConsentimento(): ConsentimentoCookies | null {
  if (typeof window === "undefined") return null;
  try {
    const bruto = window.localStorage.getItem(CHAVE_CONSENTIMENTO);
    if (!bruto) return null;
    return normalizarRegistro(JSON.parse(bruto) as unknown);
  } catch {
    return null;
  }
}

export function consentimentoRespondido(): boolean {
  return obterConsentimento() !== null;
}

/**
 * Categoria "essenciais" nunca passa por aqui (sempre permitida, ver
 * cabeçalho do arquivo) — só use esta função para as opcionais. Sem resposta
 * registrada ainda, o padrão é NEGAR (critério de aceite 3: nenhum cookie não
 * essencial antes do consentimento explícito).
 */
export function permiteCategoria(categoria: CategoriaOpcional): boolean {
  const consentimento = obterConsentimento();
  if (!consentimento) return false;
  return Boolean(consentimento.escolhas[categoria]);
}

/** Mesma política de `permiteCategoria`, sem alocar o registro inteiro. */
export function consentimentoTecnico(): boolean {
  return consentimentoTecnicoConcedido();
}

function salvar(escolhas: EscolhasCookies): void {
  const registro: ConsentimentoCookies = {
    versao: VERSAO_CONSENTIMENTO,
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
  salvar({ analytics: true, personalizacao: true, tecnico: true });
}

export function recusarNaoEssenciais(): void {
  salvar({ analytics: false, personalizacao: false, tecnico: false });
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
  // Só o que o backend aceita hoje (ver Limite conhecido no cabeçalho): enviar
  // `tecnico` seria ignorado em silêncio e criaria a impressão de que houve
  // sincronização do que não foi sincronizado.
  const sincronizaveis: Partial<EscolhasCookies> = {};
  for (const campo of CAMPOS_SINCRONIZAVEIS) {
    sincronizaveis[campo] = consentimento.escolhas[campo];
  }
  try {
    await api.atualizarPreferenciasCookies(token, {
      analytics: Boolean(sincronizaveis.analytics),
      personalizacao: Boolean(sincronizaveis.personalizacao),
    });
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
      // A categoria técnica NÃO vem do backend (Limite conhecido): fail-closed,
      // o visitante decide de novo aqui.
      salvar({
        analytics: preferencias.analytics,
        personalizacao: preferencias.personalizacao,
        tecnico: false,
      });
    }
  } catch {
    // sem preferência registrada no backend ainda — segue mostrando o banner.
  }
}

export { CHAVE_CONSENTIMENTO };
