// Inicialização do Sentry no SERVIDOR do Next (standalone) — critérios 6, 19, 20.
//
// Carregado por `instrumentation.ts::register()` no runtime `nodejs`. O SDK 10
// não carrega mais `sentry.server.config.ts` sozinho (ele apenas avisa): a
// inicialização precisa estar no hook de instrumentação do Next, e é por isso
// que `instrumentation.ts` existe.
//
// CANAL DE RELEASE — o lado servidor é o oposto do navegador, e de propósito:
//
// * O artefato `output: "standalone"` é o MESMO arquivo para dev, homolog e
//   produção (a VPS hospeda os três ambientes). Então, no servidor, ambiente e
//   release têm de vir de VARIÁVEL DE RUNTIME: `SENTRY_ENVIRONMENT` e
//   `SENTRY_RELEASE`. Um `NEXT_PUBLIC_*` aqui seria congelado no build e os
//   três ambientes reportariam o mesmo release — que é exatamente o erro que
//   quebra alerta e correlação.
// * O fallback para `NEXT_PUBLIC_SENTRY_*` existe para o build local e para
//   qualquer deploy que não passe a variável de runtime: o valor embutido no
//   bundle é o SHA do build, que é a melhor resposta disponível, e é melhor do
//   que a string `local` que o backend usaria como último recurso.
// * O `SENTRY_AUTH_TOKEN` (upload de source map) NÃO aparece aqui: é segredo
//   de build, vive só no stage de build do Docker, e nunca chega ao runtime.

import * as Sentry from "@sentry/nextjs";
import {
  ambienteDe,
  criarOpcoesSentry,
  releaseDe,
  type LeituraAmbiente,
} from "@/lib/sentry-opcoes";
import { ehVerdadeiro } from "@/lib/observabilidade";

/**
 * `SENTRY_TECHNICAL_CONSENT_DEFAULT` — o mesmo nome e o mesmo default (`false`)
 * que o backend já usa (`backend/config/observability.py`), pelo mesmo motivo:
 * o servidor do Next **não tem como saber** o consentimento de um visitante
 * (a categoria `tecnico` não é sincronizada com o backend; ver o "Limite
 * conhecido" em `lib/cookie-consent.ts`). Inventar um header ou um cookie
 * agora seria um controle decorativo.
 *
 * Consequência honesta: com o default, o Sentry do servidor fica **desligado**
 * (fail-closed) e erros de renderização do SSR não chegam a lugar nenhum até
 * alguém decidir, explicitamente, ligar isso. Essa decisão é humana e está
 * registrada como pendência — não é um detalhe de configuração.
 */
const CONSENTIMENTO_PADRAO = ehVerdadeiro(process.env.SENTRY_TECHNICAL_CONSENT_DEFAULT);

const LEITURA_RUNTIME: LeituraAmbiente = (nome) => {
  // Literais por extenso: `process.env` é lido em runtime no bundle do
  // servidor, e a precedência é runtime > build.
  if (nome === "SENTRY_ENVIRONMENT") return process.env.SENTRY_ENVIRONMENT;
  if (nome === "NEXT_PUBLIC_SENTRY_ENVIRONMENT") return process.env.NEXT_PUBLIC_SENTRY_ENVIRONMENT;
  if (nome === "SENTRY_RELEASE") return process.env.SENTRY_RELEASE;
  if (nome === "RELEASE_SHA") return process.env.RELEASE_SHA;
  if (nome === "GIT_SHA") return process.env.GIT_SHA;
  if (nome === "NEXT_PUBLIC_SENTRY_RELEASE") return process.env.NEXT_PUBLIC_SENTRY_RELEASE;
  return undefined;
};

const DSN =
  process.env.SENTRY_DSN ||
  process.env.NEXT_PUBLIC_SENTRY_DSN ||
  "";

if (DSN) {
  const opcoes = criarOpcoesSentry({
    dsn: DSN,
    ambiente: ambienteDe(LEITURA_RUNTIME, [
      "SENTRY_ENVIRONMENT",
      "NEXT_PUBLIC_SENTRY_ENVIRONMENT",
    ]),
    release: releaseDe(LEITURA_RUNTIME, [
      "SENTRY_RELEASE",
      "RELEASE_SHA",
      "GIT_SHA",
      "NEXT_PUBLIC_SENTRY_RELEASE",
    ]),
    consentidoNoInicio: CONSENTIMENTO_PADRAO,
    // O servidor não tem o registro de consentimento por visitante; a
    // decisão é do operador e por isso é constante aqui. Ainda assim o
    // portão continua sendo `beforeSend`, então desligar a variável e
    // reiniciar o processo fecha o envio imediatamente.
    consentidoAgora: () => CONSENTIMENTO_PADRAO,
  });
  // `OpcoesSentry` é estrutural e não importa o tipo do SDK de propósito (o
  // módulo de política é puro e testável sem o pacote). O cast fica na
  // fronteira, em um lugar só.
  Sentry.init(opcoes as unknown as Parameters<typeof Sentry.init>[0]);
}

export {};
