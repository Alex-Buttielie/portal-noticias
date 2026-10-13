/**
 * M-03: notícia sem resumo próprio não é indexada.
 *
 * `robotsNoticiaSemResumo` é a função pura usada por
 * `app/noticia/[id]/page.tsx` (`generateMetadata`) — testada diretamente
 * para não depender de rede/servidor Next (ver padrão em
 * `lib/paginas-editoriais.ts` / `classificarErroPaginaEditorial`).
 */
import test from "node:test";
import assert from "node:assert/strict";

import { robotsNoticiaSemResumo } from "../lib/seo.ts";

test("resumo vazio gera noindex, follow", () => {
  assert.deepEqual(robotsNoticiaSemResumo(""), { index: false, follow: true });
});

test("resumo ausente (undefined/null) gera noindex, follow", () => {
  assert.deepEqual(robotsNoticiaSemResumo(undefined), { index: false, follow: true });
  assert.deepEqual(robotsNoticiaSemResumo(null), { index: false, follow: true });
});

test("resumo só com espaços conta como vazio", () => {
  assert.deepEqual(robotsNoticiaSemResumo("   "), { index: false, follow: true });
});

test("resumo com conteúdo não altera o robots (indexável)", () => {
  assert.equal(robotsNoticiaSemResumo("Resumo real da notícia."), undefined);
});
