/**
 * M-02 do contrato / M-04 do plano de monetização: um slot do AdSense por
 * POSIÇÃO (`NEXT_PUBLIC_ADSENSE_SLOT_<POSICAO>`), não mais só por formato.
 *
 * Cada entrada de `SLOT_POR_POSICAO` em `lib/anuncios.ts` tem que ser um
 * acesso ESTÁTICO a `process.env.NEXT_PUBLIC_*` para o Next conseguir
 * inlinar no build do navegador — por isso o módulo precisa ser
 * reimportado (cache-busting por query string) a cada ambiente testado,
 * igual ao padrão de `testes/api-base-ssr.test.mjs`.
 */
import test from "node:test";
import assert from "node:assert/strict";
import path from "node:path";
import { pathToFileURL } from "node:url";

import "./hooks.mjs";

const RAIZ = path.resolve(import.meta.dirname, "..");
const MODULO = path.join(RAIZ, "lib", "anuncios.ts");

async function importarCom(env) {
  const anteriores = {};
  for (const [k, v] of Object.entries(env)) {
    anteriores[k] = process.env[k];
    if (v === undefined) delete process.env[k];
    else process.env[k] = v;
  }
  try {
    const url = pathToFileURL(MODULO).href + `?t=${Math.random()}`;
    return await import(url);
  } finally {
    for (const [k, v] of Object.entries(anteriores)) {
      if (v === undefined) delete process.env[k];
      else process.env[k] = v;
    }
  }
}

test("env da posição definida: resolverSlotAnuncio usa o valor da posição, não o do formato", async () => {
  const { resolverSlotAnuncio } = await importarCom({
    NEXT_PUBLIC_ADSENSE_SLOT_NOTICIA_TOPO: "1111111111",
    NEXT_PUBLIC_ADSENSE_SLOT_HORIZONTAL: "2222222222",
  });
  assert.equal(resolverSlotAnuncio("noticia-topo", "horizontal"), "1111111111");
});

test("env da posição ausente: resolverSlotAnuncio cai no padrão do formato (comportamento anterior preservado)", async () => {
  const { resolverSlotAnuncio } = await importarCom({
    NEXT_PUBLIC_ADSENSE_SLOT_NOTICIA_TOPO: undefined,
    NEXT_PUBLIC_ADSENSE_SLOT_HORIZONTAL: "2222222222",
  });
  assert.equal(resolverSlotAnuncio("noticia-topo", "horizontal"), "2222222222");
});

test("sem env nenhuma, resolverSlotAnuncio devolve string vazia (placeholder, sem quebrar)", async () => {
  const { resolverSlotAnuncio } = await importarCom({
    NEXT_PUBLIC_ADSENSE_SLOT_NOTICIA_TOPO: undefined,
    NEXT_PUBLIC_ADSENSE_SLOT_HORIZONTAL: undefined,
  });
  assert.equal(resolverSlotAnuncio("noticia-topo", "horizontal"), "");
});

test("prop slot explícita tem precedência sobre a env da posição e do formato", async () => {
  const { resolverSlotAnuncio } = await importarCom({
    NEXT_PUBLIC_ADSENSE_SLOT_NOTICIA_TOPO: "1111111111",
    NEXT_PUBLIC_ADSENSE_SLOT_HORIZONTAL: "2222222222",
  });
  assert.equal(resolverSlotAnuncio("noticia-topo", "horizontal", "9999999999"), "9999999999");
});

test("id gerado em loop (categoria-infeed-N) compartilha a env do grupo", async () => {
  const { resolverSlotAnuncio } = await importarCom({
    NEXT_PUBLIC_ADSENSE_SLOT_CATEGORIA_INFEED: "3333333333",
  });
  assert.equal(resolverSlotAnuncio("categoria-infeed-0", "in-feed"), "3333333333");
  assert.equal(resolverSlotAnuncio("categoria-infeed-1", "in-feed"), "3333333333");
  assert.equal(resolverSlotAnuncio("categoria-infeed-final", "in-feed"), "3333333333");
});

test("id fixo que termina em número (home-sidebar-2) NÃO é confundido com o grupo home-sidebar", async () => {
  const { resolverSlotAnuncio } = await importarCom({
    NEXT_PUBLIC_ADSENSE_SLOT_HOME_SIDEBAR: "4444444444",
    NEXT_PUBLIC_ADSENSE_SLOT_HOME_SIDEBAR_2: "5555555555",
  });
  assert.equal(resolverSlotAnuncio("home-sidebar", "retangulo"), "4444444444");
  assert.equal(resolverSlotAnuncio("home-sidebar-2", "retangulo"), "5555555555");
});

test("ids dinâmicos de comunidade (detalhe e feed) resolvem pelo grupo", async () => {
  const { resolverSlotAnuncio } = await importarCom({
    NEXT_PUBLIC_ADSENSE_SLOT_COMUNIDADE_DETALHE: "6666666666",
    NEXT_PUBLIC_ADSENSE_SLOT_COMUNIDADE_FEED: "7777777777",
  });
  assert.equal(resolverSlotAnuncio("comunidade-detalhe-42", "in-feed"), "6666666666");
  assert.equal(resolverSlotAnuncio("comunidade-feed-3", "in-feed"), "7777777777");
});
