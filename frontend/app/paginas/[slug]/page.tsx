import type { Metadata } from "next";
import { Card, CardContent } from "@/components/ui/card";
import { SITE_NAME, SITE_URL } from "@/lib/site";
import { obterPaginaEditorial } from "@/lib/api";
export async function generateMetadata({params}:{params:{slug:string}}): Promise<Metadata>{ return { title: `${params.slug} - ${SITE_NAME}`, openGraph:{ title: params.slug, url: `${SITE_URL}/paginas/${params.slug}` } }; }
export function generateStaticParams(){ return [{slug:"termos"}, {slug:"sobre"}]; }
export const revalidate=60;
export default async function Page({params}:{params:{slug:string}}){
  let pagina:any=null; try{ pagina=await obterPaginaEditorial(params.slug);}catch{ pagina={titulo: params.slug, conteudo:`<p>Conteudo mock para <strong>${params.slug}</strong> - API offline. Pagina editorial com fallback para nao quebrar build.</p>`, atualizado_em: new Date().toISOString()}; }
  return (<div className="mx-auto max-w-3xl space-y-4 py-6"><div className="hud-line" aria-hidden /><Card className="bento border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]"><CardContent className="prose max-w-none p-6 prose-headings:text-[var(--cor-texto)] prose-p:text-[var(--cor-texto-suave)]"><h1 className="capitalize text-[var(--cor-texto)]">{pagina.titulo}</h1><div dangerouslySetInnerHTML={{__html: pagina.conteudo}} /><p className="text-xs text-[var(--cor-texto-suave)]">Atualizado em {new Date(pagina.atualizado_em).toLocaleDateString("pt-BR")}</p></CardContent></Card></div>);
}
