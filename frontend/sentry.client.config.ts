// Inicialização do Sentry no NAVEGADOR (run 20260925-1020-observabilidade,
// critérios 4, 5, 6, 20, 27).
//
// Este arquivo é injetado pelo `withSentryConfig` como PRIMEIRO módulo da entry
// `main-app` do App Router (ver `@sentry/nextjs/config`). Por isso ele não
// pode exportar nada de útil e o corpo tem que ser mínimo: importar aqui
// puxa a dependência para dentro do chunk principal.
//
// `instrumentation-client.ts` seria o nome moderno disso, mas é convenção do
// Next 15.3+ e este projeto está em Next 14.2 — o arquivo nunca seria carregado.
// O SDK 10.x ainda suporta `sentry.client.config.ts` e apenas avisa no build
// (aviso aceito e documentado: migrar junto com o upgrade do Next).
//
// A política NÃO está aqui: está em `lib/sentry-opcoes.ts` (puro, testável) e
// o portão de runtime em `lib/sentry-cliente.ts`. Este arquivo só chama o
// portão no instante certo.

import { iniciarSentryCliente, observarConsentimentoTecnico } from "@/lib/sentry-cliente";

// Sem DSN ou sem consentimento técnico na carga, `iniciarSentryCliente` não
// chega a carregar o SDK: fail-closed sem custo de bundle.
void iniciarSentryCliente();

// Recurso ou perda do consentimento depois da carga é tratado aqui, e não na
// primeira renderização: o banner de cookies pode aparecer depois do primeiro
// paint em várias rotas.
observarConsentimentoTecnico();

export {};
