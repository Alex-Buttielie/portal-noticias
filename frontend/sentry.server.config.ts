// Sentry server opcional — mesmo comportamento do client.
const dsn = process.env.NEXT_PUBLIC_SENTRY_DSN || process.env.SENTRY_DSN;
if (dsn) {
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const Sentry = require("@sentry/nextjs");
    Sentry.init({ dsn, tracesSampleRate: 0.1, enabled: true });
  } catch (e) {
    console.warn("[sentry] DSN setado mas @sentry/nextjs não instalado — ignorando", e);
  }
}

export {};
