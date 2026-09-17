"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth-context";
import * as api from "@/lib/api";
export default function Page(){
  const { token } = useAuth(); const r=useRouter();
  const [solic,setSolic]=useState<api.SolicitacaoCredenciamento|null>(null); const [perfil,setPerfil]=useState<api.PerfilJornalista|null>(null); const [loading,setLoading]=useState(true); const [err,setErr]=useState<string|null>(null);
  useEffect(()=>{ if(!token) return; (async()=>{ setLoading(true); try{ const [s,p]=await Promise.all([api.obterMinhaSolicitacaoCredenciamento(token).catch(()=>null), api.obterMeuPerfilJornalista(token).catch(()=>null)]); setSolic(s); setPerfil(p);}catch(e:any){ setErr(e?.message||"Falha ao carregar."); } finally{ setLoading(false); } })(); },[token]);
  if(!token) return (<div className="mx-auto max-w-xl py-8"><Card className="bento border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]"><CardContent className="p-6 text-center"><p className="text-sm text-[var(--cor-texto-suave)]">Entre para ver status.</p><Button onClick={()=>r.push("/login")} className="mt-3 bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]">Entrar</Button></CardContent></Card></div>);
  if(loading) return <div className="mx-auto max-w-xl py-8"><div className="h-24 animate-pulse rounded-[var(--raio-lg)] bg-[var(--cor-skeleton-base)]" /></div>;
  return (<div className="mx-auto max-w-2xl space-y-4 py-6"><div className="hud-line" aria-hidden />
    <Card className="bento border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]"><CardHeader><CardTitle>Status do credenciamento</CardTitle><CardDescription className="text-[var(--cor-texto-suave)]">Acompanhe sua solicitação</CardDescription></CardHeader><CardContent className="space-y-4">
      {err&&<p className="rounded-md border border-[var(--cor-erro)] bg-[var(--cor-erro-suave)] px-3 py-2 text-sm text-[var(--cor-erro)]">{err}</p>}
      {solic? (<div className="rounded-[var(--raio-md)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-3"><p className="text-sm text-[var(--cor-texto)]">Solicitacao #{solic.id} - <Badge className="bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]">{solic.status}</Badge></p><p className="text-xs text-[var(--cor-texto-suave)]">{solic.cidade}/{solic.uf} - {new Date(solic.criado_em).toLocaleDateString("pt-BR")}</p>{solic.motivo_decisao&&<p className="mt-2 text-sm text-[var(--cor-texto-suave)]">{solic.motivo_decisao}</p>}</div>) : <p className="text-sm text-[var(--cor-texto-suave)]">Nenhuma solicitacao encontrada - <a href="/jornalista/solicitar" className="text-[var(--cor-primaria)] underline">solicitar</a>.</p>}
      {perfil&&<div className="rounded-[var(--raio-md)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-3"><p className="text-sm font-medium text-[var(--cor-texto)]">Perfil jornalistico</p><p className="text-sm text-[var(--cor-texto-suave)]">{perfil.mini_bio}</p><div className="mt-2 flex gap-2"><Badge variant="outline" className="border-[var(--cor-borda)]">{perfil.selo_ativo?"selo ativo":"sem selo"}</Badge>{perfil.suspenso&&<Badge className="bg-[var(--cor-erro)] text-[var(--cor-texto-invertido)]">suspenso</Badge>}</div></div>}
    </CardContent></Card></div>);
}
