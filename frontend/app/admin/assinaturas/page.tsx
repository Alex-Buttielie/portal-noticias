"use client";
import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { useAuth } from "@/lib/auth-context";
import * as api from "@/lib/api";
import { useQueryAdminAssinaturas } from "@/lib/queries";
import { formatarDataCurta } from "@/lib/datas";

/**
 * Sem `MOCK`: esta tela lista assinaturas reais (com e-mail e cobrança) e a
 * lista de exemplo anterior exibia uma assinatura fictícia de "29.90" como se
 * fosse um pagamento real. API fora do ar = estado explícito, lista vazia.
 */
export default function Page(){
  const { usuario, token } = useAuth();
  const [busca,setBusca]=useState("");
  const [buscaAplicada,setBuscaAplicada]=useState<string|null>(null);
  // A tela só carrega após o clique em "Buscar" (buscaAplicada sai de null).
  const consulta=useQueryAdminAssinaturas({ token, usuarioId: usuario?.id ?? 0, filtros: { busca: buscaAplicada }, habilitada: buscaAplicada !== null });
  const itens=consulta.isError?[]:(consulta.data?.results ?? []);
  const loading=consulta.isFetching;
  const err=consulta.isError
    ? (consulta.error instanceof Error ? consulta.error.message : "Falha ao carregar — tente novamente")
    : null;
  const carregar=()=>{ setBuscaAplicada(busca || ""); void consulta.refetch(); };
  return (<div className="space-y-4"><Card className="bento border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]"><CardHeader><CardTitle>Assinaturas</CardTitle></CardHeader><CardContent className="space-y-3">
    <div className="flex gap-2"><Input placeholder="Buscar por email..." value={busca} onChange={e=>setBusca(e.target.value)} className="bg-[var(--cor-fundo-card)]" /><Button onClick={carregar} disabled={loading} className="bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)] min-h-[44px]">{loading?"Buscando...":"Buscar"}</Button></div>
    {err&&<p role="alert" className="rounded-md border border-[var(--cor-erro)] bg-[var(--cor-erro-suave)] px-3 py-2 text-sm text-[var(--cor-texto)]">{err}</p>}
    {consulta.isError&&<p className="rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] px-3 py-2 text-sm text-[var(--cor-texto-suave)]">API indisponível — nenhuma assinatura foi carregada e nenhuma assinatura de exemplo é exibida.</p>}
    {consulta.isSuccess&&!loading&&!consulta.isError&&!itens.length&&<p className="text-sm text-[var(--cor-texto-suave)]">Nenhuma assinatura encontrada para este filtro.</p>}
    <div className="grid gap-2">{itens.map((a)=> (<div key={a.id} className="rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-3"><div className="flex items-center gap-2"><Badge variant="outline" className="border-[var(--cor-borda)]">{a.status}</Badge><span className="text-sm text-[var(--cor-texto)]">{a.user_email}</span></div><p className="text-xs text-[var(--cor-texto-suave)]">{a.plan.nome} - R$ {a.preco_cobrado} - {formatarDataCurta(a.criado_em)}</p></div>))}</div>
  </CardContent></Card></div>);
}