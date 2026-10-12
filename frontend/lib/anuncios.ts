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
 * Regra (acordo do programa, P1-09 + desacoplamento feat/adsense-ativar-dev):
 *   - Premium por assinatura (papel premium/admin) OU status desconhecido/erro
 *     (`ativo === null`) → NUNCA anúncio;
 *   - Free + consentimento de publicidade + publisher ID + status conhecido
 *     (`ativo === true` ou `false`) → anúncio (flag OFF conhecida exibe);
 *   - Free sem consentimento → placeholder inerte, nada sai da máquina.
 *
 * `premium` deliberately chega como argumento em vez de a função ler o
 * Premium sozinha: o chamador resolve `isPremium || ativo === null` via
 * `usePremiumAtivo` (rede), e a prova precisa poder passar
 * "Premium desconhecido" sem mock de hook. NÃO passar `liberado` aqui:
 * `liberado` é fail-open para features e com a flag OFF esconderia anúncios
 * de todo mundo.
 */
export function podeExibirAnuncio(args: {
  consentiu: boolean;
  premium: boolean;
  temPublisherId: boolean;
}): boolean {
  return Boolean(args.consentiu) && !args.premium && Boolean(args.temPublisherId);
}

/**
 * M-04 — um slot do AdSense por POSIÇÃO, não só por formato.
 *
 * Antes, todo `AdsSlot` do mesmo formato (ex. todos os "horizontal":
 * `home-topo`, `noticia-topo`, `categoria-topo`, `planos-horizontal`...)
 * compartilhava o mesmo `data-ad-slot` (`SLOT_POR_FORMATO`) — o relatório do
 * AdSense não conseguia dizer qual POSIÇÃO estava rendendo, só o formato.
 *
 * `SLOT_POR_POSICAO` mapeia o `id` de cada `AdsSlot` (ver grep completo em
 * `implementation-history.md`, M-04) para sua própria
 * `NEXT_PUBLIC_ADSENSE_SLOT_<POSICAO>`. Cada valor abaixo tem que ser um
 * acesso ESTÁTICO a `process.env.NEXT_PUBLIC_*` (não um acesso dinâmico por
 * nome de variável) — é assim que o compilador do Next consegue substituir
 * pelo valor literal no build; `process.env[nomeDinamico]` NÃO funciona no
 * bundle do navegador (só os acessos estáticos são inlined).
 */
export type FormatoAnuncio = "horizontal" | "retangulo" | "vertical" | "in-feed";

const SLOT_POR_FORMATO: Record<FormatoAnuncio, string> = {
  horizontal: process.env.NEXT_PUBLIC_ADSENSE_SLOT_HORIZONTAL || "",
  retangulo: process.env.NEXT_PUBLIC_ADSENSE_SLOT_RETANGULO || "",
  vertical: process.env.NEXT_PUBLIC_ADSENSE_SLOT_VERTICAL || "",
  "in-feed": process.env.NEXT_PUBLIC_ADSENSE_SLOT_INFEED || "",
};

const SLOT_POR_POSICAO: Record<string, string> = {
  "home-topo": process.env.NEXT_PUBLIC_ADSENSE_SLOT_HOME_TOPO || "",
  "home-manchetes": process.env.NEXT_PUBLIC_ADSENSE_SLOT_HOME_MANCHETES || "",
  "home-ultimas": process.env.NEXT_PUBLIC_ADSENSE_SLOT_HOME_ULTIMAS || "",
  "home-pos-bombando": process.env.NEXT_PUBLIC_ADSENSE_SLOT_HOME_POS_BOMBANDO || "",
  "home-pos-regiao": process.env.NEXT_PUBLIC_ADSENSE_SLOT_HOME_POS_REGIAO || "",
  "home-pos-colunistas": process.env.NEXT_PUBLIC_ADSENSE_SLOT_HOME_POS_COLUNISTAS || "",
  "home-infeed": process.env.NEXT_PUBLIC_ADSENSE_SLOT_HOME_INFEED || "",
  "home-sidebar": process.env.NEXT_PUBLIC_ADSENSE_SLOT_HOME_SIDEBAR || "",
  "home-sidebar-2": process.env.NEXT_PUBLIC_ADSENSE_SLOT_HOME_SIDEBAR_2 || "",
  "home-footer": process.env.NEXT_PUBLIC_ADSENSE_SLOT_HOME_FOOTER || "",
  "noticia-topo": process.env.NEXT_PUBLIC_ADSENSE_SLOT_NOTICIA_TOPO || "",
  "noticia-infeed": process.env.NEXT_PUBLIC_ADSENSE_SLOT_NOTICIA_INFEED || "",
  "noticia-pos": process.env.NEXT_PUBLIC_ADSENSE_SLOT_NOTICIA_POS || "",
  "categoria-topo": process.env.NEXT_PUBLIC_ADSENSE_SLOT_CATEGORIA_TOPO || "",
  // Grupo dinâmico: `categoria-infeed-${indice}` (loop) e `categoria-infeed-final`
  // (última posição, fora do loop) compartilham a mesma variável — ver
  // `grupoDaPosicao` abaixo, que remove o último segmento de ids em loop.
  "categoria-infeed": process.env.NEXT_PUBLIC_ADSENSE_SLOT_CATEGORIA_INFEED || "",
  "categoria-infeed-final": process.env.NEXT_PUBLIC_ADSENSE_SLOT_CATEGORIA_INFEED || "",
  "categoria-pos": process.env.NEXT_PUBLIC_ADSENSE_SLOT_CATEGORIA_POS || "",
  "buscar-infeed": process.env.NEXT_PUBLIC_ADSENSE_SLOT_BUSCAR_INFEED || "",
  "buscar-horizontal": process.env.NEXT_PUBLIC_ADSENSE_SLOT_BUSCAR_HORIZONTAL || "",
  "arquivo-infeed": process.env.NEXT_PUBLIC_ADSENSE_SLOT_ARQUIVO_INFEED || "",
  "arquivo-horizontal": process.env.NEXT_PUBLIC_ADSENSE_SLOT_ARQUIVO_HORIZONTAL || "",
  "planos-horizontal": process.env.NEXT_PUBLIC_ADSENSE_SLOT_PLANOS_HORIZONTAL || "",
  "radar-retangulo": process.env.NEXT_PUBLIC_ADSENSE_SLOT_RADAR_RETANGULO || "",
  // Grupo dinâmico: `comunidade-detalhe-${safeId}`.
  "comunidade-detalhe": process.env.NEXT_PUBLIC_ADSENSE_SLOT_COMUNIDADE_DETALHE || "",
  // Grupo dinâmico: `comunidade-feed-${idx}`.
  "comunidade-feed": process.env.NEXT_PUBLIC_ADSENSE_SLOT_COMUNIDADE_FEED || "",
};

/**
 * Agrupa um id gerado em loop ("categoria-infeed-3", "comunidade-feed-12")
 * na posição-base do loop ("categoria-infeed", "comunidade-feed"), removendo
 * o último segmento (índice/id variável). Ids fixos que também terminam em
 * número (ex. "home-sidebar-2") não dependem disto: são chaves EXATAS de
 * `SLOT_POR_POSICAO`, resolvidas antes de qualquer agrupamento.
 */
function grupoDaPosicao(id: string): string {
  return id.replace(/-[^-]+$/, "");
}

/**
 * Slot do AdSense para a posição `id`. Tenta o id exato primeiro; se não
 * houver entrada (ids gerados em loop), tenta o grupo. Sem variável
 * definida para a posição (nos dois casos), devolve "" — o chamador cai no
 * padrão do formato.
 */
export function slotPorPosicao(id: string): string {
  return SLOT_POR_POSICAO[id] || SLOT_POR_POSICAO[grupoDaPosicao(id)] || "";
}

/**
 * Resolução final do `data-ad-slot` de um `AdsSlot`: prop `slot` explícita
 * (override manual) > variável de ambiente da posição (M-04) > padrão do
 * formato (comportamento anterior, preservado quando nada mais está
 * configurado — critério de aceite 4 do implementation-contract.md).
 */
export function resolverSlotAnuncio(id: string, formato: FormatoAnuncio, slotExplicito?: string): string {
  return slotExplicito || slotPorPosicao(id) || SLOT_POR_FORMATO[formato];
}

/**
 * M-05 — quando não há anúncio para mostrar (sem consentimento, ou sem
 * publisher ID/slot configurado), o placeholder de DEBUG (texto técnico:
 * "PUBLICIDADE" / "Anúncio — Google AdSense (slot …)") só pode aparecer
 * FORA de produção — é o que ajuda quem está codando a ver o espaço
 * reservado. Em produção, o leitor nunca vê esse texto: o componente
 * devolve `null` nesse ramo (M-09 substitui por `CartaoPremium` quando
 * aplicável — ver `AdsSlot.tsx`).
 *
 * Função pura e testável sem precisar de DOM/hooks/providers (ver
 * `testes/anuncios-placeholder.test.mjs`).
 */
export function mostrarPlaceholderDebug(nodeEnv: string | undefined): boolean {
  return nodeEnv !== "production";
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
