"use client";
import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { useAuth } from "@/lib/auth-context";
import * as api from "@/lib/api";
export default function Page(){
  const { token } = useAuth();
  const [busca,setBusca]=useState(""); const [itens,setItens]=useState<api.AdminUsuario[]>([]); const [loading,setLoading]=useState(false); const [err,setErr]=useState<string|null>(null);
  const buscar=async()=>{ setErr(null); setLoading(true); try{ const r=await api.adminListarUsuarios(token||"",{search:busca||undefined}); setItens(r.results||[]);}catch(e:any){ setErr(e?.message||"Falha - API offline (mock fallback)"); setItens([{id:1,email:"admin@exemplo.com",nome:"Admin Mock",papel:"admin",is_active:true,email_verificado:true,date_joined:new Date().toISOString()},{id:2,email:"user@exemplo.com",nome:"User Mock",papel:"free",is_active:true,email_verificado:false,date_joined:new Date().toISOString()}]);} finally{ setLoading(false); } };
  const alternar=async(id:number,papel:string)=>{ try{ await api.adminAtualizarUsuario(token||"",id,{papel: papel==="admin"?"free":"admin"}); await buscar();}catch(e:any){ setErr(e?.message||"Falha ao atualizar."); } };
  return (<div className="space-y-4"><Card className="bento border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]"><CardHeader><CardTitle>Usuarios</CardTitle></CardHeader><CardContent className="space-y-3">
    <div className="flex gap-2"><Input placeholder="Buscar por email..." value={busca} onChange={e=>setBusca(e.target.value)} className="bg-[var(--cor-fundo-card)]" /><Button onClick={buscar} disabled={loading} className="bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)] min-h-[44px]">{loading?"Buscando...":"Buscar"}</Button></div>
    {err&&<p className="rounded-md border border-[var(--cor-erro)] bg-[var(--cor-erro-suave)] px-3 py-2 text-sm text-[var(--cor-erro)]">{err}</p>}
    <div className="grid gap-2">{itens.map((u)=> (<div key={u.id} className="flex items-center justify-between rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-3"><div><p className="font-medium text-[var(--cor-texto)]">{u.email}</p><p className="text-xs text-[var(--cor-texto-suave)]">{u.nome} - {new Date(u.date_joined).toLocaleDateString("pt-BR")}</p></div><div className="flex items-center gap-2"><Badge variant="outline" className="border-[var(--cor-borda)]">{u.papel}</Badge><Button size="sm" variant="outline" onClick={()=>alternar(u.id,u.papel)}>Alternar papel</Button></div></div>))}</div>
    {!itens.length&&!loading&&<p className="text-sm text-[var(--cor-texto-suave)]">Clique em Buscar para carregar.</p>}
  </CardContent></Card></div>);
}
