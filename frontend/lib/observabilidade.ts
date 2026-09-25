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
  // O `…` conta para o teto: cortar em `limite` e depois anexar o marcador
  // devolvia `limite + 1` caracteres, ou seja, um teto que não era teto.
  const limitado = base.slice(0, Math.max(0, limite - 1));
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
/**
 * `Token <valor>` — o esquema do DRF, que é o token de sessão deste portal
 * (`rest_framework.authtoken`: header `Authorization: Token <key>`).
 *
 * A regra existe por causa de um teste, não por-speculação: sem ela, o texto
 * `Authorization: Token abc123` era redigido só até a palavra `Token` e o
 * **valor ficava no texto** (o `ATRIBUICAO_SEGREDO` casa `[^\s,;&]+`, que para
 * no espaço). O mesmo formato é o que o `api.ts` monta em toda chamada
 * autenticada, então a forma tem que estar coberta.
 */
const TOKEN_ESPACADO = /\bToken\s+[A-Za-z0-9._~+/=-]{8,}/gi;
const JWT = /\beyJ[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{4,}/g;
/**
 * Token DRF **solto**, sem rótulo: exatamente 40 hex em minúsculas
 * (`binascii.hexlify(os.urandom(20))`, `rest_framework/authtoken/models.py`).
 *
 * É a regra que fecha o último buraco do critério 6: um valor com a forma do
 * token que apareça num breadcrumb, num `context` ou na mensagem de uma
 * exceção é redigido mesmo quando o **nome** do campo não diz nada de
 * sensível (`sessao`, `valor`, `arg0`...). As bordas `(?<![0-9a-f])`/`(?![0-9a-f])`
 * evitam mascarar um hex maior que contenha um bloco de 40.
 *
 * Falso positivo conhecido e aceito: um SHA de commit (também 40 hex) escrito
 * dentro de uma mensagem vira `[REDACTED]`. O campo `release`/`tags.release` do
 * evento NÃO passa por esta regra, então a release continua legível — o que se
 * perde é o SHA citado no corpo de um texto, que ninguém usa para achar coisa
 * nenhuma num evento do Sentry.
 */
const TOKEN_DRF = /(?<![0-9a-f])[0-9a-f]{40}(?![0-9a-f])/g;
const ATRIBUICAO_SEGREDO =
  /\b(authorization|proxy-authorization|cookie|set-cookie|token|auth|api[_-]?key|access[_-]?key|secret|client[_-]?secret|passwd|password|pass|pwd|senha|chave|segredo|session[_-]?id|access[_-]?token|refresh[_-]?token|id[_-]?token|private[_-]?key)\s*[:=]\s*[^\s,;&]+/gi;
/**
 * Cabeçalho de autorização com valor que ocupa o resto da linha.
 *
 * roda ANTES de `ATRIBUICAO_SEGREDO` e consome o valor inteiro (inclusive o
 * `Token abc` de duas palavras), que é o formato real do header que o
 * `api.ts` envia.
 */
const CABECALHO_AUTORIZACAO =
  /\b(authorization|proxy-authorization)\s*[:=]\s*[^\n,;&]+/gi;

export const REDIGIDO = "[REDACTED]";

/** Redige texto livre (mensagem de exceção, motivo, header) para log/evento. */
export function redigirTexto(valor: unknown, limite = 300): string {
  let texto = valor == null ? "" : String(valor);
  texto = texto.replace(CABECALHO_AUTORIZACAO, (m) => `${m.split(/[:=]/)[0]}=${REDIGIDO}`);
  texto = texto.replace(ATRIBUICAO_SEGREDO, (m) => `${m.split(/[:=]/)[0]}=${REDIGIDO}`);
  texto = texto.replace(BEARER, `Bearer ${REDIGIDO}`);
  texto = texto.replace(TOKEN_ESPACADO, `Token ${REDIGIDO}`);
  texto = texto.replace(JWT, REDIGIDO);
  texto = texto.replace(TOKEN_DRF, REDIGIDO);
  texto = texto.replace(EMAIL, `$1[REDACTED_EMAIL]`);
  // Query string dentro de URL que apareça em texto de log. O caminho
  // RELATIVO também conta: o portal é same-origin, então o breadcrumb de
  // `fetch` do navegador é `/api/x?token=...`, nunca uma URL absoluta.
  texto = texto.replace(/((?:https?:\/\/|\/)[^\s?#]+)\?[^\s#]*/g, `$1?${REDIGIDO}`);
  if (texto.length > limite) return `${texto.slice(0, Math.max(0, limite - 1))}…`;
  return texto;
}

/**
 * Remove caracteres de controle — nenhum pode chegar a log/JSON/header.
 *
 * Inclui o bloco C1 (`0x80`-`0x9f`), que é o mesmo conjunto que
 * `normalizarRequestId` considera inválido: são caracteres de controle
 * Unicode, e um log que os carrega não é parseável por metade das ferramentas
 * que o leem.
 */
export function semControle(valor: unknown): string {
  return String(valor ?? "").replace(/[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]/g, "");
}

// ---------------------------------------------------------------------------
// Redação de estrutura (espelha `redact_payload` do backend,
// `backend/config/observability.py`)
// ---------------------------------------------------------------------------

/**
 * Profundidade máxima de recursão na redação estrutural, igual a
 * `MAX_REDACT_DEPTH` do backend. Um payload de erro aninhado além disso vira
 * `[TRUNCATED_DEPTH]` em vez de custo de CPU sem limite: o redator nunca pode
 * ser o que derruba o processo que ele existe para diagnosticar.
 */
export const MAX_REDITACAO_PROFUNDIDADE = 6;

/** Teto de itens por lista/objeto, igual a `MAX_REDACT_ITEMS` do backend. */
export const MAX_REDITACAO_ITENS = 100;

/** Teto de texto livre já redigido, igual a `MAX_LOG_TEXT` do backend. */
export const MAX_REDITACAO_TEXTO = 1000;

/**
 * `true` quando a CHAVE nomeia algo que nunca pode aparecer em telemetria.
 *
 * Mesma política por TOKEN do backend (`is_sensitive_key`), nunca por
 * sub-string: a versão por sub-string redigia campos inocente como `description`
 * ("descrip-tion" contém "ip") e `clip`, escondendo diagnóstico real.
 */
export function chaveSensivel(chave: unknown): boolean {
  return CHAVE_SENSIVEL.test(String(chave ?? ""));
}

/**
 * Reduz uma estrutura recursivamente para uma forma segura de log/evento.
 *
 * Réplica de `redact_payload` (`backend/config/observability.py`): chave
 * sensível vira `[REDACTED]`, texto livre passa por `redigirTexto` (e-mail,
 * JWT, Bearer, `token=...` e query string de URL somem), listas/objetos são
 * limitados e `unknown` cai no tipo. É também a **cópia**: a função devolve
 * sempre uma estrutura nova, então quem chama pode usá-la para sanitizar um
 * evento do Sentry sem mutar o objeto original do SDK.
 */
export function redigirPayload(
  valor: unknown,
  profundidade = 0,
  chave?: unknown
): unknown {
  if (chave !== undefined && chaveSensivel(chave)) return REDIGIDO;
  if (profundidade >= MAX_REDITACAO_PROFUNDIDADE) return "[TRUNCATED_DEPTH]";
  if (valor === null || valor === undefined) return valor;
  const tipo = typeof valor;
  if (tipo === "boolean" || tipo === "number") return valor;
  if (tipo === "string") return redigirTexto(valor, MAX_REDITACAO_TEXTO);
  if (tipo === "bigint") return valor.toString();
  if (tipo === "function" || tipo === "symbol") return `[${tipo}]`;
  if (valor instanceof Date) return valor.toISOString();
  if (valor instanceof Error) {
    // Mensagem de exceção sem stack e sem credencial: o stack é diagnóstico e
    // já vem no campo próprio do evento do Sentry.
    return redigirTexto(`${valor.name}: ${valor.message}`, MAX_REDITACAO_TEXTO);
  }
  if (Array.isArray(valor)) {
    const itens = valor.slice(0, MAX_REDITACAO_ITENS).map((item) =>
      redigirPayload(item, profundidade + 1)
    );
    if (valor.length > MAX_REDITACAO_ITENS) itens.push("[TRUNCATED_ITEMS]");
    return itens;
  }
  if (tipo === "object") {
    const entrada = valor as Record<string, unknown>;
    const saida: Record<string, unknown> = {};
    let indice = 0;
    for (const chaveAtual of Object.keys(entrada)) {
      if (indice >= MAX_REDITACAO_ITENS) {
        saida._truncated = true;
        break;
      }
      indice += 1;
      saida[redigirTexto(chaveAtual, 120)] = redigirPayload(
        entrada[chaveAtual],
        profundidade + 1,
        chaveAtual
      );
    }
    return saida;
  }
  return `[${tipo}]`;
}

/** Redige um valor já serializado em JSON, para uso em tag/contexto do Sentry. */
export function redigirJson(valor: unknown, limite = MAX_REDITACAO_TEXTO): string {
  try {
    const seguro = redigirPayload(valor);
    const texto = JSON.stringify(seguro) ?? "";
    return texto.length > limite ? `${texto.slice(0, Math.max(0, limite - 1))}…` : texto;
  } catch {
    return "[REDACTED]";
  }
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
