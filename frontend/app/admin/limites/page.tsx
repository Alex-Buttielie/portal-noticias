"use client";
import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { useAuth } from "@/lib/auth-context";
import * as api from "@/lib/api";
type Lim = { id:number; chave:string; plano:string; valor:string; descricao:string };
export default function Page(){
  const { token } = useAuth();
  const [itens,setItens]=useState<Lim[]>([]); const [loading,setLoading]=useState(false); const [err,setErr]=useState<string|null>(null); const [editId,setEditId]=useState<number|null>(null); const [valor,setValor]=useState(""); const [desc,setDesc]=useState("");
  const carregar=async()=>{ setErr(null); setLoading(true); try{ const r=await api.adminListarLimites(token||""); setItens((r.results as Lim[])||[]);}catch(e:any){ setErr(e?.message||"Falha - API offline"); setItens([{id:1,chave:"feed_max_itens",plano:"free",valor:"20",descricao:"Mock - limite de itens no feed"},{id:2,chave:"radar_credito",plano:"premium",valor:"100",descricao:"Mock - creditos radar"}]);} finally{ setLoading(false);} };
  const salvar=async(id:number)=>{ try{ await api.adminAtualizarLimite(token||"",id,{valor,descricao:desc}); setEditId(null); await carregar();}catch(e:any){ setErr(e?.message||"Falha ao salvar.");} };
  return (<div className="space-y-4"><Card className="bento"><CardHeader><CardTitle>Limites por plano</CardTitle><CardDescription className="text-[var(--cor-texto-suave)]">FeatureLimit — gating: valor por chave/plano, log de alteração</CardDescription></CardHeader><CardContent className="space-y-3">
    <Button onClick={carregar} disabled={loading} className="min-h-[44px] bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]">{loading?"Carregando...":"Carregar limites"}</Button>
    {err&&<p className="rounded-md border border-[var(--cor-erro)] bg-[var(--cor-erro-suave)] px-3 py-2 text-sm text-[var(--cor-erro)]">{err}</p>}
    <div className="grid gap-2">{itens.map((l)=> (<div key={l.id} className="rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-3"><div className="flex flex-wrap items-center gap-2"><Badge variant="outline" className="border-[var(--cor-borda)]">{l.chave}</Badge><Badge className="bg-[var(--cor-neon-violeta)] text-[var(--cor-texto-invertido)]">{l.plano}</Badge><span className="text-sm font-mono text-[var(--cor-texto)]">{l.valor}</span></div><p className="mt-1 text-xs text-[var(--cor-texto-suave)]">{l.descricao||"—"}</p>{editId===l.id? (<div className="mt-2 grid gap-2 md:grid-cols-[1fr_1fr_auto]"><div><Label>Valor</Label><Input value={valor} onChange={e=>setValor(e.target.value)} /></div><div><Label>Descricao</Label><Input value={desc} onChange={e=>setDesc(e.target.value)} /></div><div className="flex items-end gap-2"><Button size="sm" onClick={()=>salvar(l.id)} className="bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]">Salvar</Button><Button size="sm" variant="ghost" onClick={()=>setEditId(null)}>Cancelar</Button></div></div>):(<Button size="sm" variant="outline" className="mt-2" onClick={()=>{ setEditId(l.id); setValor(l.valor); setDesc(l.descricao||""); }}>Editar</Button>)} </div>))}</div>
    {!itens.length&&!loading&&<p className="text-sm text-[var(--cor-texto-suave)]">Clique em Carregar limites.</p>}
  </CardContent></Card></div>);
}
