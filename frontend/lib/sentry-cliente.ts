/**
 * Inicialização e uso do Sentry **no navegador** (critérios 4, 5, 6, 20, 27).
 *
 * Este módulo é a casca de runtime; a política (redação, consentimento,
 * ambiente/release) está em `lib/sentry-opcoes.ts`, que é puro e testável.
 * Aqui ficam só as três coisas que dependem de `window`, do relógio e do SDK.
 *
 * ## Fail-closed em duas camadas
 *
 * 1. **Sem DSN ou sem consentimento técnico na carga**, o SDK **nem é
 *    carregado** — não há chunk, não há listener global, não há integração de
 *    tracing. O bundle do portal não paga por telemetria que ninguém autorizou.
 * 2. **Com o SDK carregado**, `beforeSend`/`beforeSendTransaction`
 *    reavaliam o consentimento **a cada evento** (`lib/sentry-opcoes.ts`).
 *    É essa camada que faz a revogação valer no instante em que o visitante
 *    desliga a categoria, sem reinstalar nada.
 *
 * `Sentry.init` é chamado **no máximo uma vez** por sessão do navegador. O
 * SDK v10 avisa no console quando `init` é chamado duas vezes, e esse aviso
 * apareceria justamente no instante em que a pessoa aceita o diagnóstico — o
 * pior lugar possível para poluir o console. Por isso o caminho é: na carga,
 * consentimento já concedido -> `init`; sem consentimento -> escuta o evento
 * de consentimento e chama `init` na primeira concessão.
 */

import { consentimentoTecnico, EVENTO_CONSENTIMENTO_ALTERADO } from "./cookie-consent";
import {
  ambienteDe,
  criarOpcoesSentry,
  releaseDe,
  SERVICO_FRONTEND,
  type LeituraAmbiente,
} from "./sentry-opcoes";
import { semControle } from "./observabilidade";

/**
 * Canal build -> browser do release e do ambiente.
 *
 * `NEXT_PUBLIC_*` é **substituído por literal no bundle** no momento do build:
 * no `output: "standalone"` isso é irreversível (o artefato é o mesmo arquivo
 * para dev, homolog e produção), e é justamente isso que se quer para o
 * release: o release que o navegador reporta é, por construção, o SHA do
 * código que ele está executando. Um release por variável de runtime seria
 * mentiroso no bundle client.
 *
 * O preço desta escolha é declarado aqui: **trocar de release exige rebuild**,
 * e o mesmo valor precisa ser passado ao build da API para que
 * `X-Release` (do Django) e `release` (do Sentry) casem. O lado servidor usa o
 * canal de runtime (`SENTRY_RELEASE`) com este valor embutido como fallback —
 * ver `sentry.server.config.ts`.
 *
 * Os literais são escritos por extenso de propósito: o Next só substitui
 * `process.env.NEXT_PUBLIC_X` quando a propriedade aparece escrita assim; uma
 * leitura por índice (`process.env[nome]`) passaria ilesa para dentro do
 * bundle e viraria `undefined` em produção.
 */
const LEITURA_BUILD: LeituraAmbiente = (nome) => {
  if (nome === "NEXT_PUBLIC_SENTRY_ENVIRONMENT") return process.env.NEXT_PUBLIC_SENTRY_ENVIRONMENT;
  if (nome === "NEXT_PUBLIC_SENTRY_RELEASE") return process.env.NEXT_PUBLIC_SENTRY_RELEASE;
  return undefined;
};

const NAMES_AMBIENTE = ["NEXT_PUBLIC_SENTRY_ENVIRONMENT"];
const NAMES_RELEASE = ["NEXT_PUBLIC_SENTRY_RELEASE"];

/**
 * DSN do browser. **Não é segredo**: por definição ele vai embutido no bundle
 * e a chave pública do projeto está no próprio DSN. O que é segredo é o
 * `SENTRY_AUTH_TOKEN` de upload de source map, que só existe no build.
 */
export const DSN_CLIENTE = process.env.NEXT_PUBLIC_SENTRY_DSN || "";

/** Release/ambiente efetivamente usados no browser (para exibir e para log). */
export const AMBIENTE_CLIENTE = ambienteDe(LEITURA_BUILD, NAMES_AMBIENTE);
export const RELEASE_CLIENTE = releaseDe(LEITURA_BUILD, NAMES_RELEASE);

/** Forma mínima do SDK que este módulo usa — evita tipar o pacote inteiro. */
type SentryMinimo = {
  init: (opcoes: unknown) => unknown;
  captureException: (erro: unknown, contexto?: Record<string, unknown>) => string;
  captureMessage: (mensagem: string, nivel?: string) => string;
  close: (tempo?: number) => PromiseLike<boolean>;
};

let sdk: SentryMinimo | null = null;
let iniciando = false;
let escutando = false;

/** `true` quando o SDK está carregado E ativo neste navegador. */
export function sentryAtivo(): boolean {
  return sdk !== null;
}

/**
 * Carrega e inicializa o SDK — uma única vez, e só se já houver consentimento
 * técnico. Seguro para chamar várias vezes (o `error.tsx` chama a cada erro).
 */
export async function iniciarSentryCliente(): Promise<boolean> {
  if (sdk || iniciando) return sdk !== null;
  if (!DSN_CLIENTE) return false;
  if (!consentimentoTecnico()) {
    // Fail-closed: sem a categoria de diagnóstico, o SDK não é nem baixado.
    return false;
  }
  iniciando = true;
  try {
    const modulo = (await import("@sentry/nextjs")) as unknown as SentryMinimo;
    modulo.init(
      criarOpcoesSentry({
        dsn: DSN_CLIENTE,
        ambiente: AMBIENTE_CLIENTE,
        release: RELEASE_CLIENTE,
        consentidoNoInicio: true,
        // Reavaliado por evento: revogar o consentimento para o envio aqui
        // mesmo, sem recarregar a página.
        consentidoAgora: () => consentimentoTecnico(),
      })
    );
    sdk = modulo;
    return true;
  } catch {
    // Falha de carga/inicialização do SDK não pode derrubar a aplicação: o
    // portal continua funcionando sem telemetria, que é o modo degradado
    // correto.
    return false;
  } finally {
    iniciando = false;
  }
}

/**
 * Fica ouvindo a mudança de preferências de cookies. Entrada da decisão
 * "revisitar o consentimento liga o SDK": o evento é disparado por
 * `lib/cookie-consent.ts` em toda gravação de escolha.
 */
export function observarConsentimentoTecnico(): void {
  if (typeof window === "undefined" || escutando) return;
  escutando = true;
  window.addEventListener(EVENTO_CONSENTIMENTO_ALTERADO, () => {
    if (consentimentoTecnico()) {
      void iniciarSentryCliente();
      return;
    }
    // Revogação: o `beforeSend` já recusa tudo a partir do próximo evento.
    // Fechar o transporte aqui é o que garante que nada que já estava em voo
    // (buffer do transporte) saia depois da revogação.
    const atual = sdk;
    sdk = null;
    if (atual) {
      try {
        void atual.close(2000);
      } catch {
        // Encerrar o cliente nunca pode virar erro visível.
      }
    }
  });
}

/** Valor seguro para tag: sem controle e curto. */
function tagSeguro(valor: unknown, limite = 200): string {
  return semControle(valor == null ? "" : String(valor)).slice(0, limite);
}

/**
 * Captura uma exceção do browser **apenas** com consentimento técnico
 * (critérios 4 e 27).
 *
 * Devolve `false` quando nada foi enviado — o chamador (`app/error.tsx`,
 * `app/global-error.tsx`) usa isso para não afirmar ao visitante que o erro
 * "já está sendo analisado" quando nenhum envio aconteceu.
 *
 * `ApiError` é reconhecido por **forma** (`requestId`), não por `instanceof`:
 * o boundary pode estar no bundle que não compartilha a classe, e a
 * correlação por request id é o que precisa sobreviver a isso.
 */
export function capturarErroTecnico(
  erro: unknown,
  contexto: { origem?: string } = {}
): boolean {
  if (!consentimentoTecnico()) return false;
  if (!sdk) {
    // Ainda não carregado (primeira visita sem consentimento, ou o import
    // ainda está em voo). Tentamos iniciar e devolvemos `false`: prometer
    // captura sem SDK seria mentira.
    void iniciarSentryCliente();
    return false;
  }
  try {
    const requestId = (erro as { requestId?: string | null } | null)?.requestId ?? null;
    sdk.captureException(erro, {
      tags: {
        service: SERVICO_FRONTEND,
        request_id: requestId ? tagSeguro(requestId, 64) : "-",
        origem: tagSeguro(contexto.origem ?? "boundary", 32),
      },
    });
    return true;
  } catch {
    return false;
  }
}

/** Fecha o transporte (usado em teste e no desligamento explícito). */
export async function encerrarSentryCliente(): Promise<void> {
  const atual = sdk;
  sdk = null;
  if (atual) {
    try {
      await atual.close(2000);
    } catch {
      // idempotente por natureza
    }
  }
}
