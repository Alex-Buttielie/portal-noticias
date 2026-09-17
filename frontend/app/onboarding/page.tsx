"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { useAuth } from "@/lib/auth-context";
import * as api from "@/lib/api";
import BuscaCep from "@/components/BuscaCep";
const CATS = ["política","economia","tecnologia","esportes","cultura","saúde","mundo","cidades"];
export default function Page(){
  const { token, usuario } = useAuth();
  const r = useRouter();
  const [sel,setSel] = useState<string[]>(usuario?.interesses ?? []);
  const [loc,setLoc] = useState(usuario?.localidade ?? "");
  const [err,setErr] = useState<string|null>(null);
  const [ok,setOk] = useState(false);
  const toggle = (c:string)=> setSel(s=> s.includes(c) ? s.filter(x=>x!==c) : [...s,c]);
  const salvar = async (pular?:boolean)=>{
    setErr(null);
    if(!token){ setErr("Entre para salvar onboarding."); return; }
    try{ await api.atualizarOnboarding(token,{interesses:sel,localidade:loc,pular}); setOk(true); setTimeout(()=>r.push("/"),800);}catch(e:any){ setErr(e?.message||"Falha ao salvar."); }
  };
  if(!token) return (<div className="mx-auto max-w-xl py-8"><Card className="bento border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]"><CardContent className="p-6 text-center"><p className="text-sm text-[var(--cor-texto-suave)]">Entre para personalizar sua experiência.</p><Button onClick={()=>r.push("/login")} className="mt-3 bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]">Entrar</Button></CardContent></Card></div>);
  return (<div className="mx-auto max-w-2xl space-y-4 py-6"><div className="hud-line" aria-hidden />
    <Card className="bento border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]"><CardHeader><CardTitle>Onboarding</CardTitle><CardDescription className="text-[var(--cor-texto-suave)]">Escolha interesses e localidade — HUD bento • vidro</CardDescription></CardHeader><CardContent className="space-y-4">
      <div><p className="mb-2 text-sm font-medium text-[var(--cor-texto)]">Interesses</p><div className="flex flex-wrap gap-2">{CATS.map(c=>(<button key={c} type="button" onClick={()=>toggle(c)} className={"rounded-full border px-3 py-1 text-sm capitalize min-h-[36px] "+(sel.includes(c)?"bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)] border-[var(--cor-primaria)]":"border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] text-[var(--cor-texto)]")} aria-pressed={sel.includes(c)}>{c}</button>))}</div></div>
      <div className="space-y-2"><p className="text-sm font-medium text-[var(--cor-texto)]">Encontre sua localidade por CEP</p><BuscaCep compact valorInicial={loc} onEndereco={(e)=> setLoc(`${e.localidade}, ${e.uf}`)} /></div>
      <div className="space-y-2"><Label htmlFor="loc">Localidade</Label><Input id="loc" placeholder="Ex: São Paulo, SP" value={loc} onChange={e=>setLoc(e.target.value)} className="bg-[var(--cor-fundo-card)]" /><p className="text-xs text-[var(--cor-texto-suave)]">Preenchido automaticamente ao usar o CEP — edite se necessário.</p></div>
      {err&&<p role="alert" className="rounded-md border border-[var(--cor-erro)] bg-[var(--cor-erro-suave)] px-3 py-2 text-sm text-[var(--cor-erro)]">{err}</p>}
      {ok&&<p className="rounded-md border border-[var(--cor-sucesso)] bg-[var(--cor-sucesso-suave)] px-3 py-2 text-sm text-[var(--cor-sucesso)]">Salvo — redirecionando…</p>}
      <div className="flex gap-2"><Button onClick={()=>salvar(false)} className="bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)] min-h-[44px]">Salvar</Button><Button variant="outline" onClick={()=>salvar(true)} className="min-h-[44px]">Pular</Button></div>
      <div className="flex gap-2 text-xs text-[var(--cor-texto-suave)]"><Badge variant="outline" className="border-[var(--cor-borda)]">{sel.length} interesses</Badge><span>HUD • bento • neon contido</span></div>
    </CardContent></Card></div>);
}
