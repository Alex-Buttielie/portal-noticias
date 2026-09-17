import type { Metadata } from "next";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { SITE_NAME } from "@/lib/site";
import { obterPlanos, type Plano } from "@/lib/api";
export const metadata: Metadata = { title: `Planos - ${SITE_NAME}` };
export const revalidate = 60;
async function getPlanos(): Promise<Plano[]>{ try{ const p=await obterPlanos(); return p?.length? p: [];}catch{ return [{id:1,nome:"Free",preco:"0.00",duracao_dias:0},{id:2,nome:"Premium",preco:"29.90",duracao_dias:30}]; } }
export default async function Page(){
  const planos=await getPlanos();
  return (<div className="mx-auto max-w-4xl space-y-4 py-6"><div className="hud-line" aria-hidden /><div className="rounded-[var(--raio-lg)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] p-6"><h1 className="text-2xl font-bold text-[var(--cor-texto)]">Planos</h1><p className="text-sm text-[var(--cor-texto-suave)]">Escolha seu acesso - bento HUD</p></div><div className="grid gap-4 md:grid-cols-2">{planos.map((p)=> (<Card key={p.id} className="bento border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]"><CardHeader><CardTitle className="flex items-center justify-between">{p.nome}<Badge variant="outline" className="border-[var(--cor-borda)]">{p.duracao_dias? `${p.duracao_dias}d`:"gratis"}</Badge></CardTitle><CardDescription className="text-[var(--cor-texto-suave)]">R$ {p.preco}</CardDescription></CardHeader><CardContent><Button className="w-full bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)] min-h-[44px]">Assinar</Button></CardContent></Card>))}</div></div>);
}
