import type { Metadata } from "next";
import { notFound } from "next/navigation";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { SITE_NAME, SITE_URL } from "@/lib/site";
import { newsArticleJsonLd } from "@/lib/schema";
import { obterDetalheItem, obterFeed, ApiError, type FeedDetalhe } from "@/lib/api";
import { imagemNoticia } from "@/lib/imagens";
import { LeituraPremium } from "../../LeituraPremium";
import { NoticiaReporter } from "@/components/Reporters";
import { CoberturaCompleta } from "@/components/CoberturaCompleta";
import { NoticiaIndisponivel } from "@/components/NoticiaIndisponivel";

/** Estados separados; ver a explicação em `app/noticia/[id]/page.tsx`. */
type ResultadoDetalhe =
  | { tipo: "detalhe"; dados: FeedDetalhe }
  | { tipo: "inexistente" }
  | { tipo: "indisponivel"; requestId: string | null; mensagem: string };

function classificar(erro: unknown): { tipo: "inexistente" } | { tipo: "indisponivel"; requestId: string | null; mensagem: string } {
  if (erro instanceof ApiError && erro.status === 404) return { tipo: "inexistente" };
  return {
    tipo: "indisponivel",
    requestId: erro instanceof ApiError ? erro.requestId : null,
    mensagem: erro instanceof Error ? erro.message : "Falha inesperada ao consultar o item.",
  };
}

async function getD(id:string): Promise<ResultadoDetalhe>{
  try{ return { tipo: "detalhe", dados: await obterDetalheItem(id) }; }
  catch(erro){ return classificar(erro); }
}
export async function generateMetadata({params}:{params:{id:string}}): Promise<Metadata>{ let t=`Item #${params.id} - ${SITE_NAME}`; try{ const r=await getD(params.id); if(r.tipo==="detalhe") t=r.dados.titulo; }catch{ /* 404/indisponivel tratados abaixo */ } return {title:t, openGraph:{url:`${SITE_URL}/noticia/item/${params.id}`}}; }
/** `[]`: sem pré-geração no build (ver `app/noticia/[id]/page.tsx`). */
export function generateStaticParams(){ return []; }
export const revalidate=60;
type Relacionado = { id: number; titulo: string; categoria: string; imagem_url?: string };
export default async function Page({params}:{params:{id:string}}){
  const resultado=await getD(params.id);
  if(resultado.tipo==="inexistente") notFound();
  if(resultado.tipo==="indisponivel") return <NoticiaIndisponivel requestId={resultado.requestId} mensagem={resultado.mensagem} />;
  const d=resultado.dados;
  const jsonLd=newsArticleJsonLd({id:d.id,tipo:"item",titulo:d.titulo,categoria:d.categoria,timestamp:d.timestamp,fontes:d.fontes.map(f=>({nome_fonte:f.nome_fonte,url_fonte_original:f.url_fonte_original}))});
  const imagemReal=d.fontes.find((f)=>f.imagem_url)?.imagem_url||"";
  const heroSrc=imagemNoticia({imagem_url: imagemReal, categoria:d.categoria,id:d.id,titulo:d.titulo});
  let relacionados: Relacionado[]=[];
  try{
    const r=await obterFeed({categoria:d.categoria});
    relacionados=(r.results||[]).filter(x=>x.id!==d.id).slice(0,6).map(x=>({id:x.id,titulo:x.titulo,categoria:x.categoria||d.categoria,imagem_url:x.imagem_url}));
  }catch{ /* relacionados são opcionais; o item continua válido */ }
  return (<><script type="application/ld+json" dangerouslySetInnerHTML={{__html: JSON.stringify(jsonLd)}} /><NoticiaReporter entryTipo="item" entryId={d.id} categoria={d.categoria} /><LeituraPremium detalhe={d} relacionados={relacionados} heroSrc={heroSrc} imagemReal={imagemReal} /><div className="mx-auto mt-6 max-w-3xl px-4"><CoberturaCompleta tipo="item" id={d.id} /><div className="mt-6 flex flex-wrap gap-2"><Button asChild variant="outline" className="min-h-[44px] border-[var(--cor-borda)]"><Link href="/">Voltar ao início</Link></Button><Button asChild variant="outline" className="min-h-[44px] border-[var(--cor-borda)]"><Link href="/arquivo">Ver arquivo</Link></Button></div></div></>);
}
