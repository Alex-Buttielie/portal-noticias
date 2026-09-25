/**
 * Hook de instrumentação do Next (run 20260925-1020-observabilidade,
 * critério 20).
 *
 * O `@sentry/nextjs` v10 **não** carrega `sentry.server.config.ts` sozinho: a
 * inicialização do SDK precisa acontecer dentro de `register()`, e é este
 * arquivo que existe para isso. Sem ele, o servidor do Next simplesmente não
 * reporta nada — e o sintoma é silencioso, que é o pior tipo de defeito de
 * observabilidade.
 *
 * No Next 14.2 o hook só existe com `experimental.instrumentationHook: true`;
 * o `withSentryConfig` liga isso sozinho (ver `next.config.js`), mas a flag
 * fica declarada explicitamente aqui também para que o arquivo não dependa
 * desse efeito colateral.
 *
 * `onRequestError` é convenção do Next 15 (erros de Server Components
 * aninhados). O Next 14.2 simplesmente ignora o export — mantê-lo é
 * retrocompatibilidade gratuita com o próximo upgrade, e satisfaz a checagem
 * do SDK que_avisa quando o arquivo existe sem esse hook.
 */

import * as Sentry from "@sentry/nextjs";

export async function register(): Promise<void> {
  // O portal não usa o runtime `edge` (não há `middleware.ts`), então existe
  // um único caminho de inicialização. Se alguém introduzir edge no futuro, o
  // `sentry.edge.config.ts` entra aqui — e não como substituição silenciosa
  // deste.
  if (process.env.NEXT_RUNTIME === "nodejs") {
    await import("./sentry.server.config");
  }
}

export const onRequestError = Sentry.captureRequestError;
