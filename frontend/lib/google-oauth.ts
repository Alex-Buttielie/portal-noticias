/**
 * Login social via Google — orquestração do handshake de 3 passos (P1-05b).
 *
 * POR QUE ESTE MÓDULO EXISTE SEPARADO DE `components/BotaoGoogle.tsx`
 * O componente é React e não pode ser importado em Node puro; este módulo é a
 * parte que decide, e é importado direto pela guarda de regressão
 * (`scripts/verificar-google-oauth.mjs`) para ser exercitada de verdade. O
 * componente só desenha os três estados e repassa o resultado.
 *
 * AS TRÊS REGRAS QUE ESTE ARQUIVO EXISTE PARA CUMPRIR
 *
 * 1. NADA SAI DA MÁQUINA ANTES DO CLIQUE. O Google Identity Services (GIS) é
 *    carregado por injeção de `<script>` criada aqui, dentro de
 *    `carregarGoogleIdentityServices()`, que só é chamada DEPOIS do nonce e
 *    dentro do clique. Não há `<script src="accounts.google.com">` no
 *    `<head>` nem `next/script` em lugar nenhum: o `preconnect` sozinho já
 *    entregaria IP, hora e User-Agent ao Google antes de qualquer consentimento
 *    — foi exatamente por isso que o P1-09/P1-10 também retiraram o
 *    pré-carregamento de anúncios/analytics.
 *
 * 2. O NONCE VEM ANTES E VOLTA EM TODAS AS ETAPAS. O backend emite o
 *    `state`/nonce em `POST /api/auth/google/iniciar/` e o amarra à sessão do
 *    navegador; o MESMO valor precisa voltar ASSINADO no claim `nonce` do
 *    `id_token`, e o `POST /api/auth/google/` precisa reenviá-lo. Sem o par, o
 *    endpoint final é um POST anônimo sem proteção CSRF que devolve um token
 *    de API — ver `backend/identidade/oauth_google.py`.
 *
 * 3. `id_token` NÃO É LOGIN. A única coisa que produz sessão é a resposta 200
 *    de `POST /api/auth/google/` com um `token` não vazio. Receber a
 *    credencial, o nonce vencer, o popup fechar, o backend recusar — nada
 *    disso é sucesso, e `classificarErroGoogle` não tem como devolver
 *    "sucesso" por construção (o tipo de retorno não tem campo de sucesso).
 */

import {
  API_BASE_URL,
  ApiError,
  concluirLoginGoogle,
  iniciarLoginGoogle,
  type RespostaLoginGoogle,
} from "./api";

// ---------------------------------------------------------------------------
// Configuração
// ---------------------------------------------------------------------------

/**
 * `client_id` do OAuth do Google. Vem SEMPRE de `process.env`:
 *
 *  - é configuração de ambiente, não de código-fonte; e
 *  - valor escrito à mão em arquivo versionado é conta de outra pessoa, ou
 *    pior, o `client_id` de produção colado no `develop` e nunca revogado.
 *
 * Em navegador o valor precisa ser público por natureza (o Google envia o
 * `id_token` para o cliente, e o `aud` é conferido contra ele), então o
 * prefixo `NEXT_PUBLIC_` é o mecanismo correto — e, como em todo
 * `NEXT_PUBLIC_*`, ele é embutido no bundle no BUILD. Passar a variável para o
 * processo `web` e refazer o build é o que a habilita em DEV/HOMOLOG/PROD.
 *
 * `NEXT_PUBLIC_GOOGLE_OAUTH_CLIENT_ID` é o mesmo valor de
 * `GOOGLE_OAUTH_CLIENT_ID`, que o backend lê em
 * `backend/config/settings.py` — o backend confere o `aud` do `id_token`
 * contra ele. As duas pontas precisam do MESMO valor; o front não pode
 * "inventar" o seu.
 */
export const GOOGLE_CLIENT_ID = process.env.NEXT_PUBLIC_GOOGLE_OAUTH_CLIENT_ID || "";

/** Host do provedor de identidade. Declarado aqui para a guarda conseguir listar. */
export const ORIGEM_GOOGLE = "https://accounts.google.com";

/** Script do GIS. Injetado só no clique (ver `carregarGoogleIdentityServices`). */
export const SCRIPT_GOOGLE = `${ORIGEM_GOOGLE}/gsi/client`;

/**
 * Teto do botão em estado "carregando" quando nada voltou do popup.
 *
 * O GIS não avisa quando a pessoa fecha o popup, cancela, ou quando o
 * navegador bloqueou a janela: nos três casos simplesmente não chega
 * credencial. A única forma honesta de transformar isso em estado de erro é um
 * prazo. Ele é MENOR que a vida do nonce de propósito: segurar a pessoa por
 * minutos num botão travado é pior do que pedir para ela tentar de novo — e
 * tentar de novo é seguro, porque o passo 1 emite um nonce novo.
 */
export const LIMITE_INTERACAO_MS = 120_000;

/** Vida do nonce quando o backend não manda `expira_em_segundos` utilizável. */
export const NONCE_TTL_PADRAO_SEGUNDOS = 600; // = GOOGLE_OAUTH_NONCE_MAX_AGE_SECONDS

/** Há `client_id` para este ambiente? Sem ele o botão não tem o que mostrar. */
export function googleDisponivel(): boolean {
  return GOOGLE_CLIENT_ID.length > 0;
}

// ---------------------------------------------------------------------------
// Erros
// ---------------------------------------------------------------------------

/**
 * Motivos de falha do login Google. Values estáveis e sem PII: a UI decide o
 * texto por este código, e nenhum valor aqui é um "sucesso" — a lista é de
 * falhas, e é finita.
 */
export type CodigoErroGoogle =
  /** Sem `NEXT_PUBLIC_GOOGLE_OAUTH_CLIENT_ID` no bundle. */
  | "nao_configurado"
  /** 503 do backend: `GOOGLE_OAUTH_CLIENT_ID` ausente no ambiente do Django. */
  | "provedor_nao_configurado"
  /** O passo 1 (nonce) não respondeu — rede, 5xx, 429. */
  | "nonce_indisponivel"
  /** O nonce passou do `expira_em_segundos` enquanto a pessoa estava no popup. */
  | "nonce_expirado"
  /** Nada voltou: popup fechado, cancelado ou bloqueado pelo navegador. */
  | "sem_credencial"
  /** O GIS respondeu com credencial vazia/ausente. */
  | "credencial_invalida"
  /** 400 "Token do Google inválido." — assinatura/aud/exp recusados. */
  | "token_recusado"
  /** 403 de identidade (nonce divergente, e-mail não verificado, …). */
  | "identidade_recusada"
  /** 400 de aceite de termos (conta nova). */
  | "termos_pendentes"
  /** 403 "Conta inativa." */
  | "conta_inativa"
  /** 429 do throttle do DRF. */
  | "muitas_tentativas"
  /** `API_BASE_URL` em outro site: o cookie de sessão não viaja (Lax). */
  | "origem_incorporada"
  /** Sem rede (ApiError 0) ou erro inesperado. */
  | "sem_conexao"
  | "indisponivel";

const MENSAGENS: Record<CodigoErroGoogle, string> = {
  nao_configurado:
    "O login com Google não está disponível neste ambiente. Entre com e-mail e senha.",
  provedor_nao_configurado:
    "O login com Google não está disponível neste ambiente. Entre com e-mail e senha.",
  nonce_indisponivel:
    "Não foi possível iniciar o login com Google. Tente de novo em instantes.",
  nonce_expirado:
    "A janela do login com Google passou do tempo. Clique de novo para recomeçar.",
  sem_credencial:
    "O Google não devolveu a credencial — a janela foi fechada, cancelada ou bloqueada pelo navegador. Permita pop-ups deste site e tente de novo.",
  credencial_invalida:
    "O Google devolveu uma credencial vazia. Tente de novo.",
  token_recusado:
    "O Google recusou a credencial enviada. Tente de novo.",
  identidade_recusada:
    "Não foi possível concluir o login com esta conta. Entre com e-mail e senha.",
  termos_pendentes:
    "É necessário aceitar os termos de uso e a política de privacidade para se cadastrar.",
  conta_inativa: "Conta inativa.",
  muitas_tentativas: "Muitas tentativas. Aguarde um pouco e tente de novo.",
  origem_incorporada:
    "O login com Google não funciona com a API em outro domínio: o cookie de sessão não viaja. Entre com e-mail e senha.",
  sem_conexao:
    "Não foi possível conectar ao servidor. Verifique sua conexão e tente novamente.",
  indisponivel: "Não foi possível concluir o login com Google. Entre com e-mail e senha.",
};

export class ErroGoogle extends Error {
  readonly codigo: CodigoErroGoogle;

  constructor(codigo: CodigoErroGoogle) {
    super(MENSAGENS[codigo]);
    this.name = "ErroGoogle";
    this.codigo = codigo;
  }
}

export function novoErroGoogle(codigo: CodigoErroGoogle): ErroGoogle {
  return new ErroGoogle(codigo);
}

/** Lê o `detail` do DRF (ou o `ApiError.detail` cru) como texto. */
function detalheComoTexto(detalhe: unknown, padrao: string): string {
  if (typeof detalhe === "string" && detalhe.trim()) return detalhe.trim();
  if (detalhe && typeof detalhe === "object") {
    const objeto = detalhe as Record<string, unknown>;
    if (typeof objeto.detail === "string" && objeto.detail.trim()) return objeto.detail.trim();
    const primeira = Object.values(objeto)[0];
    if (Array.isArray(primeira) && typeof primeira[0] === "string") return primeira[0];
  }
  return padrao;
}

/**
 * Converte QUALQUER erro do caminho Google em (código, mensagem) para a UI.
 *
 * O tipo de retorno não tem nenhum campo de sucesso — é impossível, por
 * construção, transformar um erro em "login efetuado" usando esta função. A
 * guarda de regressão exercita a tabela inteira de respostas que o backend
 * pode devolver e afirma que nenhuma delas produz código de sucesso.
 */
export function classificarErroGoogle(erro: unknown): {
  codigo: CodigoErroGoogle;
  mensagem: string;
} {
  if (erro instanceof ErroGoogle) {
    return { codigo: erro.codigo, mensagem: erro.message };
  }
  if (erro instanceof ApiError) {
    const detalhe = detalheComoTexto(erro.detail, erro.message);
    if (erro.status === 0) {
      return { codigo: "sem_conexao", mensagem: MENSAGENS.sem_conexao };
    }
    if (erro.status === 429) {
      const espera = erro.retryAfterSegundos;
      const sufixo = espera && espera > 0 ? ` Tente de novo em ${espera}s.` : "";
      return { codigo: "muitas_tentativas", mensagem: MENSAGENS.muitas_tentativas + sufixo };
    }
    if (erro.status === 503) {
      // `MSG_OAUTH_NAO_CONFIGURADO` do backend: ambiente sem credencial lá.
      return { codigo: "provedor_nao_configurado", mensagem: detalhe || MENSAGENS.provedor_nao_configurado };
    }
    if (erro.status === 400) {
      // Os dois 400 do passo 3 mandam `detail` em texto; o do aceite de termos
      // é o único que fala em "termos", e ele precisa chegar à pessoa porque
      // a ação dela (marcar o checkbox) resolve.
      if (/termos de uso|aceitar os termos/i.test(detalhe)) {
        return { codigo: "termos_pendentes", mensagem: detalhe };
      }
      return { codigo: "token_recusado", mensagem: detalhe || MENSAGENS.token_recusado };
    }
    if (erro.status === 403) {
      if (/conta inativa/i.test(detalhe)) {
        return { codigo: "conta_inativa", mensagem: detalhe };
      }
      // Todo o resto (nonce ausente/inválido/expirado, claim divergente,
      // e-mail não verificado no provedor, conta local sem e-mail confirmado)
      // volta com a MESMA mensagem do backend, de propósito: uma mensagem por
      // motivo transformaria o endpoint em oráculo de "esta conta existe e
      // está verificada".
      return { codigo: "identidade_recusada", mensagem: detalhe || MENSAGENS.identidade_recusada };
    }
    return { codigo: "indisponivel", mensagem: detalhe || MENSAGENS.indisponivel };
  }
  return { codigo: "indisponivel", mensagem: MENSAGENS.indisponivel };
}

// ---------------------------------------------------------------------------
// Coerção e prazo do nonce
// ---------------------------------------------------------------------------

/**
 * O nonce desta tentativa já venceu?
 *
 * Atalho de UX, NÃO de segurança: o backend consome e confere o nonce de
 * qualquer forma (`motivo_recusa_nonce` faz `pop` antes de validar), então
 * recusar aqui não abre nem fecha nenhuma porta. O que ele compra é não mandar
 * um `id_token` válido numa viagem que vai ser recusada com 403 e sem explicar
 * por quê, e não dar a impressão de que a conta da pessoa foi recusada.
 *
 * O prazo vem de `expira_em_segundos`, que é o número que o BACKEND usa
 * (`GOOGLE_OAUTH_NONCE_MAX_AGE_SECONDS`) — não um palpite do front.
 */
export function nonceVenceuEm(
  emitidoEmMs: number,
  expiraEmSegundos: number,
  agoraMs: number
): boolean {
  if (!Number.isFinite(emitidoEmMs) || !Number.isFinite(agoraMs)) return true;
  const ttl =
    Number.isFinite(expiraEmSegundos) && expiraEmSegundos > 0
      ? expiraEmSegundos
      : NONCE_TTL_PADRAO_SEGUNDOS;
  return agoraMs - emitidoEmMs > ttl * 1000;
}

// ---------------------------------------------------------------------------
// Mesma origem: o cookie de sessão precisa viajar
// ---------------------------------------------------------------------------

/**
 * O cookie de sessão do backend chega nesta URL base?
 *
 * `SESSION_COOKIE_SAMESITE = "Lax"` (`backend/config/settings.py:217`) só
 * entrega o cookie em requisição de mesma origem ou de mesmo SITE. "Mesmo
 * site" = mesmo domínio registrável; porta e esquema não contam para o
 * SameSite. Três casos aceitos, por serem os reais deste projeto:
 *   - mesma origem (o navegador chamando `/api/...` no próprio host),
 *   - o mesmo host com porta diferente (`localhost:3000` -> `localhost:8000`,
 *     que é o `next dev`),
 *   - um host sendo subdomínio do outro.
 *
 * Por que isso é um gate e não um comentário: sem o cookie, `POST
 * /api/auth/google/iniciar/` devolve 200 e o passo 3 volta 403 `nonce_ausente`.
 * A pessoa veria "Não foi possível concluir o login com esta conta. Entre com
 * e-mail e senha" — uma falha de configuração vestida de falha de identidade.
 * Aqui ela vira uma mensagem que diz a verdade.
 */
export function cookieDeSessaoChega(urlBase: string, origemDoSite: string): boolean {
  // URL vazia = mesma origem por construção (ver `API_BASE_URL` em `lib/api.ts`).
  if (!urlBase) return true;
  let base: URL;
  let site: URL;
  try {
    base = new URL(urlBase);
    site = new URL(origemDoSite);
  } catch {
    // Base não interpretável: não dá para provar que o cookie viaja, então não
    // se presume que viaja.
    return false;
  }
  if (base.origin === site.origin) return true;
  const hostBase = base.hostname.toLowerCase();
  const hostSite = site.hostname.toLowerCase();
  if (hostBase === hostSite) return true;
  if (hostBase.endsWith(`.${hostSite}`) || hostSite.endsWith(`.${hostBase}`)) return true;
  // Últimos dois rótulos: cobre `a.exemplo.com.br` <-> `b.exemplo.com.br`
  // (ambos `com.br`) sem depender de lista de public suffix — dependência
  // nova está fora do escopo deste item.
  const rotulos = (host: string) => host.split(".");
  const a = rotulos(hostBase);
  const b = rotulos(hostSite);
  const ultimosDois = (partes: string[]) => partes.slice(-2).join(".");
  return a.length >= 2 && b.length >= 2 && ultimosDois(a) === ultimosDois(b);
}

// ---------------------------------------------------------------------------
// Carregamento do Google Identity Services (SÓ no clique)
// ---------------------------------------------------------------------------

interface JanelaGoogle extends Window {
  google?: {
    accounts?: {
      id?: {
        initialize: (config: Record<string, unknown>) => void;
        renderButton: (elemento: HTMLElement, opcoes: Record<string, unknown>) => void;
      };
    };
  };
}

/**
 * Carrega o GIS injetando o `<script>` na mão.
 *
 * Por que injeção manual e não `next/script`: `next/script` resolve
 * `strategy` no carregamento da página (`beforeInteractive` no `<head>`,
 * `afterInteractive`/`lazyOnload` ainda no carregamento) — nenhum deles é
 * "quando a pessoa clicar". Uma importação dinâmica (`import()`) de uma URL
 * absoluta também não serve: o bundler tenta resolver
 * `https://accounts.google.com/gsi/client` no build. Injeção imperativa é
 * literalmente "cria a tag agora".
 *
 * Idempotente e reentrante: a primeira chamada cria a tag e todas as
 * seguintes devolvem a mesma promessa. Uma falha limpa a cache para que o
 * próximo clique tente de novo, em vez de devolver para sempre a mesma
 * promessa já rejeitada.
 */
let carregandoScript: Promise<void> | null = null;

export function carregarGoogleIdentityServices(): Promise<void> {
  if (carregandoScript) return carregandoScript;
  const promessa = new Promise<void>((resolve, reject) => {
    if (typeof document === "undefined" || typeof window === "undefined") {
      reject(novoErroGoogle("indisponivel"));
      return;
    }
    const janela = window as JanelaGoogle;
    if (janela.google?.accounts?.id) {
      resolve();
      return;
    }
    const script = document.createElement("script");
    script.src = SCRIPT_GOOGLE;
    script.async = true;
    script.defer = true;
    script.onload = () => resolve();
    script.onerror = () => reject(novoErroGoogle("indisponivel"));
    document.head.appendChild(script);
  });
  carregandoScript = promessa;
  promessa.catch(() => {
    if (carregandoScript === promessa) carregandoScript = null;
  });
  return promessa;
}

// ---------------------------------------------------------------------------
// O handshake
// ---------------------------------------------------------------------------

export interface OpcoesFluxoGoogle {
  /** Valor do checkbox de termos, enviado tal como está no passo 3. */
  aceiteTermos: boolean;
  /** Onde o botão do Google Identity Services é renderizado. */
  container: HTMLElement;
  /** O nonce foi emitido e o botão do Google já está na tela. */
  aoExibirBotaoGoogle?: () => void;
  /** O nonce venceu enquanto a pessoa estava na tela do Google. */
  aoExpirarNonce?: () => void;
  /**
   * Teto de espera pela credencial. Costura de teste: a guarda de regressão
   * precisa provar que "o popup não devolveu nada" vira erro, e não pode ficar
   * dois minutos esperando. O default é o valor de produção
   * (`LIMITE_INTERACAO_MS`); nenhum caminho de produção passa isto.
   */
  limiteInteracaoMs?: number;
}

/**
 * Resolve a credencial do Google, com prazo.
 *
 * O GIS resolve em modo popup e não tem callback de cancelamento: fechar a
 * janela, cancelar, ou ter o popup bloqueado pelo navegador são a MESMA
 * coisa observável daqui — nada chega. Por isso a promessa só pode ser
 * cumprida pelo callback do GIS ou falhar por prazo, e nunca por "a pessoa
 * cancelou" (o que seria uma mentira sobre o que sabemos).
 */
function obterCredencialGoogle(
  nonce: string,
  container: HTMLElement,
  limiteMs: number,
  aoExibirBotaoGoogle?: () => void
): Promise<string> {
  return new Promise<string>((resolve, reject) => {
    const gapi = (window as JanelaGoogle).google;
    if (!gapi?.accounts?.id) {
      reject(novoErroGoogle("indisponivel"));
      return;
    }
    let encerrado = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const finalizar = (desfecho: () => void) => {
      if (encerrado) return;
      encerrado = true;
      if (timer !== undefined) clearTimeout(timer);
      desfecho();
    };
    timer = setTimeout(
      () => finalizar(() => reject(novoErroGoogle("sem_credencial"))),
      limiteMs
    );
    try {
      gapi.accounts.id.initialize({
        client_id: GOOGLE_CLIENT_ID,
        ux_mode: "popup",
        // O nonce vai no `initialize` E no `renderButton`. O GIS o coloca no
        // claim `nonce` do `id_token`, que é o que o backend confere contra
        // o valor que ele emitiu no passo 1. Sem isto, o passo 3 volta 403.
        nonce,
        callback: (resposta: { credential?: unknown }) => {
          const credencial = resposta?.credential;
          if (typeof credencial !== "string" || credencial.length === 0) {
            finalizar(() => reject(novoErroGoogle("credencial_invalida")));
            return;
          }
          finalizar(() => resolve(credencial));
        },
      });
      container.replaceChildren();
      gapi.accounts.id.renderButton(container, {
        theme: "outline",
        size: "large",
        text: "continue_with",
        nonce,
      });
      aoExibirBotaoGoogle?.();
    } catch {
      finalizar(() => reject(novoErroGoogle("indisponivel")));
    }
  });
}

/**
 * O login Google inteiro, do clique ao token.
 *
 * Única função que resolve com sucesso, e ela resolve **depois** do
 * `POST /api/auth/google/` e **só** se a resposta trouxer um `token` não
 * vazio. Todas as outras saídas lançam `ErroGoogle` — inclusive "o Google
 * respondeu" e "o nonce foi emitido". Um 200 sem token também é falha: tratar
 * resposta sem credencial como login efetuado é a forma mais barata de
 * inventar sessão.
 */
export async function iniciarFluxoGoogle(
  opcoes: OpcoesFluxoGoogle
): Promise<RespostaLoginGoogle> {
  if (!googleDisponivel()) {
    throw novoErroGoogle("nao_configurado");
  }
  if (typeof window !== "undefined" && !cookieDeSessaoChega(API_BASE_URL, window.location.origin)) {
    throw novoErroGoogle("origem_incorporada");
  }

  // ---- PASSO 1: o nonce, ANTES de qualquer contato com o Google ------------
  let pendente: { nonce: string; expira_em_segundos: number };
  try {
    pendente = await iniciarLoginGoogle();
  } catch (erro) {
    if (erro instanceof ApiError) throw erro; // classificado pela UI
    throw novoErroGoogle("nonce_indisponivel");
  }
  if (!pendente || typeof pendente.nonce !== "string" || pendente.nonce.length === 0) {
    throw novoErroGoogle("nonce_indisponivel");
  }
  const ttl = Number(pendente.expira_em_segundos);
  const emitidoEm = Date.now();

  // ---- PASSO 2: só agora o script do Google entra na máquina ---------------
  await carregarGoogleIdentityServices();

  const expirar = setTimeout(() => opcoes.aoExpirarNonce?.(), Math.max(1, ttl > 0 ? ttl : NONCE_TTL_PADRAO_SEGUNDOS) * 1000);
  let idToken: string;
  try {
    idToken = await obterCredencialGoogle(
      pendente.nonce,
      opcoes.container,
      opcoes.limiteInteracaoMs ?? LIMITE_INTERACAO_MS,
      opcoes.aoExibirBotaoGoogle
    );
  } finally {
    clearTimeout(expirar);
  }

  // O nonce venceu enquanto a pessoa estava na tela de consentimento? O passo 3
  // seria recusado com 403 e a mensagem do backend não diz o motivo. Dizer aqui
  // é mais honesto e não muda a decisão do backend, que revalida de qualquer
  // forma.
  if (nonceVenceuEm(emitidoEm, ttl, Date.now())) {
    throw novoErroGoogle("nonce_expirado");
  }

  // ---- PASSO 3: o id_token sozinho NÃO é login -----------------------------
  const resposta = await concluirLoginGoogle({
    id_token: idToken,
    nonce: pendente.nonce,
    aceite_termos: opcoes.aceiteTermos,
  });
  if (!resposta || typeof resposta.token !== "string" || resposta.token.length === 0) {
    throw novoErroGoogle("indisponivel");
  }
  return resposta;
}
