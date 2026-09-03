import { API_BASE_URL } from "@/lib/api";
import { SITE_DESCRIPTION, SITE_NAME, SITE_URL } from "@/lib/site";

/**
 * Feed RSS 2.0 (implementation-contract.md run
 * 20260903-1134-seo-lgpd-design-system, escopo A) — implementado como route
 * handler nativo do Next.js (`app/rss.xml/route.ts`), gerando XML por
 * template string, SEM biblioteca de terceiros (restrição técnica do
 * contrato: preferir stdlib/nativo do framework antes de propor um pacote
 * novo). Decisão registrada em implementation-history.md: optou-se por não
 * duplicar esta lógica no backend porque o endpoint `/api/feed/` já expõe
 * exatamente os dados necessários (itens publicáveis, já filtrados por
 * `feed/services.py`) — reimplementar em `catalogo_noticias` seria
 * redundante.
 */
export const revalidate = 900; // 15min — mesmo intervalo do job de ingestão (config default)

interface FeedEntradaRSS {
  tipo: "cluster" | "item";
  id: number;
  titulo: string;
  resumo: string;
  timestamp: string;
}

function escaparXml(valor: string): string {
  return valor
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

async function obterUltimasNoticias(): Promise<FeedEntradaRSS[]> {
  try {
    const resposta = await fetch(`${API_BASE_URL}/api/feed/?page_size=30`, {
      next: { revalidate },
    });
    if (!resposta.ok) return [];
    const dados = (await resposta.json()) as { results?: FeedEntradaRSS[] };
    return dados.results || [];
  } catch {
    return [];
  }
}

export async function GET() {
  const itens = await obterUltimasNoticias();

  const itensXml = itens
    .map((item) => {
      const url = `${SITE_URL}/noticia/${item.tipo}/${item.id}`;
      const dataPublicacao = new Date(item.timestamp);
      const pubDate = Number.isNaN(dataPublicacao.getTime())
        ? new Date().toUTCString()
        : dataPublicacao.toUTCString();
      return `
    <item>
      <title>${escaparXml(item.titulo)}</title>
      <link>${url}</link>
      <guid isPermaLink="true">${url}</guid>
      <description>${escaparXml(item.resumo || "")}</description>
      <pubDate>${pubDate}</pubDate>
    </item>`;
    })
    .join("");

  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>${escaparXml(SITE_NAME)}</title>
    <link>${SITE_URL}</link>
    <description>${escaparXml(SITE_DESCRIPTION)}</description>
    <language>pt-BR</language>${itensXml}
  </channel>
</rss>`;

  return new Response(xml, {
    headers: { "Content-Type": "application/rss+xml; charset=utf-8" },
  });
}
