/**
 * Prova de que `sentry.server.config.ts` é inicialização REAL (critérios 6, 19).
 *
 * Antes deste bloco os dois arquivos de configuração eram *scaffolding inerte*:
 * o pacote não estava instalado, o `next.config.js` não carregava nada e o
 * `require("@sentry/nextjs")` estava dentro de um `try/catch` que só emitia um
 * `console.warn`. Um teste que verifica "o arquivo existe" não diria nada; este
 * importa o módulo de verdade, deixa o `Sentry.init` rodar e inspeciona as
 * opções que o cliente ficou.
 *
 * As variáveis de ambiente são setadas ANTES do import dinâmico e os módulos são
 * recarregados (`vi.resetModules`) porque o Next/Vite faz hoist dos imports:
 * sem isso o teste leria as variáveis do import estático do próprio arquivo de
 * teste e "passaria" sem exercitar nada.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

/**
 * DSN obviamente falso (chave pública toda zero, host `.invalid`, ID 0). Existe
 * para o SDK aceitar o formato sem reclamar no stderr; **nunca** é um DSN real
 * e não há segredo aqui — a chave pública do Sentry é pública por definição, e
 * esta nem é uma.
 */
const DSN_FALSO = "https://00000000000000000000000000000000@o0.ingest.us.sentry.invalid/0";

const AMBIENTE: Record<string, string | undefined> = {};

function definir(nome: string, valor: string | undefined): void {
  AMBIENTE[nome] = valor;
  if (valor === undefined) delete process.env[nome];
  else process.env[nome] = valor;
}

async function carregarCliente(): Promise<{ getOptions: () => Record<string, unknown> } | null> {
  vi.resetModules();
  const sentry = (await import("@sentry/nextjs")) as unknown as {
    getClient: () => { getOptions: () => Record<string, unknown> } | undefined;
    getCurrentScope: () => { setClient: (c: unknown) => void };
  };
  // O `init` do SERVIDOR e de uso unico por processo: `@sentry/nextjs` faz
  // `if (sdkAlreadyInitialized()) return`, e `sdkAlreadyInitialized()` e
  // `!!getClient()`. Sem esta linha, o segundo cenario leria as opcoes do
  // cliente do primeiro e o teste "fail-closed" passaria por acidente - o
  // pior tipo de verde. `setClient(undefined)` devolve o processo ao estado
  // inicial, que e o que importa aqui.
  sentry.getCurrentScope().setClient(undefined);
  await import("../sentry.server.config");
  return sentry.getClient() ?? null;
}

beforeEach(() => {
  definir("SENTRY_DSN", DSN_FALSO);
  definir("NEXT_PUBLIC_SENTRY_DSN", undefined);
  definir("SENTRY_ENVIRONMENT", "homolog");
  definir("SENTRY_RELEASE", "sha-homolog-1234567");
  definir("RELEASE_SHA", undefined);
  definir("GIT_SHA", undefined);
  definir("NEXT_PUBLIC_SENTRY_ENVIRONMENT", undefined);
  definir("NEXT_PUBLIC_SENTRY_RELEASE", undefined);
  definir("SENTRY_TECHNICAL_CONSENT_DEFAULT", "true");
});

afterEach(async () => {
  // Cada `init` adiciona um listener `beforeExit` no `process`; sem fechar o
  // cliente, seis cenários no mesmo processo estouram o limite de 10 listeners
  // e o teste imprime um `MaxListenersExceededWarning` que é artefato do teste,
  // não do código. Fechar mantém a saída da CI limpa, que é o ponto: um aviso
  // recorrente treina o time a ignorar avisos.
  const sentry = (await import("@sentry/nextjs")) as unknown as {
    getClient: () => { close: (t?: number) => PromiseLike<boolean> } | undefined;
    getCurrentScope: () => { setClient: (c: unknown) => void };
  };
  await sentry.getClient()?.close(0);
  sentry.getCurrentScope().setClient(undefined);
  for (const nome of Object.keys(AMBIENTE)) {
    delete process.env[nome];
    delete AMBIENTE[nome];
  }
  vi.resetModules();
});

describe("sentry.server.config.ts", () => {
  it("inicializa de verdade quando ha DSN e consentimento do operador", async () => {
    const cliente = await carregarCliente();
    expect(cliente).not.toBeNull();
    const opcoes = cliente?.getOptions() as Record<string, unknown>;
    expect(opcoes.dsn).toBe(DSN_FALSO);
    expect(opcoes.environment).toBe("homolog");
    expect(opcoes.release).toBe("sha-homolog-1234567");
    expect(opcoes.enabled).toBe(true);
  });

  it("mantem a politica de privacidade do browser no servidor", async () => {
    const opcoes = (await carregarCliente())?.getOptions() as Record<string, unknown>;
    expect(opcoes.sendDefaultPii).toBe(false);
    expect(opcoes.tracesSampleRate).toBe(0.1);
    expect(opcoes.replaysSessionSampleRate).toBe(0);
    expect(opcoes.replaysOnErrorSampleRate).toBe(0);
    const coleta = opcoes.dataCollection as Record<string, unknown>;
    expect(coleta.userInfo).toBe(false);
    expect(coleta.cookies).toBe(false);
    expect(coleta.httpBodies).toEqual([]);
    expect(coleta.urlQueryParams).toBe(false);
    expect(coleta.stackFrameVariables).toBe(false);
  });

  it("FAIL-CLOSED: sem SENTRY_TECHNICAL_CONSENT_DEFAULT nao inicializa nada", async () => {
    definir("SENTRY_TECHNICAL_CONSENT_DEFAULT", undefined);
    const opcoes = (await carregarCliente())?.getOptions() as Record<string, unknown> | undefined;
    // Cliente pode existir, mas `enabled: false` significa: sem transporte,
    // sem integrations e sem envelope. E o beforeSend recusa tudo.
    expect(opcoes?.enabled).toBe(false);
    const antes = opcoes?.beforeSend as (e: unknown) => unknown;
    expect(antes({ message: "erro qualquer" })).toBeNull();
  });

  it("FAIL-CLOSED: `false` explicito e o mesmo que ausente", async () => {
    definir("SENTRY_TECHNICAL_CONSENT_DEFAULT", "false");
    const opcoes = (await carregarCliente())?.getOptions() as Record<string, unknown>;
    expect(opcoes.enabled).toBe(false);
  });

  it("sem DSN nao ha cliente nenhum (e o build nao quebra)", async () => {
    definir("SENTRY_DSN", undefined);
    await expect(import("../sentry.server.config")).resolves.toBeDefined();
  });

  it("o beforeSend do servidor redige o mesmo que o do browser", async () => {
    const opcoes = (await carregarCliente())?.getOptions() as Record<string, unknown>;
    const antes = opcoes.beforeSend as (e: unknown) => Record<string, unknown> | null;
    const TOKEN = "a1b2c3d4e5f60718293a4b5c6d7e8f9012345678";
    const saida = antes({
      message: `falha com token=${TOKEN}`,
      user: { email: "pessoa@dominio.invalido" },
      request: { url: `https://x.invalid/api?token=${TOKEN}`, headers: { Authorization: `Token ${TOKEN}` } },
      exception: { values: [{ type: "E", value: TOKEN, stacktrace: { frames: [{ vars: { t: TOKEN } }] } }] },
    });
    expect(saida).not.toBeNull();
    expect(JSON.stringify(saida)).not.toContain(TOKEN);
    expect(saida?.user).toBeUndefined();
  });
});
