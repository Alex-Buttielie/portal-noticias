"use client";
import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { useAuth } from "@/lib/auth-context";
import * as api from "@/lib/api";
export default function Page(){
  const { token } = useAuth(); const [itens,setItens]=useState<any[]>([]); const [motivo,setMotivo]=useState(""); const [loading,setLoading]=useState(false); const [err,setErr]=useState<string|null>(null);
  const carregar=async()=>{ setErr(null); setLoading(true); try{ const r=await api.adminListarDenuncias(token||""); setItens((r as any).results||[]);}catch(e:any){ setErr(e?.message||"API offline - mock"); setItens([{id:1,motivo:"spam",detalhe:"Conteudo repetido",status:"pendente",denunciante_email:"denunciante@exemplo.com",criado_em:new Date().toISOString(),alvo_repr:"Publicacao #1"}]);} finally{ setLoading(false); } };
  const agir=async(id:number,tipo:string)=>{ try{ await api.adminAplicarAcaoDenuncia(token||"",id,{tipo,motivo: motivo||"acao administrativa"}); await carregar(); setMotivo("");}catch(e:any){ setErr(e?.message||"Falha na acao."); } };
  return (<div className="space-y-4"><Card className="bento border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]"><CardHeader><CardTitle>Moderacao - Denuncias</CardTitle></CardHeader><CardContent className="space-y-3">
    <Button onClick={carregar} disabled={loading} className="bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)] min-h-[44px]">{loading?"Carregando...":"Carregar denuncias"}</Button>
    {err&&<p className="rounded-md border border-[var(--cor-erro)] bg-[var(--cor-erro-suave)] px-3 py-2 text-sm text-[var(--cor-erro)]">{err}</p>}
    <div className="space-y-2"><Label htmlFor="motivo">Motivo da acao</Label><Textarea id="motivo" value={motivo} onChange={e=>setMotivo(e.target.value)} placeholder="Justificativa..." rows={2} /></div>
    <div className="grid gap-2">{itens.map((d)=> (<div key={d.id} className="rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-3"><div className="flex items-center gap-2"><Badge variant="outline" className="border-[var(--cor-borda)]">{d.status}</Badge><span className="text-xs text-[var(--cor-texto-suave)]">{d.motivo} - {d.denunciante_email}</span></div><p className="mt-1 text-sm text-[var(--cor-texto)]">{d.detalhe}</p><p className="text-xs text-[var(--cor-texto-suave)]">{d.alvo_repr}</p><div className="mt-2 flex gap-2"><Button size="sm" onClick={()=>agir(d.id,"remover")} className="bg-[var(--cor-erro)] text-[var(--cor-texto-invertido)]">Remover</Button><Button size="sm" variant="outline" onClick={()=>agir(d.id,"ignorar")}>Ignorar</Button></div></div>))}</div>
  </CardContent></Card></div>);
}
