/**
 * Primitivas de observabilidade do cliente (implementation-contract.md run
 * 20260925-1020-observabilidade, critérios 1, 2, 3, 28).
 *
 * Este módulo é a RAIZ da correlação ponta a ponta e precisa ser importável
 * tanto pelo cliente (`lib/api.ts`, componentes client) quanto pelo servidor
 * do Next (`app/api/[...path]/route.ts`). Por isso ele NÃO importa `lib/api.ts`
 * nem nada que importe `lib/api.ts`: qualquer aresta para fora criaria ciclo.
 *
 * O contrato de normalização é o MESMO do backend
 * (`backend/config/middleware.py::normalizar_request_id`): o valor aceito
 * precisa ser imprimível, ter no máximo `MAX_REQUEST_ID_LENGTH` e não pode ser
 * o sentinel "-". Valor inválido, longo ou com caractere de controle vira um
 * UUID novo em vez de ser truncado — truncar poderia fazer dois requests
 * distintos colidirem no índice unique de `EventoBusca.request_id` (critério 3).
 */

/** Mesmo limite do backend (`EventoBusca.request_id` é `max_length=64`). */
export const MAX_REQUEST_ID_LENGTH = 64;

const HEX = "0123456789abcdef";

function byteParaHex(byte: number): string {
  return HEX[(byte >>> 4) & 0x0f] + HEX[byte & 0x0f];
}

/**
 * UUID v4 por `crypto.getRandomValues`, que é a API usada como fallback.
 *
 * NOTA sobre `randomUUID`: ele só existe em contexto SEGURO (HTTPS/localhost).
 * O portal é servido por HTTPS em dev/homolog/prod, mas o mesmo bundle roda em
 * `http://<ip>:3000` durante diagnóstico (foi assim que o incidente
 * 2026-09-18/19 foi diagnosticado) e `crypto.subtle` também não existe lá.
 * `getRandomValues` está disponível em contexto não seguro, então é ele — e
 * não o `Math.random()` que o código usava — que garante entropia real.
 */
function uuidDeBytes(bytes: Uint8Array): string {
  // Versão 4 + variante RFC 4122, para o valor continuar sendo um UUID canônico
  // (o backend não revalida o formato, mas o operador cola isso em buscas).
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex: string[] = [];
  for (let i = 0; i < 16; i += 1) hex.push(byteParaHex(bytes[i]));
  return (
    hex.slice(0, 4).join("") +
    "-" +
    hex.slice(4, 6).join("") +
    "-" +
    hex.slice(6, 8).join("") +
    "-" +
    hex.slice(8, 10).join("") +
    "-" +
    hex.slice(10, 16).join("")
  );
}

/**
 * Gera um `X-Request-ID` seguro por requisição (critério 1).
 *
 * Ordem de preferência: `crypto.randomUUID` → `crypto.getRandomValues` →
 * contador monotônico com prefixo de processo. O último degrau só existe para
 * ambientes sem WebCrypto (nunca visto em navegador/Node suportado) e é
 *derivado de `Date.now()` + contador, NÃO de `Math.random()`: mesmo no pior
 * caso ele é único dentro do processo, que é o que o índice unique exige.
 */
export function gerarRequestId(): string {
  try {
    const webcrypto = globalThis.crypto;
    if (webcrypto) {
      const comRandomUUID = webcrypto as Crypto & { randomUUID?: () => string };
      if (typeof comRandomUUID.randomUUID === "function") {
        const gerado = comRandomUUID.randomUUID();
        if (gerado) return gerado;
      }
      if (typeof webcrypto.getRandomValues === "function") {
        const bytes = new Uint8Array(16);
        webcrypto.getRandomValues(bytes);
        return uuidDeBytes(bytes);
      }
    }
  } catch {
    // Cai no degrau final abaixo em vez de derrubar a requisição.
  }
  return requestIdSemWebCrypto();
}

// Contador por PROCESSO, não por requisição: garante unicidade mesmo sem
// entropia. Em Node o `process` existe; no bundle do cliente não, e daí o
// `globalThis` (que sobrevive a duplicação de módulo em HMR do `next dev`).
const CONTADOR: { valor: number } = ((globalThis as Record<string, unknown>)
  .__portalRequestIdContador as { valor: number }) || { valor: 0 };
(globalThis as Record<string, unknown>).__portalRequestIdContador = CONTADOR;

function requestIdSemWebCrypto(): string {
  CONTADOR.valor += 1;
  const tempo = Date.now().toString(16);
  const seq = CONTADOR.valor.toString(16);
  return `req-${tempo}-${seq}-${byteParaHex((CONTADOR.valor >>> 0) % 255)}`;
}

/**
 * Normaliza um `X-Request-ID` recebido (resposta do Django, header do proxy ou
 * o que o cliente mandou). Espelha `normalizar_request_id` do backend.
 *
 * `crypto.randomUUID` é usado como valor de substituição porque o id gerado
 * localmente e o aceito pelo Django precisam ter a MESMA forma — assim o
 * operador encontra o mesmo valor no navegador, no log do proxy e no log do
 * Django.
 */
export function normalizarRequestId(valor: string | null | undefined): string {
  if (valor == null) return gerarRequestId();
  const bruto = String(valor);
  // Imprimibilidade verificada no valor BRUTO: tab e qualquer outro caractere
  // de controle continuam inválidos mesmo quando `strip()` os removeria das
  // bordas (mesma razão do backend).
  for (let i = 0; i < bruto.length; i += 1) {
    const codigo = bruto.charCodeAt(i);
    const ehControle =
      codigo < 0x20 || codigo === 0x7f || (codigo >= 0x80 && codigo <= 0x9f);
    if (ehControle) return gerarRequestId();
  }
  const requestId = bruto.replace(/^ +/, "").replace(/ +$/, "");
  if (!requestId || requestId === "-") return gerarRequestId();
  if (requestId.length > MAX_REQUEST_ID_LENGTH) return gerarRequestId();
  return requestId;
}

/**
 * Remove query string, fragment e credenciais de userinfo do path antes de
 * qualquer log/evento (critério 28). `?q=...` de busca e `?token=...` de
 * convite não podem ir para telemetria de produto nem para log técnico.
 */
export function caminhoSeguro(valor: string, limite = 300): string {
  let base = String(valor ?? "");
  const semHash = base.split("#")[0];
  const semQuery = semHash.split("?")[0];
  // `https://user:pass@host/x` — userinfo é credencial.
  base = semQuery.replace(/^([a-z][a-z0-9+.-]*:\/\/)[^/@]*@/i, "$1");
  const limitado = base.slice(0, Math.max(0, limite));
  return limitado.length < base.length ? `${limitado}…` : limitado;
}

/** Valores aceitos como "verdadeiro" no header booleano do backend. */
const VERDADEIRO = new Set(["1", "true", "yes", "on"]);

export function ehVerdadeiro(valor: string | null | undefined): boolean {
  if (!valor) return false;
  return VERDADEIRO.has(valor.trim().toLowerCase());
}

/**
 * Campos de texto que não podem aparecer em log/evento técnico, por TOKEN
 * (início/fim de palavra ou separador `_`/`-`) e nunca por sub-string: a
 * versão por sub-string redigia campos inocente como `description` e `clip`.
 */
const CHAVE_SENSIVEL =
  /(?:^|[^a-z0-9])(?:authorization|proxy-authorization|cookie|set-cookie|password|passwd|secret|token|api[-_]?key|access[-_]?key|private[-_]?key|credential|session|sessionid|csrf|xsrf|email|telefone|phone|documento|senha|chave|segredo|cpf|cnpj)(?:[^a-z0-9]|$)/i;

const EMAIL =
  /(^|[^\w.+-])[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}(?![A-Za-z0-9.-])/g;
const BEARER = /\bBearer\s+[A-Za-z0-9._~+/=-]+/gi;
const JWT = /\beyJ[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{4,}/g;
const ATRIBUICAO_SEGREDO =
  /\b(authorization|proxy-authorization|cookie|set-cookie|token|auth|api[_-]?key|access[_-]?key|secret|client[_-]?secret|passwd|password|pass|pwd|senha|chave|segredo|session[_-]?id|access[_-]?token|refresh[_-]?token|id[_-]?token|private[_-]?key)\s*[:=]\s*[^\s,;&]+/gi;

export const REDIGIDO = "[REDACTED]";

/** Redige texto livre (mensagem de exceção, motivo, header) para log/evento. */
export function redigirTexto(valor: unknown, limite = 300): string {
  let texto = valor == null ? "" : String(valor);
  texto = texto.replace(ATRIBUICAO_SEGREDO, (m) => `${m.split(/[:=]/)[0]}=${REDIGIDO}`);
  texto = texto.replace(BEARER, `Bearer ${REDIGIDO}`);
  texto = texto.replace(JWT, REDIGIDO);
  texto = texto.replace(EMAIL, `$1[REDACTED_EMAIL]`);
  // Query string dentro de URL que apareça em texto de log.
  texto = texto.replace(/(https?:\/\/[^\s?]+)\?[^\s#]+/g, `$1?${REDIGIDO}`);
  if (texto.length > limite) return `${texto.slice(0, Math.max(0, limite - 1))}…`;
  return texto;
}

/** Remove caracteres de controle — nenhum pode chegar a log/JSON/header. */
export function semControle(valor: unknown): string {
  return String(valor ?? "").replace(/[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]/g, "");
}

/**
 * Log de falha de API: estruturado e redigido.
 *
 * Não recebe o erro cru. O contrato exige que o log traga o suficiente para
 * correlacionar (request id + rota + método + status) e NADA que identifique a
 * pessoa ou o segredo: sem token, sem e-mail, sem query string, sem corpo da
 * resposta, sem `String(erro)` despejado.
 */
export interface DetalheFalhaApi {
  origem: "cliente" | "proxy";
  requestId: string | null;
  metodo: string;
  rota: string;
  status: number | null;
  motivo: "timeout" | "conexao" | "abort" | "http" | "corpo";
  duracaoMs?: number;
  detalhe?: string;
}

export function registrarFalhaApi(detalhe: DetalheFalhaApi): void {
  const registro: Record<string, unknown> = {
    origem: detalhe.origem,
    requestId: detalhe.requestId,
    metodo: detalhe.metodo,
    rota: caminhoSeguro(detalhe.rota),
    status: detalhe.status ?? null,
    motivo: detalhe.motivo,
  };
  if (typeof detalhe.duracaoMs === "number") {
    registro.duracaoMs = Math.round(detalhe.duracaoMs);
  }
  if (detalhe.detalhe) {
    registro.detalhe = redigirTexto(semControle(detalhe.detalhe));
  }
  try {
    console.error("[api] falha de requisição", registro);
  } catch {
    // Console indisponível nunca pode derrubar a tela do usuário.
  }
}
