/**
 * M-07: "Economize X%" em `/planos` tem que vir do preço/duração REAIS dos
 * planos pagos ativos — nunca um número fixo no código.
 */
import test from "node:test";
import assert from "node:assert/strict";

import "./hooks.mjs";
import { calcularDestaquePlanos } from "../lib/planos.ts";

function plano(overrides) {
  return { id: 1, nome: "Premium", preco: "0", duracao_dias: 30, ativo: true, ...overrides };
}

test("1 plano pago: sem base de comparação, nenhuma economia nem destaque", () => {
  const [p] = calcularDestaquePlanos([plano({ id: 1, nome: "Premium Anual", preco: "30.00", duracao_dias: 365 })]);
  assert.equal(p.economiaPercent, null);
  assert.equal(p.destaque, false);
  assert.ok(Math.abs((p.custoPorDia ?? 0) - 30 / 365) < 1e-9);
});

test("2 planos pagos (semestral R$20/180d, anual R$30/365d): anual é mais barato por dia e ganha destaque + economia", () => {
  const semestral = plano({ id: 1, nome: "Premium Semestral", preco: "20.00", duracao_dias: 180 });
  const anual = plano({ id: 2, nome: "Premium Anual", preco: "30.00", duracao_dias: 365 });
  const [resSemestral, resAnual] = calcularDestaquePlanos([semestral, anual]);

  const custoSemestral = 20 / 180;
  const custoAnual = 30 / 365;
  assert.ok(custoAnual < custoSemestral, "pré-condição do teste: anual deve ser mais barato por dia que semestral");

  assert.equal(resSemestral.destaque, false);
  assert.equal(resSemestral.economiaPercent, null);

  assert.equal(resAnual.destaque, true);
  const economiaEsperada = Math.round((1 - custoAnual / custoSemestral) * 100);
  assert.equal(resAnual.economiaPercent, economiaEsperada);
  assert.ok(resAnual.economiaPercent > 0, "o plano mais barato por dia deve ter economia positiva");
});

test("3 planos ativos no banco (free + semestral + anual): free não entra no cálculo de economia (só planos pagos)", () => {
  // `app/planos/page.tsx` filtra o `free` antes de chamar
  // `calcularDestaquePlanos` — este teste prova que, SE o free entrasse por
  // engano (preco "0.00", duracao_dias curta ou 0), ele não quebra o
  // cálculo nem assume o destaque por ter o menor preço absoluto (o que
  // seria errado: destaque é por CUSTO POR DIA, não por preço total).
  const free = plano({ id: 0, nome: "Free", preco: "0.00", duracao_dias: 0 });
  const semestral = plano({ id: 1, nome: "Premium Semestral", preco: "20.00", duracao_dias: 180 });
  const anual = plano({ id: 2, nome: "Premium Anual", preco: "30.00", duracao_dias: 365 });

  const resultado = calcularDestaquePlanos([semestral, anual]); // free já filtrado fora, como a página faz
  assert.equal(resultado.length, 2);
  assert.equal(resultado.find((p) => p.nome === "Premium Anual").destaque, true);

  // Prova adicional: se o free fosse passado (duracao_dias=0), seu
  // custoPorDia é `null` e ele nunca entra na comparação nem quebra o cálculo.
  const comFreeMisturado = calcularDestaquePlanos([free, semestral, anual]);
  const freeResultado = comFreeMisturado.find((p) => p.nome === "Free");
  assert.equal(freeResultado.custoPorDia, null);
  assert.equal(freeResultado.destaque, false);
  assert.equal(comFreeMisturado.find((p) => p.nome === "Premium Anual").destaque, true);
});

test("0 planos pagos: não quebra, devolve lista vazia", () => {
  assert.deepEqual(calcularDestaquePlanos([]), []);
});

test("preço não numérico não quebra o cálculo (custoPorDia null, sem exceção)", () => {
  const [p] = calcularDestaquePlanos([plano({ preco: "não é número", duracao_dias: 30 })]);
  assert.equal(p.custoPorDia, null);
});
