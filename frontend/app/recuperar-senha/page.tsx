"use client";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import * as api from "@/lib/api";
export default function Page(){
  const [ok,setOk]=useState(false); const [err,setErr]=useState<string|null>(null);
  const {register,handleSubmit,formState:{errors,isSubmitting}} = useForm<{email:string}>({defaultValues:{email:""}});
  const onSubmit=async(d:{email:string})=>{ setErr(null); try{ await api.recuperarSenha(d.email); setOk(true);}catch(e:any){ setErr(e?.message||"Falha ao solicitar."); } };
  return (<div className="mx-auto max-w-md space-y-4 py-6"><div className="hud-line" aria-hidden /><Card className="bento border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]"><CardHeader><CardTitle>Recuperar senha</CardTitle><CardDescription className="text-[var(--cor-texto-suave)]">Enviaremos um link para seu email</CardDescription></CardHeader><CardContent>
    {ok ? <p className="rounded-md border border-[var(--cor-sucesso)] bg-[var(--cor-sucesso-suave)] px-3 py-2 text-sm text-[var(--cor-sucesso)]">Se o email existir, enviamos instrucoes.</p> :
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-3" noValidate><div className="space-y-2"><Label htmlFor="email">Email</Label><Input id="email" type="email" autoComplete="email" placeholder="voce@exemplo.com" {...register("email",{required:"Informe o email"})} />{errors.email&&<p className="text-xs text-[var(--cor-erro)]">{errors.email.message as string}</p>}</div>{err&&<p role="alert" className="rounded-md border border-[var(--cor-erro)] bg-[var(--cor-erro-suave)] px-3 py-2 text-sm text-[var(--cor-erro)]">{err}</p>}<Button type="submit" disabled={isSubmitting} className="w-full bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)] min-h-[44px]">{isSubmitting?"Enviando...":"Enviar link"}</Button></form>}
  </CardContent></Card></div>);
}
