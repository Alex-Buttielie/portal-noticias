"use client";
import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/lib/auth-context";
import * as api from "@/lib/api";
export default function Page(){
  const { token } = useAuth(); const [planos,setPlanos]=useState<api.Plano[]>([]); const [nome,setNome]=useState(""); const [preco,setPreco]=useState(""); const [dias,setDias]=useState("30"); const [err,setErr]=useState<string|null>(null); const [loading,setLoading]=useState(false);
  const carregar=async()=>{ setErr(null); setLoading(true); try{ const r=await api.adminListarPlanos(token||""); const arr=(r as any).results ?? r; setPlanos(Array.isArray(arr)?arr:[]);}catch(e:any){ setErr(e?.message||"API offline - mock"); setPlanos([{id:1,nome:"Premium",preco:"29.90",duracao_dias:30},{id:2,nome:"Free",preco:"0.00",duracao_dias:0}]);} finally{ setLoading(false); } };
  const criar=async()=>{ setErr(null); try{ await api.adminCriarPlano(token||"",{nome,preco,duracao_dias:Number(dias)}); setNome(""); setPreco(""); await carregar();}catch(e:any){ setErr(e?.message||"Falha ao criar."); } };
  return (<div className="space-y-4"><Card className="bento border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]"><CardHeader><CardTitle>Planos</CardTitle></CardHeader><CardContent className="space-y-3">
    <Button onClick={carregar} disabled={loading} className="bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)] min-h-[44px]">{loading?"Carregando...":"Carregar"}</Button>
    {err&&<p className="rounded-md border border-[var(--cor-erro)] bg-[var(--cor-erro-suave)] px-3 py-2 text-sm text-[var(--cor-erro)]">{err}</p>}
    <div className="grid gap-2">{planos.map((p)=> (<div key={p.id} className="flex items-center justify-between rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-3"><div><p className="font-medium text-[var(--cor-texto)]">{p.nome}</p><p className="text-xs text-[var(--cor-texto-suave)]">R$ {p.preco} - {p.duracao_dias}d</p></div><Button size="sm" variant="outline" onClick={async()=>{ try{ await api.adminExcluirPlano(token||"",p.id); await carregar();}catch(e:any){ setErr(e?.message||"Falha ao excluir."); } }}>Excluir</Button></div>))}</div>
    <div className="rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-3 space-y-2"><p className="text-sm font-medium text-[var(--cor-texto)]">Criar plano</p><div className="grid gap-2 md:grid-cols-3"><div className="space-y-1"><Label>Nome</Label><Input value={nome} onChange={e=>setNome(e.target.value)} placeholder="Ex: Premium" /></div><div className="space-y-1"><Label>Preco</Label><Input value={preco} onChange={e=>setPreco(e.target.value)} placeholder="29.90" /></div><div className="space-y-1"><Label>Dias</Label><Input value={dias} onChange={e=>setDias(e.target.value)} placeholder="30" /></div></div><Button onClick={criar} className="bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)] min-h-[44px]">Criar</Button></div>
  </CardContent></Card></div>);
}
