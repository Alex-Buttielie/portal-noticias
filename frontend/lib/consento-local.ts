/**
 * Leitura mínima do registro de consentimento, sem nenhuma importação.
 *
 * Existe para quebrar um ciclo: `lib/cookie-consent.ts` importa `lib/api.ts`
 * (para sincronizar com o backend) e `lib/api.ts` precisa saber se a categoria
 * de diagnóstico técnico foi concedida para enviar `X-Technical-Consent`. Se
 * `api.ts` importasse `cookie-consent.ts`, teríamos um ciclo de módulos.
 *
 * Aqui ficam APENAS a chave de armazenamento e a leitura booleana. Toda a
 * política (gravar, sincronizar, banner) continua em `cookie-consent.ts`, que é
 * quem reexporta estas funções.
 *
 * FAIL-CLOSED (critérios 5, 27): sem registro legível, sem resposta ou com
 * registro de versão anterior (que não conhecia a categoria técnica), a resposta
 * é `false`. O servidor (SSR) nunca tem `localStorage`, então requisições
 * feitas no servidor não carregam o header — o consentimento é do navegador.
 */

export const CHAVE_CONSENTIMENTO = "portal_noticias_consentimento_cookies";

/** Categoria de telemetria técnica/diagnóstico (erros, Web Vitals). */
export const CATEGORIA_TECNICA = "tecnico";

interface RegistroLocal {
  versao?: number;
  escolhas?: Record<string, unknown>;
}

/**
 * `true` somente quando existe registro legível com a categoria técnica
 * explicitamente ligada. Qualquer outro caso (sem registro, JSON inválido,
 * versão desconhecida, escolha ausente ou não booleana) devolve `false`.
 */
export function consentimentoTecnicoConcedido(): boolean {
  if (typeof window === "undefined") return false;
  try {
    const bruto = window.localStorage.getItem(CHAVE_CONSENTIMENTO);
    if (!bruto) return false;
    const dados = JSON.parse(bruto) as RegistroLocal | null;
    if (!dados || typeof dados !== "object") return false;
    const escolhas = dados.escolhas;
    if (!escolhas || typeof escolhas !== "object") return false;
    return escolhas[CATEGORIA_TECNICA] === true;
  } catch {
    // localStorage bloqueado (modo privado, política do navegador): fail-closed.
    return false;
  }
}
