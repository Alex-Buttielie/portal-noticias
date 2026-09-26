import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { SITE_NAME, SITE_URL } from "@/lib/site";
import { newsArticleJsonLd } from "@/lib/schema";
import { obterDetalheItem, obterFeed, type FeedDetalhe } from "@/lib/api";
import { imagemNoticia } from "@/lib/imagens";
import { LeituraPremium } from "../../LeituraPremium";
import { NoticiaReporter } from "@/components/Reporters";
import { CoberturaCompleta } from "@/components/CoberturaCompleta";
import { JsonLd } from "@/components/JsonLd";
export async function generateMetadata({params}:{params:Promise<{id:string}>}): Promise<Metadata>{ const {id}=await params; let t=`Item #${id} - ${SITE_NAME}`; try{ const d=await obterDetalheItem(id); t=d.titulo;}catch{} return {title:t, openGraph:{url:`${SITE_URL}/noticia/item/${id}`}}; }
export function generateStaticParams(){ return [{id:"1"}]; }
export const revalidate=60;
// P0-08: sem "Fonte Exemplo" — item inexistente vira 404, não notícia fictícia.
async function getD(id:string): Promise<FeedDetalhe|null>{ try{ return await obterDetalheItem(id);}catch{ return null; } }
type Relacionado = { id: number; titulo: string; categoria: string; imagem_url?: string };
export default async function Page({params}:{params:Promise<{id:string}>}){
  const {id}=await params;
  const d=await getD(id);
  if(!d) notFound();
  const jsonLd=newsArticleJsonLd({id:d.id,tipo:"item",titulo:d.titulo,categoria:d.categoria,timestamp:d.timestamp,fontes:d.fontes.map(f=>({nome_fonte:f.nome_fonte,url_fonte_original:f.url_fonte_original}))});
  const imagemReal=d.fontes.find((f)=>f.imagem_url)?.imagem_url||"";
  const heroSrc=imagemNoticia({imagem_url: imagemReal, categoria:d.categoria,id:d.id,titulo:d.titulo});
  let relacionados: Relacionado[]=[];
  try{
    const r=await obterFeed({categoria:d.categoria});
    relacionados=(r.results||[]).filter(x=>x.id!==d.id).slice(0,6).map(x=>({id:x.id,titulo:x.titulo,categoria:x.categoria||d.categoria,imagem_url:x.imagem_url}));
  }catch{}
  return (<><JsonLd dados={jsonLd} /><NoticiaReporter entryTipo="item" entryId={d.id} categoria={d.categoria} /><LeituraPremium detalhe={d} relacionados={relacionados} heroSrc={heroSrc} imagemReal={imagemReal} /><div className="mx-auto mt-6 max-w-3xl px-4"><CoberturaCompleta tipo="item" id={d.id} /></div></>);
}
