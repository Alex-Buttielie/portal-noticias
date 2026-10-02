// ===========================================================================
// O QUE ESTE MÓDULO FAZ (e o que ele NÃO faz mais)
// ===========================================================================
// Este módulo é o ponto por onde TODA imagem de notícia passa antes de
// virar `src`. Ele faz três coisas, nesta ordem:
//
//   1. Se o RSS trouxe `imagem_url`, devolve essa URL — depois de duas
//      recusas: a allowlist de ESQUEMA (`lib/url-segura.ts`, que é o que
//      impede um `javascript:` de virar `src`) e o host do placeholder
//      (§ "O HOST DO PLACEHOLDER" abaixo).
//   2. Se não tem `imagem_url` utilizável, devolve o PLACEHOLDER LOCAL, que
//      é um SVG gerado dentro do próprio HTML (`lib/placeholder.ts`).
//   3. Expõe se a notícia tem foto real ou não (`temImagemReal`).
//
// O QUE MUDOU AQUI, E O NÚMERO QUE FECHA O ITEM
// =============================================
// Antes, o passo 2 pedia a foto a `https://picsum.photos/seed/<categoria-id>`.
// `picsum.photos` é um serviço de TERCEIRO (a Lorem Picsum, mantida pelo
// Unsplash): a requisição entregava o IP, o User-Agent e o momento da visita
// de quem ainda não tinha consentido com nada, e o HTML já servido pelo SSR
// trazia o host — ou seja, a conexão acontecia antes de qualquer JavaScript
// rodar, e também para quem não executa JS.
//
// MEDIDO com build de produção, SSR, backend próprio e ZERO consentimento
// dado, três requisições seguidas com número estável. A coluna da direita é
// o que o portal emite DEPOIS desta correção:
//
//     página                 antes -> depois
//     /                           61 -> 0 conexões a picsum.photos
//     /categoria/politica          2 -> 0 conexões a picsum.photos
//     /noticia/1                    2 -> 0 conexões a picsum.photos
//
// A medição é feita com Chrome headless por CDP, contando
// `Network.requestWillBeSent` (o que o browser EMITE, não o que o HTML
// menciona), e rolando a página até o fim — sem rolagem o browser não busca
// as `<img loading="lazy">` fora da viewport e o número sai MENOR do que a
// página pede, que é o modo de medir e dar o número errado.
//
// DOIS DETALHES QUE MATAM A AMOSTRA MENTIROSA
// ============================================
// 1. O `<link rel="preload" as="image">` que existia no build anterior
//    baixava a imagem antes de ela ser visível, o que torna a conexão
//    impossível de atribuir à rolagem. Ele desapareceu junto com a URL
//    externa: o placeholder agora é um data URI, e data URI não passa por
//    `preload as="image"` — não há requisição para pré-carregar.
// 2. Os 61 da home não são 61 itens: são as Tags da página com as MESMAS
//    notícias aparecendo em várias seções, e o `onError` das fotos do RSS
//    (que falham por DNS) caindo no placeholder e gerando uma segunda
//    requisição. Contar por item daria um número sem meaningido nenhum.
//
// O CUSTO, que é medido e não estimado: o HTML da home ficou MENOR, de
// 250.096 para 196.962 bytes. O placeholder embutido pesa ~960 bytes por
// imagem, mas o `srcset` de três URLs do picsum pesava ~700 bytes POR `<img>`
// e são ~30 deles — e o que saiu do outro lado foram 61 conexões, 61
// resoluções de DNS e 61 handshakes TLS para um host de terceiro.
//
// O QUE FICOU DE TERCEIRO (e por que NÃO é a mesma coisa)
// ========================================================
// A foto que o RSS traz (`imagem_url` apontando para o domínio do veículo)
// continua indo direto para o host do veículo, e isso é conteúdo, não
// placeholder: é a imagem da notícia. Colocá-la atrás do consentimento
// esconderia a foto da notícia de quem não aceitou "publicidade". Fora do
// escopo deste item, e é uma decisão de produto diferente da que está
// encerrada aqui.
// ===========================================================================

import { urlSeguraParaImagem, urlSeguraParaLink } from "@/lib/url-segura";
import { placeholderSvg } from "@/lib/placeholder";

/**
 * Host que JÁ FOI o placeholder do portal, declarado aqui mesmo depois da
 * troca — não por acaso, mas porque ele pode aparecer por OUTRO caminho:
 * um RSS cujo `imagem_url` seja `https://picsum.photos/...` faria o portal
 * hotlinkear o terceiro de novo, por dentro da allowlist de esquema (que
 * aceita http/https, e com razão).
 *
 * Recusar esse host aqui é o que fecha o item de verdade: depois disso,
 * NENHUM caminho do frontend consegue produzir uma conexão a
 * `picsum.photos` — nem o placeholder, nem um feed apontando para ele.
 * O que sobrevive é o placeholder local, que é determinístico e não sai da
 * máquina.
 */
export const HOST_PLACEHOLDER = "picsum.photos";

/** Verdadeiro se a URL é (ou foi) o placeholder de terceiro. */
export function ehHostDePlaceholder(url: string | null | undefined): boolean {
  if (typeof url !== "string" || !url) return false;
  try {
    return new URL(url.trim()).hostname.toLowerCase() === HOST_PLACEHOLDER;
  } catch {
    return false;
  }
}

/**
 * `imagem_url` do feed, quando ela pode ser usada como `src`.
 *
 * Duas recusas, deliberadamente NESTE nível e não dentro de
 * `lib/url-segura.ts`: aquela allowlist é sobre ESQUEMA, e a regra
 * "o placeholder do portal não pode entrar pelo feed" é sobre o CONTEÚDO.
 * Misturar as duas faria a segunda sumir no primeiro `catch`.
 */
export function urlImagemUtilizavel(url: string | null | undefined): string | null {
  const segura = urlSeguraParaImagem(url);
  if (!segura) return null;
  if (ehHostDePlaceholder(segura)) return null;
  return segura;
}

/** Slug da categoria, a MESMA normalização que o antigo `seed` usava. */
function chaveCategoria(categoria: string): string {
  return (categoria || "geral").toLowerCase().trim().replace(/\s+/g, "-") || "geral";
}

/** Identificador do placeholder: o MESMO par que era o `seed` do picsum. */
function identificadorPlaceholder(categoria: string, id: string | number): string {
  return `${chaveCategoria(categoria)}-${String(id ?? "0")}`;
}

export function categoriaImagem(categoria: string): string {
  return placeholderSvg(identificadorPlaceholder(categoria, 0), chaveCategoria(categoria));
}

export function imagemNoticia(entrada: {
  imagem_url?: string | null;
  categoria: string;
  id: string | number;
  titulo?: string;
}): string {
  // `imagem_url` vem do XML do RSS — conteúdo de terceiro. Antes era
  // devolvida VERBATIM, ou seja, `imagem_url` podia ser `javascript:…`
  // ou qualquer esquema que o browser aceitasse em `src`. Passa pela
  // allowlist de esquema; se não passar, cai no PLACEHOLDER LOCAL.
  //
  // A allowlist garante fail-closed no ESQUEMA: um `javascript:` recusado
  // nunca vira `src`. E o placeholder local garante que a recusa não
  // significa "vai pedir a um terceiro" — significa "desenha aqui".
  const real = urlImagemUtilizavel(entrada.imagem_url);
  if (real) return real;
  const categoria = chaveCategoria(entrada.categoria);
  return placeholderSvg(identificadorPlaceholder(categoria, entrada.id), categoria);
}

export function temImagemReal(entrada: { imagem_url?: string | null }): boolean {
  return urlSeguraParaLink(entrada.imagem_url) !== null;
}

export const placeholderBlur = "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7";

/**
 * Placeholder da imagem, na forma em que `ImagemNoticia` consome.
 *
 * O nome é o da função, não o do host: quem chama precisa saber que está
 * desenhando um placeholder LOCAL, e não pedindo uma foto a alguém.
 */
export function placeholder(seed: string): string {
  return placeholderSvg(seed, seed.replace(/-\d+$/, ""));
}