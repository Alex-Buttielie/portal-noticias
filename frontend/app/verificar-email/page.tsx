"use client";
import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import * as api from "@/lib/api";
function VerificarForm(){
  const sp=useSearchParams(); const token=sp.get("token")||"";
  const [msg,setMsg]=useState<string|null>(null); const [err,setErr]=useState<string|null>(null); const [loading,setLoading]=useState(false);
  const verificar=async()=>{ setErr(null); setMsg(null); setLoading(true); try{ const r=await api.verificarEmail(token); setMsg(r.detail||"Email verificado."); }catch(e:any){ setErr(e?.message||"Token invalido."); } finally{ setLoading(false); } };
  return (<Card className="bento border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]"><CardHeader><CardTitle>Verificar email</CardTitle><CardDescription className="text-[var(--cor-texto-suave)]">Confirme seu cadastro</CardDescription></CardHeader><CardContent className="space-y-3">
    <p className="text-sm text-[var(--cor-texto-suave)]">Token: <span className="font-mono text-[var(--cor-texto)]">{token ? token.slice(0,16)+"..." : "ausente"}</span></p>
    {msg&&<p className="rounded-md border border-[var(--cor-sucesso)] bg-[var(--cor-sucesso-suave)] px-3 py-2 text-sm text-[var(--cor-sucesso)]">{msg}</p>}
    {err&&<p role="alert" className="rounded-md border border-[var(--cor-erro)] bg-[var(--cor-erro-suave)] px-3 py-2 text-sm text-[var(--cor-erro)]">{err}</p>}
    <Button onClick={verificar} disabled={!token||loading} className="w-full bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)] min-h-[44px]">{loading?"Verificando...":"Verificar"}</Button>
  </CardContent></Card>);
}
export default function Page(){ return (<div className="mx-auto max-w-md space-y-4 py-6"><div className="hud-line" aria-hidden /><Suspense fallback={<div className="h-24 animate-pulse rounded-[var(--raio-lg)] bg-[var(--cor-skeleton-base)]" />}><VerificarForm /></Suspense></div>); }
