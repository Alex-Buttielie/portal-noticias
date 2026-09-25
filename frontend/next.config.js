const { withSentryConfig } = require("@sentry/nextjs/config");

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: "standalone",
  // Sem isso o Next devolve 308 para /api/feed/ -> /api/feed ANTES do
  // handler em app/api/[...path]/route.ts ser executado (trailing slash
  // normalization). O proxy perderia a barra final e cairia num loop
  // 308 (Next) <-> 301 (Django APPEND_SLASH).
  skipTrailingSlashRedirect: true,
  experimental: {
    // Hook `instrumentation.ts` (Next 14.2). O `withSentryConfig` abaixo já
    // liga isso, mas declarar aqui deixa o arquivo que depende dele
    // (`instrumentation.ts`) legível sem precisar saber do efeito colateral.
    instrumentationHook: true,
  },
};

/**
 * `withSentryConfig` é aplicado por FORA, preservando integralmente a
 * `nextConfig` acima — em especial `output: "standalone"`, que é o que o
 * `frontend/Dockerfile` e o `infra/standalone/run-standalone.sh` (Bloco C1)
 * esperam. O plugin adiciona os plugins/loaders dele; não substitui a config.
 *
 * Opções do build (critério 20):
 * - `silent: true` — o `sentry-cli` roda em CADA build, inclusive no build
 *   local e no build sem credencial. O ruído de "não achei token" não é erro,
 *   e `--silent` não esconde falha real: o upload com token corrompido ainda
 *   derruba o build.
 * - `release.name` = SHA injetado pelo build. `resolveReleaseName` usa
 *   `getSentryRelease()` (a `SENTRY_RELEASE` do build) e cai no SHA do git se
 *   ela não existir, então a release dos source maps é a mesma dos eventos.
 * - `sourcemaps.deleteSourcemapsAfterUpload: false` — o default do SDK é
 *   APAGAR os `.map` depois do upload. Num `standalone` o `.next/server` é
 *   copiado para a imagem final e o `run-standalone.sh` do Bloco C1 valida a
 *   release; apagar arquivos do artefato aqui introduziria uma diferença
 *   entre "build local" e "build com credencial" que ninguém procura depois.
 * - `telemetry: false` — o SDK manda telemetria de uso anônima do próprio
 *   `sentry-cli` durante o build. Build não é o lugar para isso.
 * - `organization`/`project` ficam de fora de propósito: são lidos de
 *   `SENTRY_ORG`/`SENTRY_PROJECT` no ambiente de build, e hardcodar aqui
 *   criaria uma segunda fonte de verdade. Sem `SENTRY_AUTH_TOKEN` o upload é
 *   pulado com aviso — que é o comportamento correto em dev e em build sem
 *   credencial.
 */
module.exports = withSentryConfig(nextConfig, {
  silent: true,
  telemetry: false,
  sourcemaps: {
    deleteSourcemapsAfterUpload: false,
  },
});
