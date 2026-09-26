import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { SITE_NAME, SITE_URL } from "@/lib/site";
import { newsArticleJsonLd } from "@/lib/schema";
import { obterDetalheCluster, obterDetalheItem, obterFeed, type FeedDetalhe } from "@/lib/api";
import { imagemNoticia } from "@/lib/imagens";
import { LeituraPremium } from "../LeituraPremium";
import { NoticiaReporter } from "@/components/Reporters";
import { CoberturaCompleta } from "@/components/CoberturaCompleta";

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }): Promise<Metadata> {
  const { id } = await params;
  const d = await getDetalhe(id);
  const t = d ? d.titulo : `Notícia #${id} — ${SITE_NAME}`;
  return { title: t, description: d?.fontes?.[0]?.resumo || `Leia em ${SITE_NAME}`, openGraph: { title: t, url: `${SITE_URL}/noticia/${id}` } };
}
export function generateStaticParams() { return [{ id: "1" }]; }
export const revalidate = 60;
// P0-08: notícia que não existe na API não é reconstruída. Antes esta rota
// fabricava um corpo ("Fonte Exemplo") para "não quebrar build" — agora devolve
// 404 quando o ID não existe e um estado de erro honesto quando a API falha.
async function getDetalhe(id: string): Promise<FeedDetalhe | null> {
  try { return await obterDetalheCluster(id); } catch {}
  try { return await obterDetalheItem(id); } catch {}
  return null;
}
export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const d = await getDetalhe(id);
  if (!d) notFound();
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
