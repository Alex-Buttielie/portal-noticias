/**
 * Resolver para os testes em Node puro.
 *
 * O frontend é compilado pelo Next, que entende o alias `@/` (tsconfig
 * `paths`) e resolve importações sem extensão (`./site`). O `node:test`
 * não entende nenhum dos dois. Este hook faz as duas resoluções de forma
 * síncrona e sem dependência externa — o objetivo dos testes é ser
 * executáveis no CI sem runner adicional (o projeto não tem vitest/jest
 * nesta base).
 */
import { registerHooks } from "node:module";
import { pathToFileURL, fileURLToPath } from "node:url";
import fs from "node:fs";
import path from "node:path";

const RAIZ = path.resolve(import.meta.dirname, "..");

/** Ordem de tentativa: como o `moduleResolution: bundler` do tsconfig. */
const EXTENSOES = ["", ".ts", ".tsx", ".mts", ".js", ".mjs", "/index.ts", "/index.tsx"];

function existeArquivo(base) {
  for (const extensao of EXTENSOES) {
    const candidato = String(base + extensao);
    if (fs.existsSync(candidato) && fs.statSync(candidato).isFile()) {
      return pathToFileURL(candidato).href;
    }
  }
  return null;
}

registerHooks({
  resolve(specifier, context, nextResolve) {
    if (specifier.startsWith("@/")) {
      const url = existeArquivo(path.join(RAIZ, specifier.slice(2)));
      if (url) return { url, shortCircuit: true, format: undefined };
    }
    if (specifier.startsWith("./") || specifier.startsWith("../")) {
      const pai = context.parentURL ? path.dirname(fileURLToPath(context.parentURL)) : RAIZ;
      const url = existeArquivo(path.resolve(pai, specifier));
      if (url) return { url, shortCircuit: true, format: undefined };
    }
    return nextResolve(specifier, context);
  },
});
