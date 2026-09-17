"use client";
import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { obterTodasLeituras } from "@/lib/intent";
import { categoriasPorAfinidade } from "@/lib/personalizar";
import { useAuth } from "@/lib/auth-context";
export default function Page(){
  const { usuario } = useAuth();
  const [cats,setCats]=useState<string[]>([]);
  const [leituras,setLeituras]=useState<Record<string,number>>({});
  useEffect(()=>{ setLeituras(obterTodasLeituras()); setCats(categoriasPorAfinidade({interesses: usuario?.interesses || []})); },[usuario]);
  return (<div className="mx-auto max-w-2xl space-y-4 py-6"><div className="hud-line" aria-hidden />
    <Card className="bento border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]"><CardHeader><CardTitle>Personalizar</CardTitle><CardDescription className="text-[var(--cor-texto-suave)]">HUD bento - usa lib/personalizar.ts</CardDescription></CardHeader><CardContent className="space-y-4">
      <div><p className="text-sm font-medium text-[var(--cor-texto)]">Afinidade</p>{cats.length? <div className="mt-2 flex flex-wrap gap-2">{cats.map((c)=> (<Badge key={c} className="bg-[var(--cor-neon-ciano)] text-[var(--cor-texto-invertido)] capitalize">{c}</Badge>))}</div> : <p className="text-sm text-[var(--cor-texto-suave)]">Sem sinal ainda - leia noticias para personalizar.</p>}</div>
      <div><p className="text-sm font-medium text-[var(--cor-texto)]">Leituras por categoria</p>{Object.keys(leituras).length? <div className="mt-2 grid grid-cols-2 gap-2">{Object.entries(leituras).map(([k,v])=> (<div key={k} className="rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-2"><p className="text-xs capitalize text-[var(--cor-texto-suave)]">{k}</p><p className="font-bold text-[var(--cor-texto)]">{v}</p></div>))}</div> : <p className="text-sm text-[var(--cor-texto-suave)]">Nenhuma leitura registrada.</p>}</div>
      <Button variant="outline" onClick={()=>{ try{ localStorage.removeItem("portal_noticias_intent"); }catch{} location.reload(); }} className="min-h-[44px]">Limpar sinais</Button>
    </CardContent></Card></div>);
}
