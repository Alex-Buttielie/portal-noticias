import type { Metadata } from "next";
import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { SITE_NAME, SITE_URL } from "@/lib/site";
import { newsArticleJsonLd } from "@/lib/schema";
import { obterDetalheCluster, type FeedDetalhe } from "@/lib/api";
import { imagemNoticia } from "@/lib/imagens";
import { AdsSlot } from "@/components/AdsSlot";
import { AcoesNoticia } from "../../[id]/acoes";
export async function generateMetadata({params}:{params:{id:string}}): Promise<Metadata>{ let t=`Cluster #${params.id} - ${SITE_NAME}`; try{ const d=await obterDetalheCluster(params.id); t=d.titulo;}catch{} return {title:t, openGraph:{url:`${SITE_URL}/noticia/cluster/${params.id}`}}; }
export function generateStaticParams(){ return [{id:"1"}]; }
export const revalidate=60;
async function getD(id:string): Promise<FeedDetalhe>{ try{ return await obterDetalheCluster(id);}catch{ return {tipo:"cluster",id:Number(id)||1,titulo:`Cluster #${id} (mock)`,categoria:"geral",urgente:false,timestamp:new Date().toISOString(),fontes:[{nome_fonte:"Fonte Exemplo",url_fonte_original:"https://example.com",resumo:"Resumo mock - API offline"}],exibir_publicidade:false}; } }
function fmt(iso:string){ return new Intl.DateTimeFormat("pt-BR",{dateStyle:"short",timeStyle:"short"}).format(new Date(iso)); }
export default async function Page({params}:{params:{id:string}}){
  const d=await getD(params.id);
  const jsonLd=newsArticleJsonLd({id:d.id,tipo:"cluster",titulo:d.titulo,categoria:d.categoria,timestamp:d.timestamp,fontes:d.fontes.map(f=>({nome_fonte:f.nome_fonte,url_fonte_original:f.url_fonte_original}))});
  const imagemReal=d.fontes.find((f)=>f.imagem_url)?.imagem_url||"";
  const entrada={tipo:d.tipo,id:d.id,titulo:d.titulo,resumo:d.fontes[0]?.resumo||"",categoria:d.categoria,urgente:d.urgente,numero_fontes:d.fontes.length,timestamp:d.timestamp,imagem_url:imagemReal} as const;
  return (<article className="mx-auto max-w-3xl space-y-4 py-4"><script type="application/ld+json" dangerouslySetInnerHTML={{__html: JSON.stringify(jsonLd)}} /><div className="flex flex-wrap items-center gap-2 text-xs text-[var(--cor-texto-suave)]"><Link href="/" className="hover:underline">Inicio</Link><span aria-hidden>›</span><Link href={`/categoria/${encodeURIComponent(d.categoria)}`} className="capitalize hover:underline">{d.categoria}</Link></div><div className="flex flex-wrap items-center gap-2"><Badge variant="outline" className="border-[var(--cor-borda)] capitalize">{d.categoria}</Badge>{d.urgente&&<Badge className="bg-[var(--cor-sinal)] text-[var(--cor-texto-invertido)]">urgente</Badge>}<span className="text-xs text-[var(--cor-texto-suave)]">{fmt(d.timestamp)} • {d.fontes.length} fontes</span></div><h1 className="text-balance text-3xl font-bold text-[var(--cor-texto)]">{d.titulo}</h1><div className="hud-line" aria-hidden /><div className="overflow-hidden rounded-[var(--raio-lg)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)]"><div className="aspect-[16/9] overflow-hidden bg-[var(--cor-fundo-elevado)]"><img src={imagemNoticia({imagem_url: imagemReal, categoria:d.categoria,id:d.id,titulo:d.titulo})} alt={d.titulo} loading="lazy" className="h-full w-full object-cover" /></div><p className="px-3 py-2 text-xs text-[var(--cor-texto-suave)]">Imagem ilustrativa — picsum.photos/seed/{d.categoria}-{d.id} • Crédito: fontes citadas</p></div><AdsSlot id="cluster-topo" formato="horizontal" /><AcoesNoticia entrada={entrada} /><Card className="bento border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]"><CardContent className="prose max-w-none p-5 prose-p:text-[var(--cor-texto)]"><p className="text-[var(--cor-texto-suave)]">{d.fontes[0]?.resumo}</p><AdsSlot id="cluster-infeed" formato="in-feed" className="my-4 not-prose" /><Separator className="my-4 bg-[var(--cor-borda)]" /><h2 className="text-lg font-bold">Fontes</h2><ul className="space-y-2">{d.fontes.map((f,i)=> (<li key={i} className="rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-3"><a href={f.url_fonte_original} target="_blank" rel="noopener noreferrer" className="font-medium text-[var(--cor-primaria)] hover:underline">{f.nome_fonte}</a>{f.resumo&&<p className="text-sm text-[var(--cor-texto-suave)]">{f.resumo}</p>}</li>))}</ul></CardContent></Card><AdsSlot id="cluster-pos" formato="horizontal" className="my-6" /></article>);
}
