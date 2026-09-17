"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useAuth } from "@/lib/auth-context";
import * as api from "@/lib/api";
export default function Page(){
  const { token } = useAuth(); const r=useRouter();
  const [err,setErr]=useState<string|null>(null);
  const [tipo,setTipo]=useState<api.TipoPublicacao>("opiniao");
  const {register,handleSubmit,formState:{errors,isSubmitting}} = useForm<{titulo:string;conteudo:string;categoria:string}>({defaultValues:{titulo:"",conteudo:"",categoria:""}});
  const onSubmit=async(d:any)=>{ setErr(null); if(!token){ setErr("Entre para publicar."); return; } try{ const pub=await api.criarRascunhoPublicacao(token,{titulo:d.titulo,conteudo:d.conteudo,tipo,categoria:d.categoria}); await api.enviarPublicacao(token,pub.id); r.push(`/comunidade/${pub.id}`);}catch(e:any){ setErr(e?.message||"Falha ao publicar."); } };
  if(!token) return (<div className="mx-auto max-w-xl py-8"><Card className="bento border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]"><CardContent className="p-6 text-center"><p className="text-sm text-[var(--cor-texto-suave)]">Entre para publicar.</p><Button onClick={()=>r.push("/login")} className="mt-3 bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]">Entrar</Button></CardContent></Card></div>);
  return (<div className="mx-auto max-w-2xl space-y-4 py-6"><div className="hud-line" aria-hidden /><Card className="bento border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]"><CardHeader><CardTitle>Nova publicacao</CardTitle><CardDescription className="text-[var(--cor-texto-suave)]">Bento HUD - vidro</CardDescription></CardHeader><CardContent><form onSubmit={handleSubmit(onSubmit)} className="space-y-3" noValidate>
    <div className="space-y-2"><Label htmlFor="titulo">Titulo</Label><Input id="titulo" placeholder="Titulo..." {...register("titulo",{required:"Informe o titulo"})} />{errors.titulo&&<p className="text-xs text-[var(--cor-erro)]">{errors.titulo.message as string}</p>}</div>
    <div className="space-y-2"><Label>Tipo</Label><Select value={tipo} onValueChange={(v)=>setTipo(v as any)}><SelectTrigger className="bg-[var(--cor-fundo-card)]"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="opiniao">Opiniao</SelectItem><SelectItem value="analise">Analise</SelectItem></SelectContent></Select></div>
    <div className="space-y-2"><Label htmlFor="categoria">Categoria</Label><Input id="categoria" placeholder="Ex: politica" {...register("categoria")} /></div>
    <div className="space-y-2"><Label htmlFor="conteudo">Conteudo</Label><Textarea id="conteudo" rows={8} placeholder="Escreva aqui..." {...register("conteudo",{required:"Informe o conteudo"})} />{errors.conteudo&&<p className="text-xs text-[var(--cor-erro)]">{errors.conteudo.message as string}</p>}</div>
    {err&&<p role="alert" className="rounded-md border border-[var(--cor-erro)] bg-[var(--cor-erro-suave)] px-3 py-2 text-sm text-[var(--cor-erro)]">{err}</p>}
    <Button type="submit" disabled={isSubmitting} className="w-full bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)] min-h-[44px]">{isSubmitting?"Enviando...":"Publicar"}</Button>
  </form></CardContent></Card></div>);
}
