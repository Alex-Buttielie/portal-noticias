/**
 * M-08 (run 20261012-1806-monetizacao-sprint1) — o CTA de assinatura dentro
 * da leitura (`LeituraPremium.tsx`) só aparece para Free confirmado; nunca
 * para Premium, nem enquanto o status Premium ainda não é conhecido
 * (`ativo === null`, fail-open — mesma regra que `AdsSlot.tsx` usa para
 * decidir se mostra anúncio).
 *
 * `premiumOuStatusDesconhecido` (lib/premium.ts) é a decisão pura — testada
 * aqui sem DOM/hooks/providers.
 */
import test from "node:test";
import assert from "node:assert/strict";

import "./hooks.mjs";
import { premiumOuStatusDesconhecido } from "../lib/premium.ts";

test("usuário Premium: CTA não aparece (premiumOuStatusDesconhecido true), mesmo com status ativo=true", () => {
  assert.equal(premiumOuStatusDesconhecido(true, true), true);
});

test("usuário Free com status Premium desconhecido (ativo=null, carregando/erro): CTA não aparece — fail-open", () => {
  assert.equal(premiumOuStatusDesconhecido(false, null), true);
});

test("usuário Free com status Premium conhecido (ativo=true ou false): CTA aparece", () => {
  assert.equal(premiumOuStatusDesconhecido(false, true), false);
  assert.equal(premiumOuStatusDesconhecido(false, false), false);
});

test("usuário Premium com status desconhecido: continua não aparecendo (dupla razão para esconder)", () => {
  assert.equal(premiumOuStatusDesconhecido(true, null), true);
});
