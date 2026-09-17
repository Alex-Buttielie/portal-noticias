import type { Metadata } from "next";
import { SITE_NAME, SITE_URL } from "@/lib/site";
import { newsArticleJsonLd } from "@/lib/schema";
import { obterDetalheItem, obterFeed, type FeedDetalhe } from "@/lib/api";
import { imagemNoticia } from "@/lib/imagens";
import { LeituraPremium } from "../../LeituraPremium";
export async function generateMetadata({params}:{params:{id:string}}): Promise<Metadata>{ let t=`Item #${params.id} - ${SITE_NAME}`; try{ const d=await obterDetalheItem(params.id); t=d.titulo;}catch{} return {title:t, openGraph:{url:`${SITE_URL}/noticia/item/${params.id}`}}; }
export function generateStaticParams(){ return [{id:"1"}]; }
export const revalidate=60;
async function getD(id:string): Promise<FeedDetalhe>{ try{ return await obterDetalheItem(id);}catch{ return {tipo:"item",id:Number(id)||1,titulo:`Item #${id}`,categoria:"geral",urgente:false,timestamp:new Date().toISOString(),fontes:[{nome_fonte:"Fonte Exemplo",url_fonte_original:"https://example.com",resumo:"Resumo indisponível no momento"}],exibir_publicidade:false}; } }
type Relacionado = { id: number; titulo: string; categoria: string; imagem_url?: string };
export default async function Page({params}:{params:{id:string}}){
  const d=await getD(params.id);
  const jsonLd=newsArticleJsonLd({id:d.id,tipo:"item",titulo:d.titulo,categoria:d.categoria,timestamp:d.timestamp,fontes:d.fontes.map(f=>({nome_fonte:f.nome_fonte,url_fonte_original:f.url_fonte_original}))});
  const imagemReal=d.fontes.find((f)=>f.imagem_url)?.imagem_url||"";
  const heroSrc=imagemNoticia({imagem_url: imagemReal, categoria:d.categoria,id:d.id,titulo:d.titulo});
  let relacionados: Relacionado[]=[];
  try{
    const r=await obterFeed({categoria:d.categoria});
    relacionados=(r.results||[]).filter(x=>x.id!==d.id).slice(0,6).map(x=>({id:x.id,titulo:x.titulo,categoria:x.categoria||d.categoria,imagem_url:x.imagem_url}));
  }catch{}
  return (<><script type="application/ld+json" dangerouslySetInnerHTML={{__html: JSON.stringify(jsonLd)}} /><LeituraPremium detalhe={d} relacionados={relacionados} heroSrc={heroSrc} imagemReal={imagemReal} /></>);
}
