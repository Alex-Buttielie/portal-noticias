/**
 * M-10 (run 20261012-1806-monetizacao-sprint1) — patrocínio identificado.
 *
 * O projeto não tem runner de renderização de componente (ver nota em
 * `links-internos.test.mjs`/`paginas-editorial.test.mjs`), então o rótulo
 * "Patrocinado", o `rel="sponsored nofollow noopener"` e as dimensões fixas
 * da imagem são verificados de forma ESTÁTICA sobre o fonte real de
 * `PatrocinioSlot.tsx` — mesmo desenho das guardas de regressão
 * `verificar-consentimento-anuncios.mjs`/`verificar-eventos-analytics.mjs`.
 * O consentimento de `analytics` para o REGISTRO de evento (não para o
 * conteúdo) já é garantido por `track()`/`consentido()` em
 * `lib/analytics.ts`, cobertos pela guarda P1-10 — aqui confirmamos só que
 * `PatrocinioSlot` chama os helpers (`trackPatrocinioView`/
 * `trackPatrocinioClick`) e nunca monta a requisição à mão.
 */
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";

import "./hooks.mjs";
import { TIPOS_EVENTO, montarCorpoEvento } from "../lib/analytics.ts";

const CAMINHO_SLOT = path.resolve(import.meta.dirname, "../components/PatrocinioSlot.tsx");
const FONTE_SLOT = readFileSync(CAMINHO_SLOT, "utf8");

test("patrocinio_view e patrocinio_click fazem parte da taxonomia de eventos", () => {
  assert.ok(TIPOS_EVENTO.includes("patrocinio_view"));
  assert.ok(TIPOS_EVENTO.includes("patrocinio_click"));
});

test("montarCorpoEvento preserva categoria (posicao) e extra (posicao + patrocinio_id) para patrocinio_view", () => {
  const corpo = montarCorpoEvento(
    { tipo: "patrocinio_view", categoria: "radar", extra: { posicao: "radar", patrocinio_id: 7 } },
    "sessao-teste",
    "/radar"
  );
  assert.equal(corpo.tipo, "patrocinio_view");
  assert.equal(corpo.categoria, "radar");
  assert.deepEqual(corpo.extra, { posicao: "radar", patrocinio_id: 7 });
  assert.equal(corpo.path, "/radar");
});

test("montarCorpoEvento preserva patrocinio_click do mesmo jeito", () => {
  const corpo = montarCorpoEvento(
    { tipo: "patrocinio_click", categoria: "newsletter", extra: { posicao: "newsletter", patrocinio_id: 3 } },
    "sessao-teste",
    "/newsletter"
  );
  assert.equal(corpo.tipo, "patrocinio_click");
  assert.deepEqual(corpo.extra, { posicao: "newsletter", patrocinio_id: 3 });
});

test("PatrocinioSlot: rótulo \"Patrocinado\" está sempre no fonte (visível, não condicional por consentimento)", () => {
  assert.match(FONTE_SLOT, /Patrocinado/);
});

test("PatrocinioSlot: link do anunciante usa rel=\"sponsored nofollow noopener\"", () => {
  assert.match(FONTE_SLOT, /rel=["']sponsored nofollow noopener["']/);
});

test("PatrocinioSlot: imagem tem alt (texto_alt do patrocínio, nunca um alt vazio/genérico fixo) e dimensões fixas", () => {
  assert.match(FONTE_SLOT, /alt=\{patrocinio\.texto_alt\}/);
  assert.match(FONTE_SLOT, /width=\{LARGURA_CRIATIVO\}/);
  assert.match(FONTE_SLOT, /height=\{ALTURA_CRIATIVO\}/);
});

test("PatrocinioSlot: sem patrocínio (null) não renderiza nada — não inventa patrocínio nem reserva buraco vazio", () => {
  assert.match(FONTE_SLOT, /if\s*\(\s*!patrocinio\s*\)\s*return null\s*;?/);
});

test("PatrocinioSlot: impressão e clique passam pelos helpers de lib/analytics.ts (nunca um fetch/beacon à mão)", () => {
  assert.match(FONTE_SLOT, /trackPatrocinioView\s*\(/);
  assert.match(FONTE_SLOT, /trackPatrocinioClick\s*\(/);
  assert.doesNotMatch(FONTE_SLOT, /sendBeacon|fetch\(/);
});
