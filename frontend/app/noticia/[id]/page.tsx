import type { Metadata } from "next";
import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { SITE_NAME, SITE_URL } from "@/lib/site";
import { newsArticleJsonLd } from "@/lib/schema";
import { obterDetalheCluster, obterDetalheItem, type FeedDetalhe } from "@/lib/api";
import { imagemNoticia } from "@/lib/imagens";
import { AcoesNoticia } from "./acoes";
import { AdsSlot } from "@/components/AdsSlot";

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
function fmt(iso: string){ return new Intl.DateTimeFormat("pt-BR",{dateStyle:"long",timeStyle:"short"}).format(new Date(iso)); }
export default async function Page({ params }: { params: { id: string } }) {
  const d = (await getDetalhe(params.id))!;
  const jsonLd = newsArticleJsonLd({ id: d.id, tipo: d.tipo, titulo: d.titulo, categoria: d.categoria, timestamp: d.timestamp, fontes: d.fontes.map(f=>({ nome_fonte:f.nome_fonte, url_fonte_original:f.url_fonte_original })) });
  const entrada = { tipo: d.tipo, id: d.id, titulo: d.titulo, resumo: d.fontes[0]?.resumo || "", categoria: d.categoria, urgente: d.urgente, numero_fontes: d.fontes.length, timestamp: d.timestamp } as const;
  const heroSrc = imagemNoticia({ categoria: d.categoria, id: d.id, titulo: d.titulo });
  return (
    <article className="mx-auto max-w-3xl space-y-4">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
      <div className="flex items-center gap-2 text-xs text-[var(--cor-texto-suave)]"><Link href="/" className="hover:underline">Início</Link><span aria-hidden>›</span><Link href={`/categoria/${encodeURIComponent(d.categoria)}`} className="capitalize hover:underline">{d.categoria}</Link></div>
      <div className="flex flex-wrap items-center gap-2"><Badge variant="outline" className="border-[var(--cor-borda)] capitalize">{d.categoria}</Badge>{d.urgente&&<Badge className="bg-[var(--cor-sinal)] text-[var(--cor-texto-invertido)]">urgente</Badge>}<span className="text-xs text-[var(--cor-texto-suave)]">{fmt(d.timestamp)} • {d.fontes.length} fontes</span></div>
      <h1 className="text-balance text-3xl font-bold leading-tight text-[var(--cor-texto)]">{d.titulo}</h1>
      <div className="hud-line" aria-hidden />
      <div className="overflow-hidden rounded-[var(--raio-lg)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)]">
        <div className="aspect-[16/9] overflow-hidden bg-[var(--cor-fundo-elevado)]">
          <img src={heroSrc} alt={d.titulo} loading="lazy" className="h-full w-full object-cover" />
        </div>
        <p className="px-3 py-2 text-xs text-[var(--cor-texto-suave)]">Imagem ilustrativa — picsum.photos/seed/{d.categoria}-{d.id} • Crédito: fontes citadas abaixo</p>
      </div>
      <AdsSlot id="noticia-topo" formato="horizontal" />
      <AcoesNoticia entrada={entrada} />
      <Card className="bento border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]"><CardContent className="prose max-w-none p-5 prose-p:text-[var(--cor-texto)] prose-headings:text-[var(--cor-texto)]"><p className="text-pretty leading-relaxed text-[var(--cor-texto-suave)]">{d.fontes[0]?.resumo}</p><AdsSlot id="noticia-infeed" formato="in-feed" className="my-4 not-prose" /><Separator className="my-4 bg-[var(--cor-borda)]" /><h2 className="text-lg font-bold">Fontes</h2><ul className="space-y-2">{d.fontes.map((f,i)=>(<li key={i} className="rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-3"><a href={f.url_fonte_original} target="_blank" rel="noopener noreferrer" className="font-medium text-[var(--cor-primaria)] hover:underline">{f.nome_fonte}</a><span className="ml-2 text-xs text-[var(--cor-texto-suave)]">↗ {new URL(f.url_fonte_original).hostname}</span>{f.resumo&&<p className="mt-1 text-sm text-[var(--cor-texto-suave)]">{f.resumo}</p>}</li>))}</ul></CardContent></Card>
      <p className="text-xs text-[var(--cor-texto-suave)]">Rastreabilidade: {d.fontes.length} fonte(s) citada(s) • <Link href="/sobre" className="underline">como apuramos</Link></p>
    </article>
  );
}
