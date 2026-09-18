import type { Metadata } from "next";
import { SITE_NAME, SITE_URL } from "@/lib/site";
import { newsArticleJsonLd } from "@/lib/schema";
import { obterDetalheCluster, obterDetalheItem, obterFeed, type FeedDetalhe } from "@/lib/api";
import { imagemNoticia } from "@/lib/imagens";
import { LeituraPremium } from "../LeituraPremium";
import { NoticiaReporter } from "@/components/Reporters";
import { CoberturaCompleta } from "@/components/CoberturaCompleta";

export async function generateMetadata({ params }: { params: { id: string } }): Promise<Metadata> {
  const d = await getDetalhe(params.id);
  const t = d ? d.titulo : `Notícia #${params.id} — ${SITE_NAME}`;
  return { title: t, description: d?.fontes?.[0]?.resumo || `Leia em ${SITE_NAME}`, openGraph: { title: t, url: `${SITE_URL}/noticia/${params.id}` } };
}
export function generateStaticParams() { return [{ id: "1" }]; }
export const revalidate = 60;
async function getDetalhe(id: string): Promise<FeedDetalhe | null> {
  try { return await obterDetalheCluster(id); } catch {}
  try { return await obterDetalheItem(id); } catch {}
  return { tipo: "item", id: Number(id) || 1, titulo: `Notícia #${id} — conteúdo de demonstração`, categoria: "geral", urgente: false, timestamp: new Date().toISOString(), fontes: [{ nome_fonte: "Fonte Exemplo", url_fonte_original: "https://example.com", resumo: "Resumo de fallback — API offline. Conteúdo demonstrativo para não quebrar build." }], exibir_publicidade: false };
}
export default async function Page({ params }: { params: { id: string } }) {
  const d = (await getDetalhe(params.id))!;
  const jsonLd = newsArticleJsonLd({ id: d.id, tipo: d.tipo, titulo: d.titulo, categoria: d.categoria, timestamp: d.timestamp, fontes: d.fontes.map(f=>({ nome_fonte:f.nome_fonte, url_fonte_original:f.url_fonte_original })) });
  const imagemReal = d.fontes.find((f) => f.imagem_url)?.imagem_url || "";
  const heroSrc = imagemNoticia({ imagem_url: imagemReal, categoria: d.categoria, id: d.id, titulo: d.titulo });
  let relacionados: { id: number; titulo: string; categoria: string; imagem_url?: string }[] = [];
  try {
    const r = await obterFeed({ categoria: d.categoria });
    relacionados = (r.results || []).filter(x=>x.id!==d.id).slice(0, 6).map(x=>({ id: x.id, titulo: x.titulo, categoria: x.categoria || d.categoria, imagem_url: x.imagem_url }));
  } catch {}
  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
      <NoticiaReporter entryTipo={d.tipo === "cluster" ? "cluster" : "item"} entryId={d.id} categoria={d.categoria} />
      <LeituraPremium detalhe={d} relacionados={relacionados} heroSrc={heroSrc} imagemReal={imagemReal} />
      <div className="mx-auto mt-6 max-w-3xl px-4">
        <CoberturaCompleta tipo={d.tipo === "cluster" ? "cluster" : "item"} id={d.id} />
      </div>
    </>
  );
}
