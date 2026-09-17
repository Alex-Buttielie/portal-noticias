"use client";
import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useAuth } from "@/lib/auth-context";
import * as api from "@/lib/api";
export default function Page(){
  const { token } = useAuth(); const [itens,setItens]=useState<api.AdminFilaItem[]>([]); const [loading,setLoading]=useState(false); const [err,setErr]=useState<string|null>(null);
  const carregar=async()=>{ setErr(null); setLoading(true); try{ const r=await api.adminListarFila(token||""); setItens(r.results||[]);}catch(e:any){ setErr(e?.message||"API offline - mock"); setItens([{tipo:"item",id:1,titulo:"Item mock para curadoria",categoria:"geral",status_revisao:"pendente",nome_fonte:"Fonte Mock",url_fonte_original:"https://example.com",urgente:false,cluster:null,cluster_titulo:"",timestamp_ingestao:new Date().toISOString()}]);} finally{ setLoading(false); } };
  const decidir=async(id:number,acao:"aprovar"|"rejeitar")=>{ try{ await api.adminDecidirFila(token||"",id,acao); await carregar();}catch(e:any){ setErr(e?.message||"Falha na decisao."); } };
  return (<div className="space-y-4"><Card className="bento border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]"><CardHeader><CardTitle>Fila de curadoria</CardTitle></CardHeader><CardContent className="space-y-3">
    <Button onClick={carregar} disabled={loading} className="bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)] min-h-[44px]">{loading?"Carregando...":"Carregar fila"}</Button>
    {err&&<p className="rounded-md border border-[var(--cor-erro)] bg-[var(--cor-erro-suave)] px-3 py-2 text-sm text-[var(--cor-erro)]">{err}</p>}
    <div className="grid gap-2">{itens.map((it)=> (<div key={`${it.tipo}-${it.id}`} className="rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-3"><div className="flex items-center gap-2"><Badge variant="outline" className="border-[var(--cor-borda)]">{it.status_revisao}</Badge>{it.urgente&&<Badge className="bg-[var(--cor-sinal)] text-[var(--cor-texto-invertido)]">urgente</Badge>}<span className="text-xs text-[var(--cor-texto-suave)]">{it.categoria} - {it.nome_fonte}</span></div><p className="mt-1 font-medium text-[var(--cor-texto)]">{it.titulo}</p><div className="mt-2 flex gap-2"><Button size="sm" onClick={()=>decidir(it.id,"aprovar")} className="bg-[var(--cor-sucesso)] text-[var(--cor-texto-invertido)]">Aprovar</Button><Button size="sm" variant="destructive" onClick={()=>decidir(it.id,"rejeitar")}>Rejeitar</Button></div></div>))}</div>
  </CardContent></Card></div>);
}
