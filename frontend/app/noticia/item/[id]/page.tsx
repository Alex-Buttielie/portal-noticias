import type { Metadata } from "next";
import DetalheNoticia from "@/components/DetalheNoticia";
import JsonLd from "@/components/JsonLd";
import * as api from "@/lib/api";
import { breadcrumbListJsonLd, newsArticleJsonLd } from "@/lib/schema";
import { IMAGEM_OG_PADRAO, SITE_URL } from "@/lib/site";

/**
 * SEO técnico (implementation-contract.md run
 * 20260903-1134-seo-lgpd-design-system, escopo A, critério de aceite 1):
 * `page.tsx` virou um Server Component que busca o detalhe da notícia UMA
 * VEZ (o Next.js faz dedupe automático de `fetch()` idêntico dentro do
 * mesmo request — "Request Memoization" — então `generateMetadata` e este
 * componente não geram duas chamadas de rede) para montar metadata +
 * JSON-LD server-side. O corpo visível continua sendo renderizado pelo
 * `DetalheNoticia` client component já existente (seu próprio fetch
 * client-side é um comportamento pré-existente, não introduzido por esta
 * run — ver implementation-history.md).
 */
export async function generateMetadata({
  params,
}: {
  params: { id: string };
}): Promise<Metadata> {
  const detalhe = await api.obterDetalheItem(params.id).catch(() => null);
  if (!detalhe) {
    return { title: "Notícia não encontrada", robots: { index: false, follow: false } };
  }

  const url = `${SITE_URL}/noticia/item/${detalhe.id}`;
  const descricao = detalhe.fontes[0]?.resumo || detalhe.titulo;

  return {
    title: detalhe.titulo,
    description: descricao,
    alternates: { canonical: url },
    openGraph: {
      type: "article",
      title: detalhe.titulo,
      description: descricao,
      url,
      publishedTime: detalhe.timestamp,
      images: [{ url: IMAGEM_OG_PADRAO, width: 1200, height: 630 }],
    },
    twitter: {
      card: "summary_large_image",
      title: detalhe.titulo,
      description: descricao,
      images: [IMAGEM_OG_PADRAO],
    },
  };
}

export default async function PaginaDetalheItem({ params }: { params: { id: string } }) {
  const detalhe = await api.obterDetalheItem(params.id).catch(() => null);

  return (
    <>
      {detalhe && (
        <>
          <JsonLd
            data={newsArticleJsonLd({
              id: detalhe.id,
              tipo: "item",
              titulo: detalhe.titulo,
              categoria: detalhe.categoria,
              timestamp: detalhe.timestamp,
              fontes: detalhe.fontes,
            })}
          />
          <JsonLd
            data={breadcrumbListJsonLd([
              { nome: "Início", url: SITE_URL },
              ...(detalhe.categoria
                ? [{ nome: detalhe.categoria, url: `${SITE_URL}/?categoria=${encodeURIComponent(detalhe.categoria)}` }]
                : []),
              { nome: detalhe.titulo, url: `${SITE_URL}/noticia/item/${detalhe.id}` },
            ])}
          />
        </>
      )}
      <DetalheNoticia tipo="item" id={params.id} />
    </>
  );
}
