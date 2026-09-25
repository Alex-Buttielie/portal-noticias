"use client";
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { useAuth } from "@/lib/auth-context";
import * as api from "@/lib/api";
import { useQueryAdminUsuarios } from "@/lib/queries";
import { queryKeys } from "@/lib/query-keys";
import { formatarDataCurta } from "@/lib/datas";

const MOCK: api.AdminUsuario[] = [
  { id: 1, email: "admin@exemplo.com", nome: "Admin Exemplo", papel: "admin", is_active: true, email_verificado: true, date_joined: new Date().toISOString() },
  { id: 2, email: "user@exemplo.com", nome: "Usuário Exemplo", papel: "free", is_active: true, email_verificado: false, date_joined: new Date().toISOString() },
];

export default function Page(){
  const { usuario, token } = useAuth();
  const cliente = useQueryClient();
  const [busca,setBusca]=useState("");
  const [buscaAplicada,setBuscaAplicada]=useState<string|null>(null);
  const [erroMutacao,setErroMutacao]=useState<string|null>(null);
  // A tela só carrega após o clique em "Buscar" (buscaAplicada sai de null).
  const consulta=useQueryAdminUsuarios({ token, usuarioId: usuario?.id ?? 0, busca: buscaAplicada, habilitada: buscaAplicada !== null });
  const itens=consulta.isError?MOCK:(consulta.data?.results ?? []);
  const loading=consulta.isFetching;
  const err=consulta.isError
    ? (consulta.error instanceof Error ? consulta.error.message : "Falha ao carregar — tente novamente")
    : erroMutacao;
  const buscar=()=>{ setErroMutacao(null); setBuscaAplicada(busca || ""); void consulta.refetch(); };
  const alternar=async(id:number,papel:string)=>{ try{ await api.adminAtualizarUsuario(token||"",id,{papel: papel==="admin"?"free":"admin"}); await cliente.invalidateQueries({ queryKey: queryKeys.admin.usuariosRaiz() }); }catch(e:any){ setErroMutacao(e?.message||"Falha ao atualizar."); } };
  return (<div className="space-y-4"><Card className="bento border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]"><CardHeader><CardTitle>Usuarios</CardTitle></CardHeader><CardContent className="space-y-3">
    <div className="flex gap-2"><Input placeholder="Buscar por email..." value={busca} onChange={e=>setBusca(e.target.value)} className="bg-[var(--cor-fundo-card)]" /><Button onClick={buscar} disabled={loading} className="bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)] min-h-[44px]">{loading?"Buscando...":"Buscar"}</Button></div>
    {err&&<p className="rounded-md border border-[var(--cor-erro)] bg-[var(--cor-erro-suave)] px-3 py-2 text-sm text-[var(--cor-erro)]">{err}</p>}
    <div className="grid gap-2">{itens.map((u)=> (<div key={u.id} className="flex items-center justify-between rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-3"><div><p className="font-medium text-[var(--cor-texto)]">{u.email}</p><p className="text-xs text-[var(--cor-texto-suave)]">{u.nome} - {formatarDataCurta(u.date_joined)}</p></div><div className="flex items-center gap-2"><Badge variant="outline" className="border-[var(--cor-borda)]">{u.papel}</Badge><Button size="sm" variant="outline" onClick={()=>alternar(u.id,u.papel)}>Alternar papel</Button></div></div>))}</div>
    {!itens.length&&!loading&&<p className="text-sm text-[var(--cor-texto-suave)]">Clique em Buscar para carregar.</p>}
  </CardContent></Card></div>);
}