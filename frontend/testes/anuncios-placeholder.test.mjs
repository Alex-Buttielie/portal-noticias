/**
 * M-05: em produção, nenhum texto técnico ("Google AdSense"/"slot {id}")
 * pode aparecer para o leitor quando não há anúncio para mostrar. Fora de
 * produção, o placeholder de debug continua (ajuda quem está codando a ver
 * o espaço reservado).
 *
 * `mostrarPlaceholderDebug` (lib/anuncios.ts) é a decisão pura que
 * `components/AdsSlot.tsx` usa — testada aqui sem precisar de DOM/hooks/
 * providers (o componente real depende de `useAuth`/`usePremiumAtivo`,
 * que exigem contexto de React Query/Auth fora do escopo deste runner de
 * teste em Node puro).
 */
import test from "node:test";
import assert from "node:assert/strict";

import "./hooks.mjs";
import { mostrarPlaceholderDebug } from "../lib/anuncios.ts";

test("produção: placeholder de debug NÃO aparece", () => {
  assert.equal(mostrarPlaceholderDebug("production"), false);
});

test("desenvolvimento: placeholder de debug aparece", () => {
  assert.equal(mostrarPlaceholderDebug("development"), true);
});

test("teste (NODE_ENV=test): placeholder de debug aparece", () => {
  assert.equal(mostrarPlaceholderDebug("test"), true);
});

test("NODE_ENV indefinido (ex. alguns runners locais): placeholder de debug aparece (nunca some por engano fora de produção)", () => {
  assert.equal(mostrarPlaceholderDebug(undefined), true);
});
