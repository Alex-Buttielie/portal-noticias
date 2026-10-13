/**
 * H-01 (run 20261013-1048-home-radar-central-ux, Bloco H) — lógica pura de
 * avanço circular do `ManchetePrincipalSlider`. Testado sem montar nenhum
 * componente React nem depender de `setInterval`/DOM (ver
 * lib/slider.ts::proximoIndiceCircular).
 */
import test from "node:test";
import assert from "node:assert/strict";

import "./hooks.mjs";
import { proximoIndiceCircular } from "../lib/slider.ts";

test("avança um índice dentro dos limites sem dar a volta", () => {
  assert.equal(proximoIndiceCircular(0, 5, 1), 1);
  assert.equal(proximoIndiceCircular(1, 5, 1), 2);
  assert.equal(proximoIndiceCircular(3, 5, 1), 4);
});

test("dá a volta para o início depois do último slide (autoplay)", () => {
  assert.equal(proximoIndiceCircular(4, 5, 1), 0);
});

test("'anterior' (delta negativo) dá a volta para o último slide a partir do primeiro", () => {
  assert.equal(proximoIndiceCircular(0, 5, -1), 4);
  assert.equal(proximoIndiceCircular(2, 5, -1), 1);
});

test("delta 0 normaliza um índice arbitrário para dentro de [0, total) — usado pela navegação manual (clique num indicador)", () => {
  assert.equal(proximoIndiceCircular(7, 5, 0), 2);
  assert.equal(proximoIndiceCircular(-1, 5, 0), 4);
  assert.equal(proximoIndiceCircular(0, 5, 0), 0);
});

test("total<=0 nunca aponta para um slide inexistente", () => {
  assert.equal(proximoIndiceCircular(0, 0, 1), 0);
  assert.equal(proximoIndiceCircular(3, -1, 1), 0);
});

test("com um único slide (total=1), qualquer delta sempre devolve 0", () => {
  for (const delta of [-3, -1, 0, 1, 3]) {
    assert.equal(proximoIndiceCircular(0, 1, delta), 0);
  }
});

test("é periódico: avançar `total` vezes volta ao índice de partida — prova de que o 'carrossel' fecha o ciclo sem pular nem repetir slide", () => {
  const total = 5;
  let indice = 0;
  for (let i = 0; i < total; i += 1) {
    indice = proximoIndiceCircular(indice, total, 1);
  }
  assert.equal(indice, 0);
});
