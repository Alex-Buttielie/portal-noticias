/**
 * M-02: `/sitemap.xml` lista só notícias publicáveis E indexáveis (com
 * resumo próprio — mesma regra de M-03/`lib/seo.ts`), cada uma com
 * `lastModified` igual ao timestamp real devolvido pela API, paginando o
 * endpoint leve `GET /api/feed/sitemap/` sem perder nenhuma página.
 */
import test from "node:test";
import assert from "node:assert/strict";

import "./hooks.mjs";

function respostaJson(corpo) {
  return {
    ok: true,
    status: 200,
    headers: { get: () => null },
    text: async () => JSON.stringify(corpo),
  };
}

test("sitemap inclui as rotas fixas e as notícias indexáveis da API, paginando até o fim", async () => {
  const chamadas = [];
  global.fetch = async (url) => {
    chamadas.push(url);
    if (String(url).includes("page=1")) {
      return respostaJson({
        count: 3,
        next: "http://x/api/feed/sitemap/?page=2&page_size=2",
        previous: null,
        results: [
          { tipo: "item", id: 10, categoria: "geral", timestamp: "2026-10-01T10:00:00Z" },
          { tipo: "cluster", id: 11, categoria: "politica", timestamp: "2026-10-02T10:00:00Z" },
        ],
      });
    }
    return respostaJson({
      count: 3,
      next: null,
      previous: "http://x/api/feed/sitemap/?page=1&page_size=2",
      results: [{ tipo: "item", id: 12, categoria: "economia", timestamp: "2026-10-03T10:00:00Z" }],
    });
  };

  const { default: sitemap } = await import(`../app/sitemap.ts?t=${Math.random()}`);
  const resultado = await sitemap();

  // Paginação completa: 2 chamadas (page=1 e page=2), nenhuma página perdida.
  assert.equal(chamadas.length, 2);

  const urlsFixas = resultado.filter((e) => !e.url.includes("/noticia/"));
  assert.ok(urlsFixas.length > 0, "rotas fixas devem continuar presentes");

  const urlsNoticias = resultado.filter((e) => e.url.includes("/noticia/"));
  assert.equal(urlsNoticias.length, 3, "deve incluir as 3 notícias das duas páginas");

  const entradaDez = urlsNoticias.find((e) => e.url.endsWith("/noticia/10"));
  assert.ok(entradaDez, "notícia id=10 deve estar no sitemap");
  assert.equal(
    new Date(entradaDez.lastModified).toISOString(),
    new Date("2026-10-01T10:00:00Z").toISOString(),
    "lastModified deve ser o timestamp real devolvido pela API"
  );
});

test("sitemap não quebra quando a API falha — mantém só as rotas fixas", async () => {
  global.fetch = async () => {
    throw new Error("rede indisponível");
  };

  const { default: sitemap } = await import(`../app/sitemap.ts?t=${Math.random()}`);
  const resultado = await sitemap();

  assert.ok(resultado.length > 0, "rotas fixas devem continuar presentes mesmo sem a API");
  assert.equal(resultado.some((e) => e.url.includes("/noticia/")), false);
});
