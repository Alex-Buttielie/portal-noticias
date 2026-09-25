/**
 * Teste de INTEGRAÇÃO com o backend real do consentimento (critérios 25 e 26).
 *
 * Por que existe separado da suíte pura: o formato do token, o nome da
 * categoria, o nome do campo no corpo e o código de recusa do backend são
 * contrato entre dois lados. Um teste que só valida a nossa própria função não
 * pega uma divergência — e a divergência aqui é silenciosa: o evento simplesmente
 * não é persistido, com HTTP 202 e `{registrado: false}`, que parece sucesso.
 *
 * ## Não roda por padrão
 *
 * Precisa de um Django no ar (em dev, `http://localhost:8000`) e **grava um
 * evento sintético** na base local. Está atrás de uma variável de ambiente
 * explícita, então `npm test` na CI não toca em nada:
 *
 * ```console
 * B2_INTEGRACAO=1 B2_API_BASE=http://localhost:8000 npx vitest run testes/integracao-backend.test.ts
 * ```
 *
 * O que ele prova, quando roda:
 * 1. o emissor real devolve um envelope que o cliente aceita;
 * 2. com token, o backend **persiste** o evento (`registrado: true`);
 * 3. sem token, o backend **recusa** (`consent_ausente`) — a prova de que o
 *    cliente fail-closed não está inventando nada: sem token não há dado de
 *    produto autorizado;
 * 4. token de outra sessão e token adulterado também são recusados.
 */

import { beforeAll, describe, expect, it } from "vitest";

const ATIVO = process.env.B2_INTEGRACAO === "1";
const BASE = (process.env.B2_API_BASE || "http://localhost:8000").replace(/\/$/, "");
const SESSAO = "b2-integracao-sessao";
const OUTRA_SESSAO = "b2-integracao-outra";

/**
 * O cliente é fail-closed e não tem `window` no node, então
 * `permiteCategoria("analytics")` responderia `false` e o teste provaria nada.
 * O stub abaixo é o menor `localStorage` que satisfaz
 * `lib/cookie-consent.ts::obterConsentimento` — e ele também registra o
 * registro de consentimento no formato REAL (versão 2 com a categoria
 * `analytics`), porque um formato inventado aqui daria um falso verde.
 */
function instalarJanelaComConsentimento(): void {
  const dados = new Map<string, string>();
  dados.set(
    "portal_noticias_consentimento_cookies",
    JSON.stringify({
      versao: 2,
      escolhas: { analytics: true, personalizacao: true, tecnico: false },
      respondidoEm: new Date(0).toISOString(),
    })
  );
  const armazenamento = () => ({
    getItem: (chave: string) => dados.get(chave) ?? null,
    setItem: (chave: string, valor: string) => void dados.set(chave, valor),
    removeItem: (chave: string) => void dados.delete(chave),
    key: (indice: number) => Array.from(dados.keys())[indice] ?? null,
    get length() {
      return dados.size;
    },
    clear: () => dados.clear(),
  });
  (globalThis as Record<string, unknown>).window = {
    localStorage: armazenamento(),
    sessionStorage: armazenamento(),
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
    location: { pathname: "/" },
    navigator: { userAgent: "b2-integracao" },
  };
}

async function postar(corpo: unknown, token?: string): Promise<{ status: number; json: Record<string, unknown> }> {
  const resposta = await fetch(`${BASE}/api/metricas/eventos/`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { "X-Consent-Token": token } : {}),
    },
    body: JSON.stringify(corpo),
  });
  return { status: resposta.status, json: (await resposta.json()) as Record<string, unknown> };
}

const EVENTO = {
  tipo: "page_view",
  path: "/",
  sessao: SESSAO,
  dispositivo: "desktop",
  origem: "direto",
};

describe.skipIf(!ATIVO)("integracao com o backend de consentimento", () => {
  let backendNoAr = false;

  beforeAll(async () => {
    instalarJanelaComConsentimento();
    try {
      const resposta = await fetch(`${BASE}/api/metricas/consent/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ categoria: "analytics", sessao: SESSAO }),
      });
      backendNoAr = resposta.ok;
    } catch {
      backendNoAr = false;
    }
    if (!backendNoAr) {
      throw new Error(
        `Backend indisponivel em ${BASE}. Suba o Django ou ajuste B2_API_BASE (o teste NAO e pulado em silencio: falhar e melhor que um verde sem prova).`
      );
    }
  });

  it("o cliente aceita o envelope que o emissor real devolve", async () => {
    const { garantirToken } = await import("../lib/consent-token");
    const token = await garantirToken(SESSAO);
    expect(token).toBeTruthy();
    // Três partes, versão v1 — o mesmo contrato do golden example do Bloco A2.
    const partes = String(token).split(".");
    expect(partes).toHaveLength(3);
    expect(partes[0]).toBe("v1");
    expect(partes[1]).not.toContain("=");
  });

  it("SEM token o backend recusa e nao persiste (criterio 26)", async () => {
    const { json, status } = await postar(EVENTO);
    expect(status).toBe(202);
    expect(json.registrado).toBe(false);
    expect(String(json.motivo)).toBe("consent_ausente");
  });

  it("COM token o backend persiste o evento (criterios 25 e 26)", async () => {
    const { garantirToken } = await import("../lib/consent-token");
    const token = await garantirToken(SESSAO);
    const { json, status } = await postar(EVENTO, token ?? undefined);
    // Status conferido na view real (`EventoIngestaoView.post`): `201` quando
    // persistiu, `202` quando recusado. Este era o ponto do contrato que o
    // teste puro NAO pegaria sozinho — foi pego aqui, na primeira execucao.
    expect(status).toBe(201);
    expect(json.registrado).toBe(true);
  });

  it("token de outra sessao e recusado (o token nao e bem publico)", async () => {
    const emissao = await fetch(`${BASE}/api/metricas/consent/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ categoria: "analytics", sessao: OUTRA_SESSAO }),
    });
    const resposta = (await emissao.json()) as { token?: string };
    expect(resposta.token).toBeTruthy();
    const { json } = await postar(EVENTO, resposta.token);
    expect(json.registrado).toBe(false);
    expect(String(json.motivo)).toBe("consent_sujeito_invalido");
  });

  it("token adulterado e recusado (a assinatura e verificada no servidor)", async () => {
    const { garantirToken } = await import("../lib/consent-token");
    const token = (await garantirToken(SESSAO)) ?? "";
    const partes = token.split(".");
    const adulterado = `${partes[0]}.${partes[1]}.${"A".repeat(partes[2].length)}`;
    const { json } = await postar(EVENTO, adulterado);
    expect(json.registrado).toBe(false);
    expect(["consent_assinatura_invalida", "consent_malformado"]).toContain(String(json.motivo));
  });

  it("o track() do analytics ANEXA o token ao evento (o caminho real do portal)", async () => {
    // Este e o teste que fecha a corrente: `track()` -> `consent-token` ->
    // `api.pedirTokenConsentimento` -> envio do evento -> backend. Sem token no
    // pedido, o backend responde `registrado: false` com HTTP 202 - o defeito
    // silencioso que este bloco existe para impedir. Interceptamos o `fetch`
    // para inspecionar o que saiu de fato, e nao o que deveria ter saido.
    const { track } = await import("../lib/analytics");
    const original = globalThis.fetch;
    const pedidos: Array<{ url: string; init: RequestInit }> = [];
    globalThis.fetch = (async (entrada: string | URL | Request, init?: RequestInit) => {
      const url = typeof entrada === "string" ? entrada : String(entrada);
      if (url.includes("/api/metricas/eventos/")) {
        pedidos.push({ url, init: init ?? {} });
        // Resposta falsa de proposito: aqui o que importa e o que foi enviado.
        return new Response(JSON.stringify({ registrado: true }), {
          status: 201,
          headers: { "Content-Type": "application/json" },
        });
      }
      return original(entrada as string, init);
    }) as typeof fetch;

    try {
      // Primeiro evento da sessao: nao ha token, entao ele vai para a fila e so
      // e despachado quando o emissor responder.
      const aceito = track({ tipo: "page_view", sessao: SESSAO });
      expect(aceito).toBe(true);

      const limite = Date.now() + 10_000;
      while (Date.now() < limite && pedidos.length === 0) {
        await new Promise((r) => setTimeout(r, 200));
      }

      expect(pedidos.length).toBeGreaterThan(0);
      const cabecalhos = (pedidos[0].init.headers ?? {}) as Record<string, string>;
      const token = cabecalhos["X-Consent-Token"];
      expect(token).toBeTruthy();
      expect(String(token).split(".")).toHaveLength(3);
      // O corpo do evento NAO leva o token (o caminho preferido e o header).
      expect(String(pedidos[0].init.body)).not.toContain(String(token));
    } finally {
      globalThis.fetch = original;
    }
  });

  it("o evento com token e aceito de verdade pelo backend", async () => {
    const { garantirToken } = await import("../lib/consent-token");
    const token = await garantirToken(SESSAO);
    const { json, status } = await postar({ ...EVENTO, path: "/" }, token ?? undefined);
    expect(status).toBe(201);
    expect(json.registrado).toBe(true);
  });
});
