"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { obterSalvos, alternarSalvo } from "@/lib/bookmarks";
import type { FeedEntrada } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { useRouter } from "next/navigation";
export default function Page(){
  const { token, carregando } = useAuth();
  const r = useRouter();
  const [itens,setItens]=useState<FeedEntrada[]>([]);
  useEffect(()=>{ setItens(obterSalvos()); },[]);
  useEffect(()=>{ if(!carregando && !token) r.replace("/login"); },[carregando,token,r]);
  if(carregando) return <div className="h-24 animate-pulse bg-[var(--cor-skeleton-base)] rounded-[var(--raio-lg)]" />;
  return (<div className="mx-auto max-w-3xl space-y-4 py-6"><div className="hud-line" aria-hidden />
    <Card className="bento border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]"><CardHeader><CardTitle>Favoritos</CardTitle><CardDescription className="text-[var(--cor-texto-suave)]">Seus itens salvos neste aparelho</CardDescription></CardHeader><CardContent>
      {itens.length===0 ? <p className="text-sm text-[var(--cor-texto-suave)]">Nenhum salvo ainda. Salve noticias no botao compartilhar.</p> :
        <div className="grid gap-3">{itens.map((n)=> (<div key={`${n.tipo}-${n.id}`} className="flex items-start justify-between gap-3 rounded-[var(--raio-md)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-3"><div><Badge variant="outline" className="border-[var(--cor-borda)] capitalize">{n.categoria}</Badge><Link href={`/noticia/${n.id}`} className="mt-1 block font-medium text-[var(--cor-texto)] hover:text-[var(--cor-primaria)]">{n.titulo}</Link><p className="text-sm text-[var(--cor-texto-suave)] line-clamp-2">{n.resumo}</p></div><Button variant="outline" size="sm" onClick={()=>{ alternarSalvo(n); setItens(obterSalvos()); }} className="shrink-0">Remover</Button></div>))}</div>}
    </CardContent></Card></div>);
}
