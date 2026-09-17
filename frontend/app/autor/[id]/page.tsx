import type { Metadata } from "next";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { SITE_NAME } from "@/lib/site";
import { obterPerfilAutor } from "@/lib/api";
export async function generateMetadata({params}:{params:{id:string}}): Promise<Metadata>{ return { title:`Autor #${params.id} - ${SITE_NAME}` }; }
export function generateStaticParams(){ return [{id:"1"}]; }
export const revalidate=60;
export default async function Page({params}:{params:{id:string}}){
  const id=Number(params.id);
  let perfil:any=null; try{ perfil=await obterPerfilAutor(Number.isFinite(id)?id:1);}catch{ perfil={id, nome:`Autor #${params.id}`, credenciado:false, numero_seguidores:0, publicacoes:[]}; }
  return (<div className="mx-auto max-w-2xl space-y-4 py-6"><div className="hud-line" aria-hidden /><Card className="bento border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]"><CardHeader><CardTitle>{perfil.nome}</CardTitle></CardHeader><CardContent><div className="flex gap-2"><Badge className="bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]">{perfil.numero_seguidores} seguidores</Badge>{perfil.credenciado&&<Badge className="bg-[var(--cor-sucesso)] text-[var(--cor-texto-invertido)]">credenciado</Badge>}</div>{perfil.publicacoes?.length? <div className="mt-4 grid gap-2">{perfil.publicacoes.map((p:any)=> (<Link key={p.id} href={`/comunidade/${p.id}`} className="rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-3 hover:bg-[var(--cor-primaria-suave)]"><p className="font-medium text-[var(--cor-texto)]">{p.titulo}</p><p className="text-xs text-[var(--cor-texto-suave)]">{p.categoria} - {p.tipo}</p></Link>))}</div> : <p className="mt-3 text-sm text-[var(--cor-texto-suave)]">Nenhuma publicacao.</p>}</CardContent></Card></div>);
}
