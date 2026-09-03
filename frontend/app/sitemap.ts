import type { MetadataRoute } from "next";
import { API_BASE_URL } from "@/lib/api";
import { SITE_URL } from "@/lib/site";

/**
 * Sitemap dinâmico nativo do Next.js (implementation-contract.md run
 * 20260903-1134-seo-lgpd-design-system, escopo A, critério de aceite 2) —
 * responde em `/sitemap.xml`. Regenerado no máximo a cada hora (não a cada
 * request), suficiente para o volume de ingestão do backend
 * (`CATALOGO_NOTICIAS_INTERVALO_INGESTAO_MINUTOS`, default 15min).
 */
export const revalidate = 3600;

interface FeedEntradaMinima {
  tipo: "cluster" | "item";
  id: number;
  timestamp: string;
}

async function obterEntradasFeedParaSitemap(): Promise<FeedEntradaMinima[]> {
  try {
    const resposta = await fetch(`${API_BASE_URL}/api/feed/?page_size=100`, {
      next: { revalidate },
    });
    if (!resposta.ok) return [];
    const dados = (await resposta.json()) as { results?: FeedEntradaMinima[] };
    return dados.results || [];
  } catch {
    // Backend indisponível no momento de gerar o sitemap — não deve
    // derrubar a rota inteira, só resulta em um sitemap com só as páginas
    // estáticas (degradação graciosa em vez de erro 500).
    return [];
  }
}

const PAGINAS_ESTATICAS_PUBLICAS = [
  "",
  "/comunidade",
  "/radar",
  "/planos",
  "/privacidade/politica",
  "/privacidade/preferencias-cookies",
];

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const entradas = await obterEntradasFeedParaSitemap();

  const urlsEstaticas: MetadataRoute.Sitemap = PAGINAS_ESTATICAS_PUBLICAS.map((caminho) => ({
    url: `${SITE_URL}${caminho}`,
    changeFrequency: caminho === "" ? "hourly" : "daily",
    priority: caminho === "" ? 1 : 0.5,
  }));

  const urlsNoticias: MetadataRoute.Sitemap = entradas.map((entrada) => ({
    url: `${SITE_URL}/noticia/${entrada.tipo}/${entrada.id}`,
    lastModified: new Date(entrada.timestamp),
    changeFrequency: "hourly",
    priority: 0.8,
  }));

  return [...urlsEstaticas, ...urlsNoticias];
}
