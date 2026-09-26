import type { Metadata } from "next";
import { Card, CardContent } from "@/components/ui/card";
import { SITE_NAME, SITE_URL } from "@/lib/site";
import { obterPaginaEditorial } from "@/lib/api";
import { formatarDataCurta } from "@/lib/datas";
export async function generateMetadata({params}:{params:Promise<{slug:string}>}): Promise<Metadata>{ const {slug}=await params; return { title: `${slug} - ${SITE_NAME}`, openGraph:{ title: slug, url: `${SITE_URL}/paginas/${slug}` } }; }
export function generateStaticParams(){ return [{slug:"termos"}, {slug:"sobre"}]; }
export const revalidate=60;
export default async function Page({params}:{params:Promise<{slug:string}>}){
  const {slug}=await params;
  let pagina:any=null; try{ pagina=await obterPaginaEditorial(slug);}catch{ pagina={titulo: slug, conteudo:`<p>Conteúdo editorial para <strong>${slug}</strong> em preparação.</p>`, atualizado_em: new Date().toISOString()}; }
  return (<div className="mx-auto max-w-3xl space-y-4 py-6"><div className="hud-line" aria-hidden /><Card className="bento border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]"><CardContent className="prose max-w-none p-6 prose-headings:text-[var(--cor-texto)] prose-p:text-[var(--cor-texto-suave)]"><h1 className="capitalize text-[var(--cor-texto)]">{pagina.titulo}</h1><div dangerouslySetInnerHTML={{__html: pagina.conteudo}} /><p className="text-xs text-[var(--cor-texto-suave)]">Atualizado em {formatarDataCurta(pagina.atualizado_em)}</p></CardContent></Card></div>);
}
