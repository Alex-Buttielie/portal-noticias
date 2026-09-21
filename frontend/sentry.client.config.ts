// Sentry frontend opcional — só inicializa se DSN estiver configurado.
// Não quebra build quando NEXT_PUBLIC_SENTRY_DSN vazio ou @sentry/nextjs não instalado.
// Para ativar: npm i @sentry/nextjs e definir NEXT_PUBLIC_SENTRY_DSN no .env
const dsn = process.env.NEXT_PUBLIC_SENTRY_DSN;
if (dsn) {
  try {
    // require dinâmico para não falhar resolve em build sem pacote
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const Sentry = require("@sentry/nextjs");
    Sentry.init({
      dsn,
      tracesSampleRate: 0.1,
      enabled: true,
    });
  } catch (e) {
    console.warn("[sentry] NEXT_PUBLIC_SENTRY_DSN setado mas @sentry/nextjs não instalado — ignorando", e);
  }
}

export {};
