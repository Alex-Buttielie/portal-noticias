/**
 * Construtores de dados estruturados schema.org (implementation-contract.md
 * run 20260903-1134-seo-lgpd-design-system, escopo A — critério de aceite
 * 1). Cada função retorna um objeto plano pronto para ser serializado em um
 * `<script type="application/ld+json">` — a renderização em si fica em
 * `components/JsonLd.tsx` (server component, sem custo de round-trip extra:
 * usa os mesmos dados já buscados para `generateMetadata`).
 */

import { IMAGEM_OG_PADRAO, SITE_NAME, SITE_URL } from "./site";

export function organizationJsonLd() {
  return {
    "@context": "https://schema.org",
    "@type": "Organization",
    name: SITE_NAME,
    url: SITE_URL,
    logo: IMAGEM_OG_PADRAO,
  };
}

export function breadcrumbListJsonLd(itens: { nome: string; url: string }[]) {
  return {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: itens.map((item, indice) => ({
      "@type": "ListItem",
      position: indice + 1,
      name: item.nome,
      item: item.url,
    })),
  };
}

export function imageObjectJsonLd(url: string, largura = 1200, altura = 630) {
  return {
    "@type": "ImageObject",
    url,
    width: largura,
    height: altura,
  };
}

/**
 * `NewsArticle` de um item/cluster do feed (`catalogo_noticias`).
 *
 * Decisão registrada em implementation-history.md: `NewsItem`/`NewsCluster`
 * (backend) não têm um autor jornalista individual nem um campo de imagem —
 * são conteúdo agregado de fontes externas (ver `catalogo_noticias/models.py`
 * e ARCHITECTURE.md seção 3), não peças autorais próprias. Por isso:
 * - `author` é a Organization do portal (agregador), não uma Person;
 * - `image` usa a imagem OG padrão (rascunho) até haver um campo de imagem
 *   própria no modelo — fora de escopo desta run (Não-objetivos: multimídia);
 * - o(s) nome(s) das fontes originais (`nome_fonte`, sempre obrigatório no
 *   modelo — rastreabilidade, BRD seção 18) entram em `citation`, preservando
 *   a atribuição de origem também nos dados estruturados.
 */
export function newsArticleJsonLd(params: {
  id: number | string;
  tipo: "cluster" | "item";
  titulo: string;
  categoria: string;
  timestamp: string;
  fontes: { nome_fonte: string; url_fonte_original: string }[];
}) {
  const url = `${SITE_URL}/noticia/${params.tipo}/${params.id}`;
  return {
    "@context": "https://schema.org",
    "@type": "NewsArticle",
    headline: params.titulo,
    datePublished: params.timestamp,
    dateModified: params.timestamp,
    mainEntityOfPage: { "@type": "WebPage", "@id": url },
    url,
    articleSection: params.categoria || undefined,
    author: { "@type": "Organization", name: SITE_NAME, url: SITE_URL },
    publisher: {
      "@type": "Organization",
      name: SITE_NAME,
      logo: imageObjectJsonLd(IMAGEM_OG_PADRAO),
    },
    image: imageObjectJsonLd(IMAGEM_OG_PADRAO),
    citation: params.fontes.map((fonte) => ({
      "@type": "CreativeWork",
      name: fonte.nome_fonte,
      url: fonte.url_fonte_original,
    })),
  };
}

/** `Person` da página de perfil público de um autor (`comunidade/`). */
export function personJsonLd(params: { id: number; nome: string; url: string }) {
  return {
    "@context": "https://schema.org",
    "@type": "Person",
    name: params.nome || `Autor #${params.id}`,
    url: params.url,
  };
}
