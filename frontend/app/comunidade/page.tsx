import type { Metadata } from "next";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { SITE_NAME } from "@/lib/site";
import { obterPublicacoes, type Publicacao } from "@/lib/api";
export const metadata: Metadata = { title: `Comunidade - ${SITE_NAME}` };
export const revalidate=30;
async function getPubs(): Promise<Publicacao[]>{ try{ const p=await obterPublicacoes({destaque:true}); return p?.length? p: [];}catch{ return [{id:1,autor:1,autor_nome:"Autor Mock",titulo:"Opiniao em destaque (mock)",conteudo:"Conteudo mock - API offline",tipo:"opiniao",status:"publicado",categoria:"politica",tags:["mock"],news_cluster:null,news_item:null,destaque:true,criado_em:new Date().toISOString(),publicado_em:new Date().toISOString()}]; } }
export default async function Page(){
  const pubs=await getPubs();
  return (<div className="mx-auto max-w-3xl space-y-4 py-6"><div className="hud-line" aria-hidden /><div className="flex items-center justify-between"><h1 className="text-2xl font-bold text-[var(--cor-texto)]">Comunidade</h1><Button asChild className="bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)] min-h-[44px]"><Link href="/comunidade/nova">Nova publicacao</Link></Button></div>{pubs.length? <div className="grid gap-3">{pubs.map((p)=> (<Link key={p.id} href={`/comunidade/${p.id}`} className="block rounded-[var(--raio-lg)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] p-4 hover:bg-[var(--cor-primaria-suave)]"><div className="flex items-center gap-2"><Badge variant="outline" className="border-[var(--cor-borda)]">{p.tipo}</Badge><span className="text-xs text-[var(--cor-texto-suave)]">{p.categoria} - {p.autor_nome}</span></div><p className="mt-1 font-medium text-[var(--cor-texto)]">{p.titulo}</p></Link>))}</div> : <Card className="bento border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]"><CardContent className="p-6 text-sm text-[var(--cor-texto-suave)]">Nenhuma publicacao ainda.</CardContent></Card>}</div>);
}
