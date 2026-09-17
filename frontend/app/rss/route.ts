import { SITE_DESCRIPTION, SITE_NAME, SITE_URL } from "@/lib/site";
import { obterFeed } from "@/lib/api";

export const revalidate = 300;

function esc(s: string) {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

export async function GET() {
  let itens: { titulo: string; link: string; desc: string; data: string }[] = [];
  try {
    const r = await obterFeed({});
    itens = (r.results || []).slice(0, 20).map((e) => ({
      titulo: e.titulo,
      link: `${SITE_URL}/noticia/${e.id}`,
      desc: e.resumo,
      data: new Date(e.timestamp).toUTCString(),
    }));
  } catch {
    itens = [{ titulo: `${SITE_NAME} — feed indisponível (mock)`, link: SITE_URL, desc: SITE_DESCRIPTION, data: new Date().toUTCString() }];
  }
  const xml = `<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>${esc(SITE_NAME)}</title><link>${SITE_URL}</link><description>${esc(SITE_DESCRIPTION)}</description><language>pt-BR</language>${itens.map((i) => `<item><title>${esc(i.titulo)}</title><link>${i.link}</link><description>${esc(i.desc)}</description><pubDate>${i.data}</pubDate><guid>${i.link}</guid></item>`).join("")}</channel></rss>`;
  return new Response(xml, { headers: { "Content-Type": "application/rss+xml; charset=utf-8", "Cache-Control": "public, s-maxage=300, stale-while-revalidate=600" } });
}
