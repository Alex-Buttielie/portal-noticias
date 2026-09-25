import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

/**
 * Suíte de testes do frontend (run 20260925-1020-observabilidade, critério 39).
 *
 * `environment: "node"` é uma escolha, não um atalho: os testes cobrem
 * **lógica pura** — normalização de request id, redação, decisões de
 * consentimento, janela de stale, ciclo de vida do token de consentimento,
 * política do Sentry e a decisão de quebra de cache. Nada disso precisa de DOM,
 * e `node` mantém a suíte rápida e sem `@testing-library`/`jsdom` no bundle de
 * desenvolvimento.
 *
 * O alias `@/` é o mesmo de `tsconfig.json` (`paths`). Sem ele, um teste que
 * importa `sentry.server.config.ts` — que usa alias, como todo o resto do
 * projeto — falharia por resolução, e a saída errada seria trocar o alias por
 * caminho relativo no arquivo de produção: mexer no código testado para
 * agradar o teste.
 *
 * O que NÃO é coberto aqui está escrito nas notas do bloco: o comportamento de
 * DOM (error boundary, banner de consentimento) continua sem suíte
 * automatizada, e isso é pendência declarada, não esquecimento.
 *
 * `include` fica explícito: `*.test.ts` só, para que um arquivo de fixture
 * solto no diretório não vire um "teste sem asserção" que dá verde.
 */
export default defineConfig({
  resolve: {
    alias: {
      "@": fileURLToPath(new URL(".", import.meta.url)),
    },
  },
  test: {
    environment: "node",
    include: ["testes/**/*.test.ts"],
    reporters: ["default"],
  },
});
