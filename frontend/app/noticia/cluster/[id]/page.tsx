import type { Metadata } from "next";
import DetalheNoticia from "@/components/DetalheNoticia";
import JsonLd from "@/components/JsonLd";
import * as api from "@/lib/api";
import { breadcrumbListJsonLd, newsArticleJsonLd } from "@/lib/schema";
import { IMAGEM_OG_PADRAO, SITE_URL } from "@/lib/site";

/**
 * Mesmo padrão de `noticia/item/[id]/page.tsx` — ver comentário lá. Um
 * `NewsCluster` também vira `NewsArticle` no JSON-LD (é um acontecimento
 * coberto por 2+ fontes, com um título/timestamp representativo — ver
 * `feed/services.py::detalhe_cluster`), com `citation` listando TODAS as
 * fontes agrupadas.
 */
export async function generateMetadata({
  params,
}: {
  params: { id: string };
}): Promise<Metadata> {
  const detalhe = await api.obterDetalheCluster(params.id).catch(() => null);
  if (!detalhe) {
    return { title: "Notícia não encontrada", robots: { index: false, follow: false } };
  }

  const url = `${SITE_URL}/noticia/cluster/${detalhe.id}`;
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

export default async function PaginaDetalheCluster({ params }: { params: { id: string } }) {
  const detalhe = await api.obterDetalheCluster(params.id).catch(() => null);

  return (
    <>
      {detalhe && (
        <>
          <JsonLd
            data={newsArticleJsonLd({
              id: detalhe.id,
              tipo: "cluster",
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
              { nome: detalhe.titulo, url: `${SITE_URL}/noticia/cluster/${detalhe.id}` },
            ])}
          />
        </>
      )}
      <DetalheNoticia tipo="cluster" id={params.id} />
    </>
  );
}
