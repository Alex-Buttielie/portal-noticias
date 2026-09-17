"use client";
import { Suspense, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import * as api from "@/lib/api";
function RedefinirForm(){
  const sp=useSearchParams(); const r=useRouter();
  const uid=sp.get("uid")||""; const tok=sp.get("token")||"";
  const [err,setErr]=useState<string|null>(null); const [ok,setOk]=useState(false);
  const {register,handleSubmit,formState:{errors,isSubmitting}}=useForm<{nova_senha:string}>({defaultValues:{nova_senha:""}});
  const onSubmit=async(d:{nova_senha:string})=>{ setErr(null); try{ await api.redefinirSenha(uid,tok,d.nova_senha); setOk(true); setTimeout(()=>r.push("/login"),1000);}catch(e:any){ setErr(e?.message||"Falha ao redefinir."); } };
  return (<Card className="bento border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]"><CardHeader><CardTitle>Redefinir senha</CardTitle><CardDescription className="text-[var(--cor-texto-suave)]">Defina sua nova senha</CardDescription></CardHeader><CardContent>
    {ok? <p className="rounded-md border border-[var(--cor-sucesso)] bg-[var(--cor-sucesso-suave)] px-3 py-2 text-sm text-[var(--cor-sucesso)]">Senha redefinida - redirecionando...</p> :
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-3" noValidate><div className="space-y-2"><Label htmlFor="senha">Nova senha</Label><Input id="senha" type="password" autoComplete="new-password" placeholder="••••••••" {...register("nova_senha",{required:"Informe a senha",minLength:{value:6,message:"Minimo 6"}})} />{errors.nova_senha&&<p className="text-xs text-[var(--cor-erro)]">{errors.nova_senha.message as string}</p>}</div>{err&&<p role="alert" className="rounded-md border border-[var(--cor-erro)] bg-[var(--cor-erro-suave)] px-3 py-2 text-sm text-[var(--cor-erro)]">{err}</p>}<Button type="submit" disabled={isSubmitting} className="w-full bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)] min-h-[44px]">{isSubmitting?"Salvando...":"Salvar"}</Button></form>}
  </CardContent></Card>);
}
export default function Page(){ return (<div className="mx-auto max-w-md space-y-4 py-6"><div className="hud-line" aria-hidden /><Suspense fallback={<div className="h-32 animate-pulse rounded-[var(--raio-lg)] bg-[var(--cor-skeleton-base)]" />}><RedefinirForm /></Suspense></div>); }
