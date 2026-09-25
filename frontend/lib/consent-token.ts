/**
 * Cliente do token de consentimento assinado de analytics (run
 * 20260925-1020-observabilidade, critérios 25 e 26) — **fecha uma pendência
 * que o backend deixou aberta**.
 *
 * Situação herdada do Bloco A2: `POST /api/metricas/eventos/` passou a exigir
 * um token assinado (`backend/metricas/consent.py`) e a INGESTÃO DE ANALYTICS
 * ESTÁ PARADA, porque nenhum cliente emite o token. Cada evento é recusado com
 * `consent_ausente` e não vira dado de produto. Não há como contornar isso sem
 * token: desligar a exigência no cliente seria exatamente o controle decorativo
 * que o Bloco A2 removeu.
 *
 * ## O que este módulo NÃO faz (e por quê)
 *
 * - **Não assina nada.** A chave HMAC é do backend. O envelope é
 *   `v1.<payload_b64url>.<assinatura_b64url>`; o cliente trata o token como
 *   uma **string opaca**.
 * - **Não decodifica o payload.** O `exp` de que precisamos vem no corpo da
 *   resposta do emissor (`{token, categoria, sub, exp, ttl_segundos}`), não de
 *   "decodificar sem verificar". Um cliente que decodifica o token está a um
 *   passo de achar que pode validá-lo, e não pode: sem a chave, a assinatura é
 *   indetectável. Quem verifica é o backend, sempre.
 * - **Não guarda o token em `localStorage`.** Ele fica em `sessionStorage` e só
 *   vale para a sessão que o pediu, porque a claim `sub` do token é a sessão e
 *   o backend rejeita (`sujeito_invalido`) um token reaproveitado em outra.
 *
 * ## Fail-closed
 *
 * `tokenParaEnvio()` devolve `null` sempre que não há token válido. O evento é
 * descartado. Nunca há envio "para tentar", nunca há flag que force envio sem
 * token.
 */

import { pedirTokenConsentimento, type RespostaTokenConsentimento } from "./api";
import { permiteCategoria } from "./cookie-consent";
import { EVENTO_CONSENTIMENTO_ALTERADO } from "./cookie-consent";

/**
 * Categoria emitida. O backend só emite `analytics` — o token técnico não
 * existe (`backend/metricas/views.py::ConsentimentoTokenView` recusa outra
 * categoria com `categoria_invalida`), e o consentimento técnico viaja pelo
 * header `X-Technical-Consent`, por um caminho separado.
 */
export const CATEGORIA_TOKEN = "analytics";

/** Versão do envelope, espelhando `VERSAO_TOKEN` do backend. */
export const VERSAO_ENVELOPE = "v1";

/**
 * `sessionStorage`, não `localStorage`: o token é amarrado à sessão (claim
 * `sub`) e a sessão já vive em `sessionStorage` (`lib/analytics.ts`), então
 * guardar o token por mais tempo do que a sessão seria manter um segredo
 * vivo sem nenhum uso.
 */
const CHAVE_ARMAZENAMENTO = "portal_noticias_consent_token_analytics";

/**
 * Janela de renovação antecipada, em segundos.
 *
 * O backend emite com TTL de 24 h (`ANALYTICS_CONSENT_TTL_SECONDS`), mas
 * renovar antes não custaria nada: o token é reemitido quando o `exp` está
 * a menos de `5 min` de expirar, e o `track()` só chama isto depois de ter
 * **usado** o token pendente. Assim a renovação acontece em uso real, sem
 * polling nem timer de fundo (restrição de performance do contrato), e a
 * troca de chave de assinatura — a revogação de que a run precisa — tem
 * janelas de troca de até 5 min, não de 24 h.
 */
export const JANELA_RENOVACAO_SEGUNDOS = 300;

/** Mesmo teto do backend (`MAX_TOKEN_BYTES`): o que passar disso é bug. */
export const MAX_TOKEN_BYTES = 2048;

/** Registro do token em mãos. É cache de transporte, não registro de consentimento. */
export interface TokenEmMaos {
  token: string;
  /** Epoch em SEGUNDOS, exatamente como o emissor devolveu. */
  exp: number;
  sub: string;
  /** Epoch em segundos do momento em que foi guardado (para diagnóstico). */
  guardadoEm: number;
}

/** Relógio injetável — o módulo é testável sem `vi.useFakeTimers` e sem `Date` global. */
export type Relogio = () => number;

/**
 * Valida a resposta do emissor antes de qualquer uso.
 *
 * Rejeita formato, categoria, sujeito e `exp` fora de faixa. Um token
 * estruturalmente errado aqui é um bug de integração; deixá-lo passar só
 * transforma a recusa em um 202 do tipo `consent_malformado` no evento, muito
 * mais difícil de diagnosticar do que uma falha no cliente.
 */
export function validarRespostaEmissor(
  resposta: unknown,
  sessao: string,
  agora: number
): TokenEmMaos | null {
  if (!resposta || typeof resposta !== "object") return null;
  const dados = resposta as Partial<RespostaTokenConsentimento>;
  if (typeof dados.token !== "string" || !dados.token) return null;
  if (dados.token.length > MAX_TOKEN_BYTES) return null;
  // Envelope `v1.<payload>.<assinatura>`: três partes, sem espaço, na versão
  // que o backend valida (`VERSAO_TOKEN` em `metricas/consent.py`). Não
  // attemptamos decodificar, mas um envelope de outra versão não veio do
  // emissor — e reprovar aqui evita um `consent_malformado` em produção, que é
  // bem mais difícil de diagnosticar do que uma falha no cliente.
  if (dados.token.trim() !== dados.token) return null;
  const partes = dados.token.split(".");
  if (partes.length !== 3) return null;
  if (partes[0] !== VERSAO_ENVELOPE) return null;
  if (!partes.every((parte) => parte.length > 0)) return null;
  if (dados.categoria !== CATEGORIA_TOKEN) return null;
  if (dados.sub !== sessao) return null;
  if (typeof dados.exp !== "number" || !Number.isFinite(dados.exp)) return null;
  // `exp` tem que estar no futuro. Tolerância zero: o backend já tem o seu
  // próprio skew (`CLOCK_SKEW_SECONDS`), e um token que chega expirado aqui
  // significa relógio muito fora ou resposta em cache.
  if (dados.exp <= agora) return null;
  return { token: dados.token, exp: dados.exp, sub: dados.sub, guardadoEm: agora };
}

/**
 * `true` quando o token em mãos ainda serve para enviar.
 *
 * A janela de renovação NÃO impede o uso: o backend aceita enquanto `exp > agora`,
 * então um token dentro da janela ainda é válido e o evento **é** enviado. A
 * janela só dispara a reemissão em paralelo. Descartar um token ainda válido
 * por estar "perto de expirar" perderia dado de produto sem ganho nenhum.
 */
export function tokenUtilizavel(
  registro: TokenEmMaos | null | undefined,
  agora: number,
  janela = JANELA_RENOVACAO_SEGUNDOS
): boolean {
  if (!registro) return false;
  if (typeof registro.token !== "string" || !registro.token) return false;
  return registro.exp > agora;
}

/** `true` quando o token ainda serve, mas já está dentro da janela de renovação. */
export function precisaRenovar(
  registro: TokenEmMaos | null | undefined,
  agora: number,
  janela = JANELA_RENOVACAO_SEGUNDOS
): boolean {
  if (!tokenUtilizavel(registro, agora, janela)) return true;
  return (registro as TokenEmMaos).exp - agora <= janela;
}

/** Estado em memória por sessão; o `sessionStorage` é a persistência. */
const EM_MEMORIA = new Map<string, TokenEmMaos>();

/** Sessões que já tiveram token em mãos — usado para revogação em massa. */
const SESSOES_COM_TOKEN = new Set<string>();

let ESCUTANDO = false;

function lerArmazenado(sessao: string): TokenEmMaos | null {
  if (typeof window === "undefined") return null;
  try {
    const bruto = window.sessionStorage.getItem(`${CHAVE_ARMAZENAMENTO}:${sessao}`);
    if (!bruto) return null;
    const dados = JSON.parse(bruto) as Partial<TokenEmMaos>;
    if (typeof dados?.token !== "string" || typeof dados?.exp !== "number") return null;
    if (dados.sub !== sessao) return null;
    return { token: dados.token, exp: dados.exp, sub: dados.sub, guardadoEm: dados.guardadoEm ?? 0 };
  } catch {
    // sessionStorage bloqueado (modo privado): o cache em memória ainda vale.
    return null;
  }
}

function gravarArmazenado(sessao: string, registro: TokenEmMaos): void {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.setItem(
      `${CHAVE_ARMAZENAMENTO}:${sessao}`,
      JSON.stringify(registro)
    );
  } catch {
    // quota/negado: a memória já tem o token para esta aba.
  }
}

function apagarArmazenado(sessao: string): void {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.removeItem(`${CHAVE_ARMAZENAMENTO}:${sessao}`);
  } catch {
    // idem
  }
}

/** Token em mãos para a sessão, ou `null`. Não emite nada, não vai à rede. */
export function tokenEmMaos(sessao: string): TokenEmMaos | null {
  if (!sessao) return null;
  const memoria = EM_MEMORIA.get(sessao);
  if (memoria) return memoria;
  const armazenado = lerArmazenado(sessao);
  if (armazenado) EM_MEMORIA.set(sessao, armazenado);
  return armazenado;
}

/** Esquece o token da sessão (consentimento revogado, ou sessão encerrada). */
export function esquecerToken(sessao: string): void {
  if (!sessao) return;
  EM_MEMORIA.delete(sessao);
  SESSOES_COM_TOKEN.delete(sessao);
  apagarArmazenado(sessao);
}

/** Emissão em voo por sessão, para não pedir N tokens para N eventos. */
const EM_VOO = new Map<string, Promise<TokenEmMaos | null>>();

/**
 * Devolve um token utilizável para a sessão, emitindo um novo só se for
 * necessário (primeira vez ou dentro da janela de renovação).
 *
 * `null` = fail-closed. O evento não é enviado. Não há caminho que produza um
 * evento sem token.
 */
export async function garantirToken(
  sessao: string,
  opcoes: { agora?: number } = {}
): Promise<string | null> {
  if (!sessao) return null;
  // Fail-closed na origem: sem consentimento de analytics não há token. O
  // emissor é público e rate-limitado; pedir token sem gesto seria pedir
  // prova de um consentimento que não existe.
  if (!permiteCategoria("analytics")) return null;

  const agora = (opcoes.agora ?? Math.floor(Date.now() / 1000)) as number;
  const emMaos = tokenEmMaos(sessao);
  if (tokenUtilizavel(emMaos, agora)) {
    // Token válido. Se já está na janela de renovação, dispara a reemissão em
    // paralelo — o evento segue com o token atual, que ainda é aceito.
    if (precisaRenovar(emMaos, agora)) void renovarToken(sessao);
    return (emMaos as TokenEmMaos).token;
  }

  const registro = await emitir(sessao, agora);
  return registro ? registro.token : null;
}

/** Reemissão fora de qualquer evento (janela de renovação, troca de chave). */
export async function renovarToken(sessao: string, opcoes: { agora?: number } = {}): Promise<string | null> {
  if (!sessao || !permiteCategoria("analytics")) return null;
  const agora = (opcoes.agora ?? Math.floor(Date.now() / 1000)) as number;
  const registro = await emitir(sessao, agora);
  return registro ? registro.token : null;
}

/**
 * Emite (ou reemite) e guarda o token, deduplicando chamadas concorrentes.
 *
 * Sem a deduplicação, um `page_view` + três cliques no primeiro segundo
 * disparariam quatro pedidos ao emissor — que é rate-limitado a `30/min`
 * (`THROTTLE_CONSENTIMENTO_RATE`) e ainda assim é desperdício evitável.
 */
async function emitir(sessao: string, agora: number): Promise<TokenEmMaos | null> {
  const emVoo = EM_VOO.get(sessao);
  if (emVoo) return emVoo;

  const promessa = (async () => {
    try {
      const resposta = await pedirTokenConsentimento(sessao);
      const registro = validarRespostaEmissor(resposta, sessao, agora);
      if (!registro) return null;
      EM_MEMORIA.set(sessao, registro);
      SESSOES_COM_TOKEN.add(sessao);
      gravarArmazenado(sessao, registro);
      return registro;
    } catch {
      // Falha de rede, 429, 503 (backend sem chave) ou `ApiError`: o evento
      // simplesmente não é enviado. Fail-closed e silencioso — nada de
      // retentar em laço e nada de-console com o token.
      return null;
    } finally {
      EM_VOO.delete(sessao);
    }
  })();

  EM_VOO.set(sessao, promessa);
  return promessa;
}

/**
 * Cabeçalhos do evento com o token anexado.
 *
 * O header `X-Consent-Token` é o caminho preferido (não entra no corpo, e corpo
 * é o que um log de proxy poderia acabar guardando). Ele só pode ser usado no
 * caminho `fetch`, porque `navigator.sendBeacon` **não** permite cabeçalhos
 * customizados — para o beacon, use `anexarTokenAoCorpo`.
 */
export function cabecalhoConsentimento(token: string | null): Record<string, string> {
  return token ? { "X-Consent-Token": token } : {};
}

/**
 * Anexa o token ao corpo do evento (caminho do `sendBeacon`).
 *
 * O backend lê `X-Consent-Token` do header OU `consent_token` do corpo
 * (`backend/metricas/views.py::_token_do_request`), e `consent_token` está na
 * allowlist de transporte (`CAMPOS_TRANSPORTE`) — nunca vira conteúdo de evento.
 */
export function anexarTokenAoCorpo<T extends Record<string, unknown>>(
  corpo: T,
  token: string | null
): T & { consent_token?: string } {
  if (!token) return corpo;
  return { ...corpo, consent_token: token };
}

/** Limpa todos os tokens em mãos (troca de conta, logout, fim de teste). */
export function esquecerTodosTokens(): void {
  EM_MEMORIA.clear();
  EM_VOO.clear();
  SESSOES_COM_TOKEN.clear();
  if (typeof window === "undefined") return;
  try {
    // O `sessionStorage` é por sessão do portal; como o nome da chave inclui a
    // sessão, basta varrer as chaves conhecidas do prefixo.
    const chaves: string[] = [];
    for (let i = 0; i < window.sessionStorage.length; i += 1) {
      const chave = window.sessionStorage.key(i);
      if (chave && chave.startsWith(`${CHAVE_ARMAZENAMENTO}:`)) chaves.push(chave);
    }
    for (const chave of chaves) window.sessionStorage.removeItem(chave);
  } catch {
    // idem
  }
}

/**
 * Reage à mudança de consentimento.
 *
 * **Revogação**: o token em mãos é esquecido na hora. O backend continuaria
 * aceitando aquele token até o `exp` (a assinatura é válida), então continuar
 * usando depois da revogação seria um vazamento que ninguém perceberia — é o
 * motivo de o esquecimento estar aqui e não só no `track()`.
 *
 * **Concessão**: não pré-emite. A emissão acontece no primeiro evento, que é o
 * único momento em que sabemos que o visitante está de fato navegando (e é o
 * momento em que o evento é realmente enviado). Pedir token para quem não
 * vai gerar evento seria pedir prova de um consentimento sem uso.
 */
export function observarConsentimentoAnalytics(): void {
  if (typeof window === "undefined" || ESCUTANDO) return;
  ESCUTANDO = true;
  window.addEventListener(EVENTO_CONSENTIMENTO_ALTERADO, () => {
    if (permiteCategoria("analytics")) {
      // Nada a fazer aqui: o próximo `track()` usa ou renova o token.
      return;
    }
    for (const sessao of Array.from(SESSOES_COM_TOKEN)) esquecerToken(sessao);
    SESSOES_COM_TOKEN.clear();
  });
}
