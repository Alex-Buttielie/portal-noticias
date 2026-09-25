/**
 * PROVA DE QUE O TOKEN DO `localStorage` NÃO CHEGA AO SENTRY (critérios 5, 6, 27).
 *
 * ## O risco concreto
 *
 * `frontend/lib/auth-context.tsx` guarda o token DRF em
 * `localStorage["portal_noticias_token"]` e o passa como `Authorization: Token
 * <valor>` em toda chamada autenticada. A partir do momento em que o
 * `@sentry/nextjs` é inicializado no browser, o token tem caminhos plausíveis
 * para dentro de um evento:
 *
 * - `event.user` (SDK com `sendDefaultPii`);
 * - breadcrumb de `fetch`/`xhr` (url, e em algumas versões o corpo);
 * - `event.request.headers`/`cookies`/`data` (no servidor,via integração HTTP);
 * - `event.extra`/`contexts` (o `error.tsx` e o `api.ts` passam objetos);
 * - `stacktrace.frames[].vars` — **variáveis locais**, onde `tokenSalvo`/`novoToken`
 *   do `AuthProvider` vivem literalmente;
 * - `event.message`/texto de exceção com `token=` embutido;
 * - `event.request.url` com query string (`/convite?token=...`).
 *
 * ## Como este arquivo prova que isso não acontece
 *
 * Não testando "o SDK faz a coisa certa" (isso é território do SDK e muda a
 * cada versão), e sim a **nossa** fronteira: um evento sintético é montado com o
 * token em CADA uma dessas posições, e o que volta de `beforeSend` é conferido
 * por `JSON.stringify` — se a string do token não aparece em nenhum byte do
 * evento serializado, ela não sai. Isso pega também o caminho oblíquo (o token
 * dentro de uma chave que o redator não conhece, dentro de um array aninhado,
 * dentro de um breadcrumb).
 *
 * A segunda bateria confere o **fail-closed**: sem consentimento técnico, o
 * `beforeSend` devolve `null` (o SDK descarta o envelope) — o que é o que
 * garante o critério 27 independente de qualquer redação.
 *
 * `lib/sentry-opcoes.ts` é puro e não importa o SDK de propósito, então este
 * teste roda sem DSN, sem rede e sem browser.
 */

import { describe, expect, it } from "vitest";
import {
  ambienteDe,
  criarOpcoesSentry,
  eventoParaEnvio,
  primeiroValor,
  releaseDe,
  REPLAYS_ON_ERROR_SAMPLE_RATE,
  REPLAYS_SESSION_SAMPLE_RATE,
  SERVICO_FRONTEND,
  TRACES_SAMPLE_RATE,
  type ContextoSentry,
} from "../lib/sentry-opcoes";

/** Token de mentira, com a mesma FORMA do DRF (`<hash de 40 hex>`). */
const TOKEN = "a1b2c3d4e5f60718293a4b5c6d7e8f9012345678";
const OUTRO_TOKEN = "ffffffffffffffffffffffffffffffffffffffff";

const EMAIL = "pessoa.exemplo@dominio.invalido";

function contexto(consentido: boolean): ContextoSentry {
  return {
    dsn: "https://chave-publica@o0.ingest.us.sentry.io/0",
    ambiente: "homolog",
    release: "b1-proxy-check-1",
    consentidoNoInicio: consentido,
    consentidoAgora: () => consentido,
  };
}

/**
 * Evento com o token em TODAS as posições plausíveis de uma vez. É
 * deliberadamente exagerado: cada entrada aqui é um caminho que já existiu em
 * alguma versão do SDK ou que a instrumentação de aplicação poderia criar.
 */
function eventoComTokenEmTudo(valor = TOKEN): Record<string, unknown> {
  return {
    event_id: "aaaa",
    message: `falha ao chamar a API com token=${valor}`,
    logger: "app/error.tsx",
    release: "release-falso-do-evento",
    environment: "development-falso",
    // 1. `user`
    user: { id: "42", email: EMAIL, ip_address: "203.0.113.9", username: EMAIL },
    // 2. breadcrumb de fetch/xhr
    breadcrumbs: {
      values: [
        {
          category: "fetch",
          type: "http",
          message: `GET /api/metricas/eventos/?sessao=${valor}`,
          data: {
            method: "POST",
            url: `https://portal.exemplo/api/assinatura/assinar/?convite=${valor}`,
            status_code: 401,
            request_body_size: 120,
            body: `{"token":"${valor}","senha":"${valor}"}`,
            headers: { Authorization: `Token ${valor}`, Cookie: `sessao=${valor}` },
          },
        },
        {
          category: "console",
          level: "error",
          message: `[api] falha ${valor}`,
          data: { email: EMAIL, arg0: { token: valor } },
        },
      ],
    },
    // 3. request do servidor
    request: {
      method: "GET",
      url: `https://portal.exemplo/api/metricas/eventos/?token=${valor}#frag`,
      query_string: `token=${valor}`,
      headers: { Authorization: `Token ${valor}`, "X-Consent-Token": valor },
      cookies: `portal_noticias_token=${valor}`,
      data: { token: valor, email: EMAIL },
      env: { SENTRY_DSN: "https://chave@o0.ingest.us.sentry.io/0", API_INTERNAL_URL: "http://127.0.0.1:8000" },
    },
    // 4. extra/contexts
    extra: { token: valor, email: EMAIL, aninhado: { profundo: { Authorization: `Token ${valor}` } } },
    contexts: {
      browser: { name: "Chrome", user_agent: `Mozilla/5.0 ... Token ${valor}` },
      trace: { data: { "http.request.header.Authorization": `Token ${valor}`, "sessao": valor } },
    },
    // 5. variaveis locais de frame: o vetor do `AuthProvider`
    exception: {
      values: [
        {
          type: "ApiError",
          value: `status 401 — token ${valor}`,
          stacktrace: {
            frames: [
              {
                filename: "webpack-internal:///./app/login/page.tsx",
                function: "fazerLogin",
                lineno: 40,
                vars: { tokenSalvo: valor, response: { token: valor }, email: EMAIL },
              },
            ],
          },
        },
      ],
    },
    tags: { request_id: "req-1", Authorization: valor },
    sdkProcessingMetadata: { sentryRelease: { name: valor } },
  };
}

function serializado(evento: unknown): string {
  return JSON.stringify(evento) ?? "";
}

describe("beforeSend: o token do localStorage nao chega ao Sentry", () => {
  it("nao deixa o token em NENHUM campo do evento serializado", () => {
    const saida = eventoParaEnvio(eventoComTokenEmTudo(), contexto(true));
    expect(saida).not.toBeNull();
    const texto = serializado(saida);
    expect(texto).not.toContain(TOKEN);
    expect(texto).not.toContain(OUTRO_TOKEN);
  });

  it("nao deixa e-mail, IP completo nem user", () => {
    const saida = eventoParaEnvio(eventoComTokenEmTudo(), contexto(true)) as Record<string, unknown>;
    const texto = serializado(saida);
    expect(texto).not.toContain(EMAIL);
    expect(texto).not.toContain("203.0.113.9");
    expect(saida.user).toBeUndefined();
  });

  it("nao deixa query string nem fragmento na URL do request", () => {
    const saida = eventoParaEnvio(eventoComTokenEmTudo(), contexto(true)) as Record<string, unknown>;
    const request = saida.request as Record<string, unknown>;
    // O path sobrevive (é diagnóstico); query, fragmento e userinfo não.
    expect(String(request.url)).toBe("https://portal.exemplo/api/metricas/eventos/");
    expect(String(request.url)).not.toContain("?");
    expect(String(request.url)).not.toContain("#");
  });

  it("remove cookies, headers, corpo e env do request inteiro", () => {
    const saida = eventoParaEnvio(eventoComTokenEmTudo(), contexto(true)) as Record<string, unknown>;
    const request = saida.request as Record<string, unknown>;
    for (const campo of ["cookies", "headers", "query_string", "data", "env"]) {
      expect(request).not.toHaveProperty(campo);
    }
    // O método sobrevive: é diagnóstico, não é segredo.
    expect(request.method).toBe("GET");
  });

  it("redige a URL e o corpo dos breadcrumbs de fetch/xhr", () => {
    const saida = eventoParaEnvio(eventoComTokenEmTudo(), contexto(true)) as Record<string, unknown>;
    const migalhas = (saida.breadcrumbs as Record<string, unknown>).values as Array<Record<string, unknown>>;
    const primeira = migalhas[0];
    const dados = primeira.data as Record<string, unknown>;
    expect(String(dados.url)).not.toContain("?");
    expect(dados).not.toHaveProperty("body");
    expect(dados).not.toHaveProperty("headers");
    expect(serializado(primeira)).not.toContain(TOKEN);
  });

  it("descarta vars e previews dos frames de stacktrace", () => {
    const saida = eventoParaEnvio(eventoComTokenEmTudo(), contexto(true)) as Record<string, unknown>;
    const valores = ((saida.exception as Record<string, unknown>).values as Array<Record<string, unknown>>);
    const frames = ((valores[0].stacktrace as Record<string, unknown>).frames as Array<Record<string, unknown>>);
    expect(frames[0]).not.toHaveProperty("vars");
    expect(frames[0]).not.toHaveProperty("previews");
    // Nome de arquivo e linha sobrevivem: sem eles o frame não serve para nada.
    expect(String(frames[0].filename)).toContain("login/page.tsx");
    expect(frames[0].lineno).toBe(40);
  });

  it("redige a mensagem do evento e o valor da excecao", () => {
    const saida = eventoParaEnvio(eventoComTokenEmTudo(), contexto(true)) as Record<string, unknown>;
    expect(String(saida.message)).not.toContain(TOKEN);
    expect(String(saida.message)).toContain("[REDACTED]");
    const valores = ((saida.exception as Record<string, unknown>).values as Array<Record<string, unknown>>);
    expect(String(valores[0].value)).not.toContain(TOKEN);
  });

  it("redige tags e remove tag de chave sensivel", () => {
    const saida = eventoParaEnvio(eventoComTokenEmTudo(), contexto(true)) as Record<string, unknown>;
    const tags = saida.tags as Record<string, unknown>;
    expect(tags.Authorization).toBeUndefined();
    expect(tags.request_id).toBe("req-1");
  });

  it("forca ambiente e releaseEfetivos, ignorando os do proprio evento", () => {
    const saida = eventoParaEnvio(eventoComTokenEmTudo(), contexto(true)) as Record<string, unknown>;
    expect(saida.environment).toBe("homolog");
    expect(saida.release).toBe("b1-proxy-check-1");
    const tags = saida.tags as Record<string, unknown>;
    expect(tags.environment).toBe("homolog");
    expect(tags.release).toBe("b1-proxy-check-1");
    expect(tags.service).toBe(SERVICO_FRONTEND);
  });

  it("nao reenvia o sdkProcessingMetadata (chave publica do DSN)", () => {
    const saida = eventoParaEnvio(eventoComTokenEmTudo(), contexto(true)) as Record<string, unknown>;
    expect(saida).not.toHaveProperty("sdkProcessingMetadata");
  });

  it("aguenta um evento com nesting profundo e listas grandes", () => {
    // Um payload de erro malicioso não pode virar custo sem limite no redator.
    const fundo: Record<string, unknown> = { token: TOKEN };
    let cursor = fundo;
    for (let i = 0; i < 40; i += 1) {
      const proximo: Record<string, unknown> = {};
      cursor.proximo = proximo;
      cursor = proximo;
    }
    cursor.token = TOKEN;
    const evento = { ...eventoComTokenEmTudo(), extra: { fundo }, contextos: { lista: Array.from({ length: 500 }, () => ({ token: TOKEN })) } };
    const saida = eventoParaEnvio(evento, contexto(true));
    expect(saida).not.toBeNull();
    expect(serializado(saida)).not.toContain(TOKEN);
  });

  it("ignora evento que nao e objeto (o SDK nunca deve chamar assim)", () => {
    for (const invalido of [null, undefined, "texto", 42, []]) {
      expect(eventoParaEnvio(invalido, contexto(true))).toBeNull();
    }
  });
});

describe("fail-closed de consentimento (criterios 5 e 27)", () => {
  it("devolve null sem consentimento tecnico — nada e enviado", () => {
    expect(eventoParaEnvio(eventoComTokenEmTudo(), contexto(false))).toBeNull();
  });

  it("falha ao LER o consentimento tambem e falha fechada", () => {
    const quebrado: ContextoSentry = {
      ...contexto(true),
      consentidoAgora: () => {
        throw new Error("localStorage bloqueado");
      },
    };
    expect(eventoParaEnvio(eventoComTokenEmTudo(), quebrado)).toBeNull();
  });

  it("reavalia o consentimento a CADA evento (revogacao vale na hora)", () => {
    let autorizado = true;
    const dinamico: ContextoSentry = { ...contexto(true), consentidoAgora: () => autorizado };
    expect(eventoParaEnvio(eventoComTokenEmTudo(), dinamico)).not.toBeNull();
    autorizado = false;
    expect(eventoParaEnvio(eventoComTokenEmTudo(), dinamico)).toBeNull();
  });
});

describe("opcoes do SDK", () => {
  it("desliga PII padrao explicitamente", () => {
    const opcoes = criarOpcoesSentry(contexto(true));
    expect(opcoes.sendDefaultPii).toBe(false);
  });

  it("mantem sampling de traces em 10%", () => {
    expect(criarOpcoesSentry(contexto(true)).tracesSampleRate).toBe(TRACES_SAMPLE_RATE);
    expect(TRACES_SAMPLE_RATE).toBe(0.1);
  });

  it("zera session replay explicitamente nos dois campos (nao-objetivo do contrato)", () => {
    const opcoes = criarOpcoesSentry(contexto(true));
    expect(opcoes.replaysSessionSampleRate).toBe(REPLAYS_SESSION_SAMPLE_RATE);
    expect(opcoes.replaysOnErrorSampleRate).toBe(REPLAYS_ON_ERROR_SAMPLE_RATE);
    expect(opcoes.replaysSessionSampleRate).toBe(0);
    expect(opcoes.replaysOnErrorSampleRate).toBe(0);
  });

  it("condiciona `enabled` ao consentimento no instante da inicializacao", () => {
    expect(criarOpcoesSentry(contexto(true)).enabled).toBe(true);
    expect(criarOpcoesSentry(contexto(false)).enabled).toBe(false);
  });

  it("recusa estruturalmente PII no dataCollection, alem do beforeSend", () => {
    const { dataCollection } = criarOpcoesSentry(contexto(true));
    expect(dataCollection.userInfo).toBe(false);
    expect(dataCollection.cookies).toBe(false);
    expect(dataCollection.httpHeaders).toEqual({ request: false, response: false });
    expect(dataCollection.httpBodies).toEqual([]);
    expect(dataCollection.urlQueryParams).toBe(false);
    expect(dataCollection.stackFrameVariables).toBe(false);
  });

  it("aplica o mesmo beforeSend a evento e a transacao", () => {
    const opcoes = criarOpcoesSentry(contexto(true));
    expect(opcoes.beforeSend).toBe(opcoes.beforeSendTransaction);
  });

  it("transacao (Web Vitals/pageload) tambem passa pelo portao de consentimento", () => {
    const transacao = { type: "transaction", transaction: "/buscar?q=x", contexts: { trace: { data: {} } } };
    const autorizado = criarOpcoesSentry(contexto(true)).beforeSendTransaction(transacao) as Record<string, unknown>;
    expect(autorizado).not.toBeNull();
    expect(String(autorizado.transaction)).toBe("/buscar");
    expect(criarOpcoesSentry(contexto(false)).beforeSendTransaction(transacao)).toBeNull();
  });
});

describe("resolucao de ambiente e release", () => {
  const leitura = (mapa: Record<string, string>) => (nome: string) => mapa[nome];

  it("usa o primeiro valor nao vazio da lista", () => {
    expect(primeiroValor(leitura({ B: "dois", A: "um" }), ["A", "B"])).toBe("um");
    expect(primeiroValor(leitura({ B: "dois" }), ["A", "B"])).toBe("dois");
    expect(primeiroValor(leitura({}), ["A"])).toBeNull();
    expect(primeiroValor(leitura({ A: "   " }), ["A"])).toBeNull();
  });

  it("descarta caracteres de controle (CR/LF em header e injecao de resposta)", () => {
    expect(ambienteDe(leitura({ E: "homolog\r\nX-Injetado: 1" }), ["E"])).toBe("homologX-Injetado:1");
    expect(releaseDe(leitura({ R: "abc def" }), ["R"])).toBe("abcdef");
  });

  it("cai no padrao quando nada e informado", () => {
    expect(ambienteDe(leitura({}), ["E"])).toBe("development");
    expect(releaseDe(leitura({}), ["R"])).toBe("local");
  });

  it("limita o tamanho (release vira header e tag)", () => {
    const longo = "a".repeat(5000);
    expect(releaseDe(leitura({ R: longo }), ["R"]).length).toBeLessThanOrEqual(200);
    expect(ambienteDe(leitura({ E: longo }), ["E"]).length).toBeLessThanOrEqual(80);
  });
});
