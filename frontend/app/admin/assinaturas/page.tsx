"use client";
import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { useAuth } from "@/lib/auth-context";
import * as api from "@/lib/api";
export default function Page(){
  const { token } = useAuth(); const [itens,setItens]=useState<api.AdminAssinatura[]>([]); const [busca,setBusca]=useState(""); const [loading,setLoading]=useState(false); const [err,setErr]=useState<string|null>(null);
  const carregar=async()=>{ setErr(null); setLoading(true); try{ const r=await api.adminListarAssinaturas(token||"",{search:busca||undefined}); setItens(r.results||[]);}catch(e:any){ setErr(e?.message||"Falha ao carregar — tente novamente"); setItens([{id:1,user_email:"user@exemplo.com",user_nome:"Usuário Exemplo",plan:{id:2,nome:"Premium",preco:"29.90",duracao_dias:30},status:"ativa",preco_cobrado:"29.90",criado_em:new Date().toISOString()}]);} finally{ setLoading(false); } };
  return (<div className="space-y-4"><Card className="bento border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]"><CardHeader><CardTitle>Assinaturas</CardTitle></CardHeader><CardContent className="space-y-3">
    <div className="flex gap-2"><Input placeholder="Buscar por email..." value={busca} onChange={e=>setBusca(e.target.value)} className="bg-[var(--cor-fundo-card)]" /><Button onClick={carregar} disabled={loading} className="bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)] min-h-[44px]">{loading?"Buscando...":"Buscar"}</Button></div>
    {err&&<p className="rounded-md border border-[var(--cor-erro)] bg-[var(--cor-erro-suave)] px-3 py-2 text-sm text-[var(--cor-erro)]">{err}</p>}
    <div className="grid gap-2">{itens.map((a)=> (<div key={a.id} className="rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-3"><div className="flex items-center gap-2"><Badge variant="outline" className="border-[var(--cor-borda)]">{a.status}</Badge><span className="text-sm text-[var(--cor-texto)]">{a.user_email}</span></div><p className="text-xs text-[var(--cor-texto-suave)]">{a.plan.nome} - R$ {a.preco_cobrado} - {new Date(a.criado_em).toLocaleDateString("pt-BR")}</p></div>))}</div>
  </CardContent></Card></div>);
}
