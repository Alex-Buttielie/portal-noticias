"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useAuth } from "@/lib/auth-context";
import * as api from "@/lib/api";
export default function Page(){
  const { token } = useAuth(); const r=useRouter();
  const [cidade,setCidade]=useState(""); const [uf,setUf]=useState(""); const [mini,setMini]=useState(""); const [dados,setDados]=useState(""); const [tel,setTel]=useState(""); const [arquivo,setArquivo]=useState<File|null>(null); const [err,setErr]=useState<string|null>(null); const [ok,setOk]=useState(false); const [loading,setLoading]=useState(false);
  const enviar=async(e:React.FormEvent)=>{ e.preventDefault(); setErr(null); if(!token){ setErr("Entre para solicitar credenciamento."); return; } if(!arquivo){ setErr("Anexe o documento."); return; } setLoading(true); try{ await api.solicitarCredenciamento(token,{cidade,uf,mini_bio:mini,dados_profissionais:dados,documento:arquivo,telefone:tel||undefined}); setOk(true); setTimeout(()=>r.push("/jornalista/status"),800);}catch(e:any){ setErr(e?.message||"Falha ao enviar."); } finally{ setLoading(false); } };
  if(!token) return (<div className="mx-auto max-w-xl py-8"><Card className="bento border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]"><CardContent className="p-6 text-center"><p className="text-sm text-[var(--cor-texto-suave)]">Entre para solicitar credenciamento.</p><Button onClick={()=>r.push("/login")} className="mt-3 bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]">Entrar</Button></CardContent></Card></div>);
  return (<div className="mx-auto max-w-2xl space-y-4 py-6"><div className="hud-line" aria-hidden /><Card className="bento border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]"><CardHeader><CardTitle>Solicitar credenciamento</CardTitle><CardDescription className="text-[var(--cor-texto-suave)]">Jornalista - HUD bento - vidro</CardDescription></CardHeader><CardContent><form onSubmit={enviar} className="space-y-3">
    <div className="grid gap-3 md:grid-cols-2"><div className="space-y-2"><Label htmlFor="cidade">Cidade</Label><Input id="cidade" value={cidade} onChange={e=>setCidade(e.target.value)} placeholder="Ex: Sao Paulo" required /></div><div className="space-y-2"><Label htmlFor="uf">UF</Label><Input id="uf" value={uf} onChange={e=>setUf(e.target.value)} placeholder="SP" maxLength={2} required /></div></div>
    <div className="space-y-2"><Label htmlFor="tel">Telefone</Label><Input id="tel" value={tel} onChange={e=>setTel(e.target.value)} placeholder="(11) 99999-9999" autoComplete="tel" /></div>
    <div className="space-y-2"><Label htmlFor="mini">Mini bio</Label><Textarea id="mini" value={mini} onChange={e=>setMini(e.target.value)} rows={3} placeholder="Sua trajetoria..." required /></div>
    <div className="space-y-2"><Label htmlFor="dados">Dados profissionais</Label><Textarea id="dados" value={dados} onChange={e=>setDados(e.target.value)} rows={3} placeholder="Veiculos, registro..." required /></div>
    <div className="space-y-2"><Label htmlFor="doc">Documento (PDF/imagem)</Label><Input id="doc" type="file" accept=".pdf,image/*" onChange={e=>setArquivo(e.target.files?.[0]||null)} required /></div>
    {err&&<p role="alert" className="rounded-md border border-[var(--cor-erro)] bg-[var(--cor-erro-suave)] px-3 py-2 text-sm text-[var(--cor-erro)]">{err}</p>}
    {ok&&<p className="rounded-md border border-[var(--cor-sucesso)] bg-[var(--cor-sucesso-suave)] px-3 py-2 text-sm text-[var(--cor-sucesso)]">Solicitacao enviada - redirecionando...</p>}
    <Button type="submit" disabled={loading} className="w-full bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)] min-h-[44px]">{loading?"Enviando...":"Enviar solicitacao"}</Button>
  </form></CardContent></Card></div>);
}
