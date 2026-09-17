import type { Metadata } from "next";
import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { SITE_NAME, SITE_URL } from "@/lib/site";
import { obterPublicacao } from "@/lib/api";
export async function generateMetadata({params}:{params:{id:string}}): Promise<Metadata>{ return { title: `Publicacao #${params.id} - ${SITE_NAME}`, openGraph:{ url:`${SITE_URL}/comunidade/${params.id}` } }; }
export function generateStaticParams(){ return [{id:"1"}]; }
export const revalidate=60;
export default async function Page({params}:{params:{id:string}}){
  const id=Number(params.id);
  let pub:any=null;
  try{ pub=await obterPublicacao(null, Number.isFinite(id)? id:1);}catch{}
  if(!pub) pub={id, titulo:`Publicacao #${params.id} (mock - API offline)`, conteudo:"Conteudo mock para nao quebrar build.", tipo:"opiniao", categoria:"geral", autor_nome:"Autor Mock", destaque:false, criado_em:new Date().toISOString()};
  return (<div className="mx-auto max-w-2xl space-y-4 py-6"><div className="hud-line" aria-hidden /><div className="text-xs text-[var(--cor-texto-suave)]"><Link href="/comunidade" className="hover:underline">Comunidade</Link> - #{pub.id}</div><h1 className="text-2xl font-bold text-[var(--cor-texto)]">{pub.titulo}</h1><div className="flex gap-2"><Badge variant="outline" className="border-[var(--cor-borda)]">{pub.tipo}</Badge><Badge variant="outline" className="border-[var(--cor-borda)]">{pub.categoria}</Badge><span className="text-xs text-[var(--cor-texto-suave)]">por {pub.autor_nome}</span></div><Card className="bento border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]"><CardContent className="prose max-w-none p-5 prose-p:text-[var(--cor-texto)]"><p className="whitespace-pre-wrap text-[var(--cor-texto)]">{pub.conteudo}</p></CardContent></Card></div>);
}
