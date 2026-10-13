import type { MetadataRoute } from "next";
import { SITE_URL } from "@/lib/site";
import { obterSitemapEntradas, type SitemapEntrada } from "@/lib/api";

// Sem isso, o Next.js gera este arquivo uma vez no build (CI, sem API viva
// — ver comentário de `app/paginas/[slug]/page.tsx`) e nunca mais busca a
// API em produção: o fallback silencioso de `obterTodasEntradas()`, pensado
// para uma falha passageira em runtime, acaba "vencendo" para sempre. Mesmo
// padrão já usado por `app/rss/route.ts`.
export const revalidate = 3600;

const ROTAS_FIXAS = ["", "/editorias", "/ao-vivo", "/buscar", "/sobre", "/contato", "/termos", "/privacidade", "/cookies", "/arquivo", "/newsletter", "/categoria/politica", "/categoria/economia", "/categoria/tecnologia"];

// M-02 (run 20261012-1806-monetizacao-sprint1): só notícias publicáveis E
// indexáveis (com resumo próprio — mesma regra de `lib/seo.ts`/M-03) entram
// no sitemap. Páginas `noindex` não são anunciadas ao Google. Busca paginada
// no endpoint leve `GET /api/feed/sitemap/` (backend/feed/), sem N+1.
// Best-effort: se a API falhar, o sitemap ainda sai com as rotas fixas em
// vez de quebrar o build (`generateSitemaps` não é necessário hoje — bem
// abaixo do limite de 50 mil URLs por sitemap do Next).
async function obterTodasEntradas(): Promise<SitemapEntrada[]> {
  const entradas: SitemapEntrada[] = [];
  let page = 1;
  try {
    for (;;) {
      const resposta = await obterSitemapEntradas(page, 500);
      entradas.push(...resposta.results);
      if (!resposta.next) break;
      page += 1;
    }
  } catch {
    return entradas;
  }
  return entradas;
}

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const base = SITE_URL.replace(/\/$/, "");
  const now = new Date();
  const fixas: MetadataRoute.Sitemap = ROTAS_FIXAS.map((r) => ({
    url: `${base}${r || "/"}`,
    lastModified: now,
    changeFrequency: r === "" ? "hourly" : "weekly",
    priority: r === "" ? 1 : 0.7,
  }));

  const entradas = await obterTodasEntradas();
  const noticias: MetadataRoute.Sitemap = entradas.map((e) => ({
    url: `${base}/noticia/${e.id}`,
    lastModified: new Date(e.timestamp),
    changeFrequency: "daily",
    priority: 0.6,
  }));

  return [...fixas, ...noticias];
}
