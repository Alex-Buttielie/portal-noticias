/**
 * Configuração do Sentry do frontend — parte PURA, sem o SDK (run
 * 20260925-1020-observabilidade, critérios 5, 6, 20, 27).
 *
 * Por que um módulo separado e sem `import "@sentry/nextjs"`:
 *
 * 1. **Testabilidade.** A redação e a decisão de consentimento são a fronteira
 *    de privacidade do portal (o token DRF vive em `localStorage`, ver
 *    `lib/auth-context.tsx`). Uma função que "só funciona quando o SDK está
 *    carregado" não é auditável por teste unitário, e esta é justamente a
 *    função que precisa ser auditável.
 * 2. **Tempo de carregamento.** `sentry.client.config.ts` só carrega o SDK
 *    quando existe DSN **e** consentimento técnico; este módulo não puxa
 *    dependência alguma.
 *
 * O redator ESPELHA `backend/config/observability.py::sentry_before_send`:
 * mesma ordem de operações, mesmos campos removidos, mesmos defaults
 * (ambiente/release forçados, `user` fora, `request` sem cookie/header/query/
 * corpo). Onde o frontend é **mais** estrito que o backend, a razão está
 * escrita no ponto — são as arestas que o navegador abre e o Django não
 * (`stacktrace.frames[].vars`, breadcrumb de `fetch`/`xhr`, `request.env` do
 * servidor).
 *
 * NÃO-objetivo herdado do contrato: session replay, gravação de tela e PII.
 * `replaysSessionSampleRate` e `replaysOnErrorSampleRate` são **explícitos e
 * zero** — não basta omitir, porque o default do SDK é resolver o replay em
 * parte e um "deixei de fora" vira "alguém liga depois".
 */

import {
  caminhoSeguro,
  chaveSensivel,
  redigirPayload,
  redigirTexto,
  semControle,
} from "./observabilidade";

/** Nome do serviço no Sentry. O backend usa `portal-api`; o bundle é `portal-web`. */
export const SERVICO_FRONTEND = "portal-web";

export const AMBIENTE_PADRAO = "development";
export const RELEASE_PADRAO = "local";

/** Amostragem de traces exigida pela restrição de performance do contrato. */
export const TRACES_SAMPLE_RATE = 0.1;

/** Replay é NÃO-objetivo do contrato: zero explícito nos dois campos. */
export const REPLAYS_SESSION_SAMPLE_RATE = 0;
export const REPLAYS_ON_ERROR_SAMPLE_RATE = 0;

/**
 * Teto de caracteres de ambiente/release. O mesmo teto do backend
 * (`observability.py::release/environment`, 200/80): o valor vira header e tag,
 * então não pode ser uma fonte de injeção nem de cardinalidade infinita.
 */
const MAX_AMBIENTE = 80;
const MAX_RELEASE = 200;

/** `X-Environment`/`X-Release` do Django: os mesmos nomes, mesma semântica. */
const CARACTERES_INSEGUROS = /[\s\x00-\x1f\x7f]/g;

/** Leitura de ambiente injetada — o módulo puro não conhece `process`. */
export type LeituraAmbiente = (nome: string) => string | undefined;

/** Primeiro valor não vazio da lista de nomes, já sem caracteres de controle. */
export function primeiroValor(leitura: LeituraAmbiente, nomes: string[]): string | null {
  for (const nome of nomes) {
    const bruto = leitura(nome);
    if (typeof bruto !== "string") continue;
    const limpo = bruto.replace(CARACTERES_INSEGUROS, "").trim();
    if (limpo) return limpo;
  }
  return null;
}

/**
 * Ambiente efetivo para evento/tag/header.
 *
 * Um valor mal configurado **não pode virar cabeçalho de resposta** (CR/LF é
 * injeção de resposta), então o corte de caracteres de controle é a primeira
 * coisa que acontece — não a última.
 */
export function ambienteDe(leitura: LeituraAmbiente, nomes: string[] = []): string {
  const valor = primeiroValor(leitura, nomes);
  return (valor ?? AMBIENTE_PADRAO).slice(0, MAX_AMBIENTE) || AMBIENTE_PADRAO;
}

/** Release efetiva (SHA do build, por convenção), com o mesmo corte. */
export function releaseDe(leitura: LeituraAmbiente, nomes: string[] = []): string {
  const valor = primeiroValor(leitura, nomes);
  return (valor ?? RELEASE_PADRAO).slice(0, MAX_RELEASE) || RELEASE_PADRAO;
}

/**
 * Contexto que o `beforeSend` usa para decidir e rotular.
 *
 * `consentidoNoInicio` vira `enabled` (avaliado **uma vez**, na inicialização —
 * o `ClientOptions.enabled` do Sentry v10 é `boolean`, não função, e um
 * predicado ali seria silenciosamente ignorado: `enabled !== false` seria
 * `true` para uma função, ou seja, fail-**open**).
 *
 * `consentidoAgora` é o portão **por evento**, reavaliado a cada envio. É a
 * barreira que vale mesmo depois de o SDK estar carregado: revogar o
 * consentimento precisa parar o envio imediatamente, sem reinstalar o SDK.
 */
export interface ContextoSentry {
  dsn: string;
  ambiente: string;
  release: string;
  consentidoNoInicio: boolean;
  consentidoAgora: () => boolean;
}

/** Campos de `request` que saem inteiros, sem nem tentar redigir. */
const CAMPOS_REQUEST_REMOVIDOS = [
  "cookies",
  "headers",
  "query_string",
  "data",
  // Estrito em relação ao backend: no Next standalone, `request.env` é o
  // environment do processo (DSN, `API_INTERNAL_URL`, ...). Não é PII de
  // visitante, mas é configuração interna e não ajuda ninguém a depurar.
  "env",
];

/** Campos de breadcrumb que carregam corpo/header de requisição. */
const CAMPOS_BREADCRUMB_REMOVIDOS = [
  "body",
  "request_body",
  "response",
  "request",
  "headers",
  "request_headers",
  "response_headers",
];

function objeto(v: unknown): Record<string, unknown> | null {
  return v && typeof v === "object" && !Array.isArray(v)
    ? (v as Record<string, unknown>)
    : null;
}

/** `request` sem credencial e sem corpo; `url` perde query/fragment/userinfo. */
function sanearRequest(valor: unknown): unknown {
  const req = objeto(valor);
  if (!req) return valor;
  const seguro: Record<string, unknown> = {};
  for (const [chave, item] of Object.entries(req)) {
    if (CAMPOS_REQUEST_REMOVIDOS.includes(chave)) continue;
    if (chave === "url" || chave === "api_target") {
      seguro[chave] = typeof item === "string" ? caminhoSeguro(item, 1000) : redigirTexto(item);
      continue;
    }
    seguro[chave] = redigirTexto(item);
  }
  return seguro;
}

/**
 * Breadcrumbs são a superfície mais subestimada do evento do Sentry no
 * navegador: `Breadcrumbs` (default) registra `fetch`/`xhr`/`console`/clique,
 * e o `url` de um `fetch` para `/buscar?q=<o que a pessoa digitou>` ou
 * `/convite?token=...` é exatamente o dado que o critério 6 proíbe.
 */
function sanearBreadcrumbs(valor: unknown): unknown {
  const migalhas = objeto(valor);
  const lista = migalhas?.values;
  if (!Array.isArray(lista)) return valor;
  const seguro: Record<string, unknown> = { ...migalhas };
  seguro.values = lista.slice(0, 100).map((item) => {
    const migalha = objeto(item);
    if (!migalha) return redigirPayload(item);
    const saida: Record<string, unknown> = {};
    for (const [chave, valorCampo] of Object.entries(migalha)) {
      if (chave === "data") {
        const dados = objeto(valorCampo);
        if (dados) {
          const dadosSeguros: Record<string, unknown> = {};
          for (const [chaveDado, valorDado] of Object.entries(dados)) {
            if (CAMPOS_BREADCRUMB_REMOVIDOS.includes(chaveDado)) continue;
            if (chaveDado === "url" || chaveDado === "referrer") {
              dadosSeguros[chaveDado] =
                typeof valorDado === "string" ? caminhoSeguro(valorDado, 500) : redigirTexto(valorDado);
              continue;
            }
            dadosSeguros[chaveDado] = redigirPayload(valorDado);
          }
          saida[chave] = dadosSeguros;
        } else {
          saida[chave] = redigirPayload(valorCampo);
        }
        continue;
      }
      saida[chave] = typeof valorCampo === "string" ? redigirTexto(valorCampo) : redigirPayload(valorCampo);
    }
    return saida;
  });
  return seguro;
}

/**
 * `stacktrace.frames[].vars` é a aresta mais perigosa do SDK no navegador:
 * são os valores das variáveis locais do frame no momento da exceção — e a
 * variável `tokenSalvo`/`novoToken` do `AuthProvider` é, literalmente, o token
 * DRF. Remover `vars` inteiro é mais forte do que redactar por nome: o nome
 * da variável muda a cada build (minificação), a lista de nomes sensíveis não.
 */
function sanearException(valor: unknown): unknown {
  const excecao = objeto(valor);
  const valores = excecao?.values;
  if (!Array.isArray(valores)) return valor;
  const seguro: Record<string, unknown> = { ...excecao };
  seguro.values = valores.map((item) => {
    const valorAtual = objeto(item);
    if (!valorAtual) return redigirPayload(item);
    const saida: Record<string, unknown> = {};
    for (const [chave, valorCampo] of Object.entries(valorAtual)) {
      if (chave === "value" || chave === "module") {
        saida[chave] = redigirTexto(valorCampo);
        continue;
      }
      if (chave === "stacktrace") {
        saida[chave] = sanearStacktrace(valorCampo);
        continue;
      }
      saida[chave] = redigirPayload(valorCampo);
    }
    return saida;
  });
  return seguro;
}

function sanearStacktrace(valor: unknown): unknown {
  const stack = objeto(valor);
  if (!stack) return valor;
  const frames = stack.frames;
  const seguro: Record<string, unknown> = { ...stack };
  if (Array.isArray(frames)) {
    seguro.frames = frames.map((item) => {
      const frame = objeto(item);
      if (!frame) return redigirPayload(item);
      const saida: Record<string, unknown> = {};
      for (const [chave, valorCampo] of Object.entries(frame)) {
        if (chave === "vars" || chave === "previews") continue;
        saida[chave] = typeof valorCampo === "string" ? semControle(valorCampo).slice(0, 2000) : redigirPayload(valorCampo);
      }
      return saida;
    });
  }
  return seguro;
}

/**
 * Tags são strings de cardinalidade baixa. Uma tag cuja CHAVE nomeia segredo é
 * removida por inteiro (não redigida): `Authorization` como tag não tem leitura
 * útil, e "vale a pena ver que havia um Authorization" não justifica levar o
 * valor junto.
 */
function sanearTags(valor: unknown): Record<string, unknown> {
  const tags = objeto(valor) ?? {};
  const seguro: Record<string, unknown> = {};
  for (const [chave, item] of Object.entries(tags)) {
    if (item === null || item === undefined) continue;
    if (chaveSensivel(chave)) continue;
    seguro[semControle(chave).slice(0, 200)] = semControle(redigirTexto(item, 300));
  }
  return seguro;
}

/**
 * Portão final e sanitizador do evento do Sentry. Espelha
 * `sentry_before_send` do backend.
 *
 * Devolve `null` (= o SDK descarta o envelope) quando não há consentimento
 * técnico **agora**. Não é decoração: é o que garante o critério 27 mesmo com o
 * SDK carregado, e o que faz a revogação do consentimento valer imediatamente.
 */
export function eventoParaEnvio(
  evento: unknown,
  contexto: Pick<ContextoSentry, "ambiente" | "release" | "consentidoAgora">
): Record<string, unknown> | null {
  let autorizado = false;
  try {
    autorizado = Boolean(contexto.consentidoAgora());
  } catch {
    // Falha ao ler o consentimento é falha do portão, não motivo para enviar.
    autorizado = false;
  }
  if (!autorizado) return null;
  const original = objeto(evento);
  if (!original) return null;

  const seguro: Record<string, unknown> = {};
  for (const [chave, valor] of Object.entries(original)) {
    switch (chave) {
      // Barreira explícita: mesmo com `sendDefaultPii: false` e
      // `dataCollection.userInfo: false`, o `user` sai fora.
      case "user":
        continue;
      case "request":
        seguro.request = sanearRequest(valor);
        continue;
      case "breadcrumbs":
        seguro.breadcrumbs = sanearBreadcrumbs(valor);
        continue;
      case "exception":
        seguro.exception = sanearException(valor);
        continue;
      case "extra":
      case "contexts":
        seguro[chave] = redigirPayload(valor);
        continue;
      case "tags":
        seguro.tags = sanearTags(valor);
        continue;
      case "logentry":
        seguro.logentry = redigirPayload(valor);
        continue;
      case "fingerprint":
        seguro.fingerprint = Array.isArray(valor)
          ? valor.map((item) => redigirTexto(item, 200))
          : redigirTexto(valor);
        continue;
      case "message":
        seguro.message = redigirTexto(valor, 2000);
        continue;
      case "transaction":
        seguro.transaction = caminhoSeguro(redigirTexto(valor, 300), 300);
        continue;
      case "environment":
      case "release":
        // Escritos logo abaixo, com o valor efetivo: um evento que carrega o
        // ambiente errado no próprio corpo não pode sobrescrever o certo.
        continue;
      case "sdkProcessingMetadata":
        // Metadados internos do SDK (chave pública do DSN, release em cache).
        // Não são PII, mas o DSN não tem por que ser reenviado a cada evento.
        continue;
      default:
        seguro[chave] =
          typeof valor === "string" ? semControle(valor).slice(0, 4000) : redigirPayload(valor);
    }
  }

  seguro.environment = contexto.ambiente;
  seguro.release = contexto.release;
  const tags = sanearTags(seguro.tags);
  if (!tags.service) tags.service = SERVICO_FRONTEND;
  if (!tags.environment) tags.environment = contexto.ambiente;
  if (!tags.release) tags.release = contexto.release;
  seguro.tags = tags;
  return seguro;
}

export interface OpcoesSentry {
  dsn: string;
  enabled: boolean;
  environment: string;
  release: string;
  sendDefaultPii: false;
  tracesSampleRate: number;
  replaysSessionSampleRate: number;
  replaysOnErrorSampleRate: number;
  attachStacktrace: boolean;
  /**
   * Recusa estrutural de PII, **independente** do `beforeSend`: o SDK nunca
   * chega a montar `user`, cookie, header, corpo, query string ou valor de
   * variável local. O `beforeSend` é a segunda barreira, não a primeira.
   */
  dataCollection: Record<string, unknown>;
  beforeSend: (evento: unknown) => Record<string, unknown> | null;
  beforeSendTransaction: (evento: unknown) => Record<string, unknown> | null;
}

/**
 * Monta as opções de `Sentry.init` de browser **e** de servidor Node.
 *
 * Um único construtor para os dois lados é deliberado: divergir entre cliente e
 * servidor é como um evento de browser acaba com um campo que o do servidor não
 * tem, e o alerta que deveria ter disparado não dispara.
 */
export function criarOpcoesSentry(contexto: ContextoSentry): OpcoesSentry {
  const antes = (evento: unknown) => eventoParaEnvio(evento, contexto);
  return {
    dsn: contexto.dsn,
    // Condicionado ao consentimento técnico, avaliado no instante da
    // inicialização (ver `ContextoSentry.consentidoNoInicio` para por que não
    // pode ser função).
    enabled: contexto.consentidoNoInicio,
    environment: contexto.ambiente,
    release: contexto.release,
    sendDefaultPii: false,
    tracesSampleRate: TRACES_SAMPLE_RATE,
    replaysSessionSampleRate: REPLAYS_SESSION_SAMPLE_RATE,
    replaysOnErrorSampleRate: REPLAYS_ON_ERROR_SAMPLE_RATE,
    attachStacktrace: true,
    dataCollection: {
      userInfo: false,
      cookies: false,
      httpHeaders: { request: false, response: false },
      httpBodies: [],
      urlQueryParams: false,
      graphQL: { document: false, variables: false },
      genAI: { inputs: false, outputs: false },
      databaseQueryData: false,
      // Variáveis locais de frame: é o vetor do token em `localStorage`.
      stackFrameVariables: false,
      // Linhas de contexto do código-fonte: o fonte é público no repositório e
      // é o que dá legibilidade ao frame no Sentry.
      frameContextLines: 5,
    },
    beforeSend: antes,
    beforeSendTransaction: antes,
  };
}
