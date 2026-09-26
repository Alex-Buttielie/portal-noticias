/**
 * Publicidade — P1-09 "Free mostra ads; Premium não; fallback Free sem ads".
 *
 * Ponto ÚNICO de decisão e de revogação da saída de anúncio. Antes este módulo
 * não existia: `AdsSlot` e `AdsScript` cada um decidiam sozinho, e a decisão de
 * "este visitante pode ver anúncio?" ficava a cargo de CADA ponto de montagem
 * (`HomeClient`, `RadarClient`, `LeituraPremium`, `categoria/[slug]`, ...).
 * Isso é o que produziu o furo que este run fecha: em `HomeClient` só 5 dos 10
 * slots eram protegidos por `!premiumGeral`, e 6 das 9 páginas que montam
 * `AdsSlot` NÃO conhecem o Premium em lugar nenhum — inclusive a página de
 * leitura da notícia, que é onde o Premium passa mais tempo. Um assinante que
 * tivesse consentido "personalização" via AdSense via a porta da frente.
 *
 * O acordo do programa é literal: **Free com AdSense, Premium sem anúncios, e
 * fallback Free sem anúncios**. "Fallback Free" é o estado em que o status do
 * Premium ainda não é conhecido (carregando) ou falhou: nesse estado o
 * visitante é tratado como Premium — nunca como Free. É o que `usePremiumAtivo`
 * já devolve (`liberado: ativo !== true`, isto é, fail-open para o Premium) e o
 * que `podeExibirAnuncio` preserva.
 *
 * NADA é carregado antes do consentimento: `ADSENSE_CLIENT_ID` só existe se o
 * build tiver `NEXT_PUBLIC_ADSENSE_CLIENT_ID`, e a categoria de consentimento
 * exigida é "personalizacao" (a que o banner descreve como "publicidade de
 * terceiros, como AdSense"). Sem as duas coisas, `AdsScript` renderiza `null`
 * e `AdsSlot` renderiza o placeholder inerte — nem `<script>`, nem `<link>`,
 * nem `preconnect`, nem `dns-prefetch`, nem pixel.
 */

import { permiteCategoria, type CategoriaOpcional } from "./cookie-consent";

/**
 * Categoria de consentimento que autoriza a saída de anúncio. É
 * "personalizacao" e não "analytics" porque é a que o banner de consentimento
 * descreve como "publicidade de terceiros, como AdSense" — anúncio é
 * publicidade, e publicidade não é configuração de leitura.
 */
export const CATEGORIA_CONSENTIMENTO_ANUNCIO: CategoriaOpcional = "personalizacao";

/**
 * Publisher ID do AdSense. VAZIO por padrão de propósito: o código shipped
 * nunca traz ID de cliente real, porque um ID errado é conta de outra pessoa
 * e um ID inventado é conta inexistente. Quem configurar preenche
 * `NEXT_PUBLIC_ADSENSE_CLIENT_ID` no ambiente de build.
 *
 * >>> PENDÊNCIA MARCADA (não validada): o valor real chega com a conta
 * >>> AdSense do solicitante.Até lá, a validação real de anúncio servido
 * >>> (slot criado, impressão, POLICY VIOLATION no AdSense) NÃO RODOU —
 * >>> tudo aqui foi validado com dublês described em
 * >>> `scripts/verificar-consentimento-anuncios.mjs`.
 */
export const ADSENSE_CLIENT_ID = process.env.NEXT_PUBLIC_ADSENSE_CLIENT_ID || "";

/**
 * Hosts de anúncio que este frontend pode referenciar. Serve de allowlist para
 * a guarda de regressão (`verificar-consentimento-anuncios.mjs`): qualquer
 * `<script src>`/`<link href>` de terceiros no frontend que não esteja nesta
 * lista (nem seja explicitly consentido) reprova.
 *
 * - `pagead2.googlesyndication.com` — `adsbygoogle.js`, o `src` do `AdsScript`;
 * - `googleads.g.doubleclick.net`  — gravação de impressão/clique;
 * - `tpc.googlesyndication.com`    — telemetria de pageview do AdSense;
 * - `csi.gstatic.com`              — folha de estilo injetada pelo AdSense.
 */
export const HOSTS_ANUNCIO: readonly string[] = [
  "pagead2.googlesyndication.com",
  "googleads.g.doubleclick.net",
  "tpc.googlesyndication.com",
  "csi.gstatic.com",
];

/**
 * Mesmo conjunto, como sufixo de host, para reconhecer tag/URL de anúncio
 * genérica (incluindo `securepubads.g.doubleclick.net` e variantes de
 * `googlesyndication.com` que o AdSense injeta sozinho em runtime).
 */
export const SUFIXO_HOST_ANUNCIO = /(?:^|\.)(?:googlesyndication\.com|doubleclick\.net|gstatic\.com)$/i;

/** Hosts de MENSURAÇÃO (GA4/GTM). Nenhum é usado hoje — ver `GA4_NAO_IMPLEMENTADO`. */
export const HOSTS_MEDICAO: readonly string[] = [
  "www.googletagmanager.com",
  "www.google-analytics.com",
  "analytics.google.com",
  "region1.google-analytics.com",
];

/**
 * `true` enquanto NÃO existe uma conta de GA4/GTM configurada.
 *
 * O `develop` não implementa GA4: não há `gtag`, nem `G-…`, nem tag do Google
 * em lugar nenhum do frontend. Isso é BOM para o critério "nada externo antes
 * do consentimento" (não há o que vazar) e deixa a metade "GA4" do P1-10
 * **pendente de conta** — ver a guarda, que reprova se alguém introduzir um ID
 * de medição sem consentimento, e o relatório, que marca a validação real
 * como pendência e nunca como verde.
 */
export const GA4_NAO_IMPLEMENTADO = true;

/** Verdadeiro quando o HOST é de anúncio ou de medição do Google. */
export function hostEhDoGoogleAnuncioOuMedicao(host: string): boolean {
  const limpo = String(host || "").toLowerCase().split(":")[0];
  if (limpo === "googleadservices.com" || limpo === "googletagmanager.com") return true;
  return SUFIXO_HOST_ANUNCIO.test(limpo) || HOSTS_MEDICAO.some((h) => limpo === h || limpo.endsWith(`.${h}`));
}

/** Verdadeiro quando a pessoa consentiu com a categoria de publicidade. */
export function consentiuAnuncio(): boolean {
  try {
    return permiteCategoria(CATEGORIA_CONSENTIMENTO_ANUNCIO);
  } catch {
    return false;
  }
}

/**
 * A decisão de negócio, em uma função pura e testável — o resto do módulo é
 * só o efeito colateral.
 *
 * Regra (acordo do programa, P1-09):
 *   - Premium (assinante OU status Premium desconhecido/erro) → NUNCA anúncio;
 *   - Free + consentimento de publicidade + publisher ID → anúncio;
 *   - Free sem consentimento → placeholder inerte, nada sai da máquina.
 *
 * `premium` deliberately chega como argumento em vez de a função ler o
 * Premium sozinha: `liberado` (fail-open para o Premium) é decidido por
 * `usePremiumAtivo`, que depende de rede, e a prova precisa poder passar
 * "Premium desconhecido" sem mock de hook.
 */
export function podeExibirAnuncio(args: {
  consentiu: boolean;
  premium: boolean;
  temPublisherId: boolean;
}): boolean {
  return Boolean(args.consentiu) && !args.premium && Boolean(args.temPublisherId);
}

/**
 * Revogação: derruba a saída de anúncio JÁ INJETADA na página.
 *
 * Por que é preciso e não éOOK: `next/script` com `strategy="lazyOnload"`
 * não tem cleanup de unmount (ver `node_modules/next/dist/client/script.js` —
 * o efeito só chama `loadLazyScript`, nunca `removeChild`). Então, sem este
 * módulo, revogar o consentimento tirava o `<ins class="adsbygoogle">` da
 * árvore React mas deixava o `<script src="…googlesyndication…">` no DOM, com a
 * biblioteca viva: o tracking continuava depois da revogação. Este efeito é o
 * que fecha isso.
 *
 * O que ele NÃO consegue (e é honesto dizer): o pixel/beacon que já foi
 * disparado antes da revogação não volta atrás. O que ele garante é que, a
 * partir da revogação, (a) não há mais script/link/iframe de anúncio no DOM,
 * (b) não há mais `<ins class="adsbygoogle">` para a biblioteca preencher, e
 * (c) a fila global do AdSense é apagada — um `push()` tardio de um closure
 * velho cai em uma fila nova e vazia, sem slot para render, logo sem pedido.
 *
 * @returns quantos nós de saída de anúncio foram removidos (0 = nada havia).
 */
export function revogarSaidaAds(): number {
  if (typeof document === "undefined") return 0;

  const seletores = [
    'script[src*="googlesyndication.com"]',
    'script[src*="doubleclick.net"]',
    'link[href*="googlesyndication.com"]',
    'link[href*="doubleclick.net"]',
    'link[href*="gstatic.com"]',
    'iframe[src*="doubleclick.net"]',
    'ins.adsbygoogle',
    '[data-ad-client]',
  ];
  let removidos = 0;
  for (const seletor of seletores) {
    let nos: NodeListOf<Element>;
    try {
      nos = document.querySelectorAll(seletor);
    } catch {
      continue;
    }
    for (const no of Array.from(nos)) {
      try {
        no.parentNode?.removeChild(no);
        removidos += 1;
      } catch {
        /* nó já detachado */
      }
    }
  }

  // A fila global do AdSense: apagada para que nenhum `push()` pendente
  // encontre a biblioteca e nenhum re-render reative um slot já-fillado.
  // `delete` (e não um no-op congelado) para que um NOVO consentimento
  // reconstrua a fila do zero em vez de falar com um objeto morto.
  try {
    delete (window as unknown as { adsbygoogle?: unknown }).adsbygoogle;
  } catch {
    try {
      (window as unknown as { adsbygoogle?: unknown }).adsbygoogle = undefined;
    } catch {
      /* window congelado: nada a fazer */
    }
  }
  return removidos;
}
