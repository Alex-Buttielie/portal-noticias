"use client";
import { useRouter } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth-context";
import { formatarDataCurta } from "@/lib/datas";
import { useQueryPerfilJornalista, useQuerySolicitacaoJornalista } from "@/lib/queries";
export default function Page(){
  const { token, usuario } = useAuth(); const r=useRouter();
  const usuarioId = usuario?.id ?? 0;
  const solicQuery = useQuerySolicitacaoJornalista({ token, usuarioId });
  const perfilQuery = useQueryPerfilJornalista({ token, usuarioId });
  if(!token) return (<div className="mx-auto max-w-xl py-8"><Card className="bento border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]"><CardContent className="p-6 text-center"><p className="text-sm text-[var(--cor-texto-suave)]">Entre para ver status.</p><Button onClick={()=>r.push("/login")} className="mt-3 bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]">Entrar</Button></CardContent></Card></div>);
  if(solicQuery.isLoading || perfilQuery.isLoading) return <div className="mx-auto max-w-xl py-8"><div className="h-24 animate-pulse rounded-[var(--raio-lg)] bg-[var(--cor-skeleton-base)]" /></div>;
  // 404 é convertido em null pela api: dado null é estado normal, não erro.
  // Erro de rede propaga para isError/error e aparece no parágrafo de falha.
  const erroQuery = solicQuery.isError ? solicQuery.error : perfilQuery.isError ? perfilQuery.error : null;
  const mensagemErro = erroQuery ? (erroQuery.message || "Falha ao carregar.") : null;
  return (<div className="mx-auto max-w-2xl space-y-4 py-6"><div className="hud-line" aria-hidden />
    <Card className="bento border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]"><CardHeader><CardTitle>Status do credenciamento</CardTitle><CardDescription className="text-[var(--cor-texto-suave)]">Acompanhe sua solicitação</CardDescription></CardHeader><CardContent className="space-y-4">
      {mensagemErro&&<p className="rounded-md border border-[var(--cor-erro)] bg-[var(--cor-erro-suave)] px-3 py-2 text-sm text-[var(--cor-erro)]">{mensagemErro}</p>}
      {solicQuery.isError ? null : (solicQuery.data ? (<div className="rounded-[var(--raio-md)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-3"><p className="text-sm text-[var(--cor-texto)]">Solicitacao #{solicQuery.data.id} - <Badge className="bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]">{solicQuery.data.status}</Badge></p><p className="text-xs text-[var(--cor-texto-suave)]">{solicQuery.data.cidade}/{solicQuery.data.uf} - {formatarDataCurta(solicQuery.data.criado_em)}</p>{solicQuery.data.motivo_decisao&&<p className="mt-2 text-sm text-[var(--cor-texto-suave)]">{solicQuery.data.motivo_decisao}</p>}</div>) : <p className="text-sm text-[var(--cor-texto-suave)]">Nenhuma solicitacao encontrada - <a href="/jornalista/solicitar" className="text-[var(--cor-primaria)] underline">solicitar</a>.</p>)}
      {perfilQuery.data&&<div className="rounded-[var(--raio-md)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-3"><p className="text-sm font-medium text-[var(--cor-texto)]">Perfil jornalistico</p><p className="text-sm text-[var(--cor-texto-suave)]">{perfilQuery.data.mini_bio}</p><div className="mt-2 flex gap-2"><Badge variant="outline" className="border-[var(--cor-borda)]">{perfilQuery.data.selo_ativo?"selo ativo":"sem selo"}</Badge>{perfilQuery.data.suspenso&&<Badge className="bg-[var(--cor-erro)] text-[var(--cor-texto-invertido)]">suspenso</Badge>}</div></div>}
    </CardContent></Card></div>);
}
