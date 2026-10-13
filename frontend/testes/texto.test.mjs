/**
 * H-02 (run 20261013-1048-home-radar-central-ux, Bloco H) — prova de que o
 * resumo exibido nos cards da Home não é mais cortado no meio de uma
 * palavra sem indicação nenhuma.
 *
 * BUG REPRODUZIDO AQUI ANTES DA CORREÇÃO: `NewsCard.tsx` usava
 * `resumo.slice(0, max)` puro — um corte por contagem de caracteres, cego a
 * onde as palavras terminam e sem adicionar "…". Os testes abaixo
 * EXECUTAM `truncarPreservandoPalavra` (não leem o texto-fonte) e provam,
 * pela saída:
 *  - textos que já cabem no limite saem INTACTOS, sem "…";
 *  - textos maiores que o limite páram no último espaço (nunca no meio de
 *    uma palavra) e sempre terminam em "…";
 *  - um token sem nenhum espaço (ex. URL) ainda assim é limitado a `max`
 *    caracteres (não cresce sem fim) e ainda tem o indicador de corte.
 */
import test from "node:test";
import assert from "node:assert/strict";

import "./hooks.mjs";
import { truncarPreservandoPalavra } from "../lib/texto.ts";

test("texto menor ou igual ao limite não é alterado nem recebe reticências", () => {
  assert.equal(truncarPreservandoPalavra("Resumo curto.", 140), "Resumo curto.");
  assert.equal(truncarPreservandoPalavra("Exatos dez", 10), "Exatos dez");
});

test("texto maior que o limite para no último espaço — nunca no meio de uma palavra", () => {
  const texto = "O presidente anunciou um pacote de medidas economicas para o proximo semestre";
  const resultado = truncarPreservandoPalavra(texto, 40);

  assert.ok(resultado.endsWith("…"), "deveria terminar com reticências");
  const semReticencias = resultado.slice(0, -1);
  // Nenhuma palavra do resultado trunca uma palavra do texto original: toda
  // palavra do resultado (exceto possivelmente a última) é uma palavra
  // COMPLETA do texto original.
  const palavrasOriginais = new Set(texto.split(" "));
  const palavrasResultado = semReticencias.trim().split(" ");
  for (const palavra of palavrasResultado) {
    assert.ok(
      palavrasOriginais.has(palavra),
      `"${palavra}" não é uma palavra completa do texto original — foi cortada no meio`
    );
  }
  assert.ok(semReticencias.length <= 40);
});

test("respeita o limite mesmo quando o espaço mais próximo descartaria demais (token longo sem espaço)", () => {
  const tokenLongo = "a".repeat(60);
  const resultado = truncarPreservandoPalavra(tokenLongo, 20);

  assert.ok(resultado.endsWith("…"));
  assert.ok(resultado.length <= 21, "20 caracteres + reticências, nunca crescendo sem fim");
});

test("max<=0 devolve string vazia, nunca undefined/erro", () => {
  assert.equal(truncarPreservandoPalavra("qualquer coisa", 0), "");
});

test("texto vazio ou só espaços devolve vazio", () => {
  assert.equal(truncarPreservandoPalavra("", 100), "");
  assert.equal(truncarPreservandoPalavra("   ", 100), "");
});

test("aparar espaços nas pontas antes de medir o limite", () => {
  assert.equal(truncarPreservandoPalavra("  texto com espaco nas pontas  ", 100), "texto com espaco nas pontas");
});
