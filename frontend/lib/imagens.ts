// >>> PENDÊNCIA MARCADA — picsum É TERCEIRO, E SAI ANTES DO CONSENTIMENTO
// ===========================================================================
// O que este módulo é: o gerador do PLACEHOLDER de imagem. Quando a notícia
// não tem `imagem_url` (ou a URL é recusada pela allowlist de esquema), o
// portal pede uma foto de exemplo a `https://picsum.photos/seed/...`.
//
// O que este módulo NÃO é, e o que o código anterior afirmava: uma "URL do
// próprio portal". NÃO ERA VERDADE. `picsum.photos` é um serviço de TERCEIRO
// (a Lorem Picsum, mantida pelo Unsplash). A imagem é gerada no servidor
// deles, e a requisição entrega o IP, o User-Agent e o momento da visita
// de quem ainda não consentiu com nada — e, pior, o HTML JÁ SERVIDO pelo
// SSR traz o host, então a conexão acontece antes de qualquer JavaScript
// rodar e também para quem não executa JS.
//
// MEDIDO NESTE LOTE (build de produção, SSR, backend próprio com 33 itens
// — 14 deles sem `imagem_url`, o caso que dispara o placeholder — e com
// ZERO consentimento dado; três requisições seguidas, número estável):
//
//     /                    42 conexões a picsum.photos  (41 <img> + 1 preload)
//     /categoria/politica   6 conexões a picsum.photos
//     /noticia/1            6 conexões a picsum.photos  (+1 preload eager)
//     /radar                0
//
// O número 6 que circulava mede a página de categoria/artigo. A HOME é 42.
// E o preload (`<link rel="preload" as="image" imageSrcSet="https://picsum…">`)
// é pior que um `<img>` comum: o browser baixa antes de a imagem estar
// visível, o que torna a conexão impossível de atribuir à rolagem.
//
// As tags de recurso com a medição são versionadas em
// `backend/config/tests/evidencia_a10_tags.html`, e
// `backend/config/tests/test_p1_09_placeholder_terceiro.py` reconta as
// conexões a partir dele e exige que o número daqui bata. Ou seja: se este
// número divergir do HTML, a suíte reprova.
//
// POR QUE A CORREÇÃO NÃO ESTÁ NESTE ARQUIVO
// =========================================
// As duas saídas possíveis são ambas DECISÃO DE PRODUTO, não de engenharia:
//
//   (a) Trocar o placeholder por um asset local versionado. some
//       completamente a conexão externa, mas TODOS os placeholders passam a
//       ser a mesma imagem — o portal perde a variação visual que hoje
//       distingue uma notícia da outra na grade. Exige gerar/versionar o
//       asset e decidir se a perda de variedade é aceitável.
//   (b) Carregar o placeholder atrás do portão de consentimento. preserva o
//       design, mas a miniatura da notícia some até a pessoa aceitar
//       "publicidade" — e o banner descreve essa categoria como "publicidade
//       de terceiros, como AdSense". Uma foto de exemplo de artigo não é
//       publicidade, então isso é pior UX e continua sendo um produto
//       errado sem uma categoria de consentimento nova.
//
// Escolher entre (a) e (b), ou criar essa categoria nova, é decisão de quem
// define o produto. Este lote NÃO escolhe, e não escolheu: o que ele faz é
// remover a afirmação falsa, registrar a pendência com a classificação
// correta (`p-pendencia`, decisão de produto, não é bug de implementação)
// e fazer a guarda de consentimento parar de dizer "nada externo".
// ===========================================================================

import { urlSeguraParaImagem, urlSeguraParaLink } from "@/lib/url-segura";

/** Host de TERCEIRO do placeholder. Declarado à parte para ser contável. */
export const HOST_PLACEHOLDER = "picsum.photos";

export function categoriaImagem(categoria: string): string {
  const s = (categoria || "geral").toLowerCase().trim().replace(/\s+/g, "-") || "geral";
  return `https://${HOST_PLACEHOLDER}/seed/${encodeURIComponent(s)}/800/450`;
}
export function imagemNoticia(entrada: { imagem_url?: string | null; categoria: string; id: string | number; titulo?: string }): string {
  // `imagem_url` vem do XML do RSS — conteúdo de terceiro. Antes era
  // devolvida VERBATIM, ou seja, `imagem_url` podia ser `javascript:…`
  // ou qualquer esquema que o browser aceitasse em `src`. Passa pela
  // allowlist de esquema; se não passar, cai no placeholder picsum.
  //
  // O picsum É de terceiro e sai antes do consentimento (ver a PENDÊNCIA no
  // topo deste arquivo). O que a allowlist garante, e é o que interessa aqui,
  // é fail-closed no ESQUEMA: um `javascript:` recusado nunca vira `src`.
  const real = urlSeguraParaImagem(entrada.imagem_url);
  if (real) return real;
  const cat = (entrada.categoria || "geral").toLowerCase().trim().replace(/\s+/g, "-") || "geral";
  const id = String(entrada.id ?? "0");
  return `https://${HOST_PLACEHOLDER}/seed/${encodeURIComponent(`${cat}-${id}`)}/800/450`;
}
export function temImagemReal(entrada: { imagem_url?: string | null }): boolean {
  return urlSeguraParaLink(entrada.imagem_url) !== null;
}
export const placeholderBlur = "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7";

/** Tamanhos mobile-first do placeholder picsum (evita baixar 800px no 4G). */
export function picsum(seed: string, w = 800, h = 450): string {
  return `https://picsum.photos/seed/${encodeURIComponent(seed)}/${w}/${h}`;
}

/** srcSet responsivo — só faz sentido para URLs picsum (padrão /seed/s/W/H). */
export function srcSetPicsum(seed: string): string {
  return [400, 640, 800]
    .map((w) => `${picsum(seed, w, Math.round((w * 9) / 16))} ${w}w`)
    .join(", ");
}

export function ehPicsum(url: string): boolean {
  return /(^|\/\/)picsum\.photos\//.test(url || "");
}

/** Extrai a seed de URLs picsum para reaproveitar no srcSet/fallback. */
export function seedDePicsum(url: string): string | null {
  const m = (url || "").match(/picsum\.photos\/seed\/([^/]+)/);
  return m ? decodeURIComponent(m[1]) : null;
}
