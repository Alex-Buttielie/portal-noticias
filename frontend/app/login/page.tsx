"use client";
import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/lib/auth-context";
export default function Page(){
  const {fazerLogin}=useAuth(); const r=useRouter(); const [erro,setErro]=useState<string|null>(null);
  const {register,handleSubmit,formState:{errors,isSubmitting}}=useForm<{email:string;senha:string}>({defaultValues:{email:"",senha:""}});
  const onSubmit=async(d:{email:string;senha:string})=>{ setErro(null); try{ await fazerLogin(d.email,d.senha); r.push("/minha-conta"); }catch(e:any){ setErro(e?.message||"Falha no login."); } };
  return (<div className="mx-auto max-w-md space-y-4 py-6"><div className="hud-line" aria-hidden />
    <Card className="bento border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]"><CardHeader><CardTitle className="text-[var(--cor-texto)]">Entrar</CardTitle><CardDescription className="text-[var(--cor-texto-suave)]">Acesse sua conta — bento/HUD • vidro</CardDescription></CardHeader><CardContent>
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
        <div className="space-y-2"><Label htmlFor="email">Email</Label><Input id="email" type="email" autoComplete="email" placeholder="voce@exemplo.com" {...register("email",{required:"Informe o email"})} aria-invalid={!!errors.email} />{errors.email&&<p className="text-xs font-medium text-[var(--cor-erro)]">{errors.email.message as string}</p>}</div>
        <div className="space-y-2"><Label htmlFor="senha">Senha</Label><Input id="senha" type="password" autoComplete="current-password" placeholder="••••••••" {...register("senha",{required:"Informe a senha",minLength:{value:6,message:"Mínimo 6 caracteres"}})} aria-invalid={!!errors.senha} />{errors.senha&&<p className="text-xs font-medium text-[var(--cor-erro)]">{errors.senha.message as string}</p>}</div>
        {erro&&<p role="alert" className="rounded-md border border-[var(--cor-erro)] bg-[var(--cor-erro-suave)] px-3 py-2 text-sm text-[var(--cor-erro)]">{erro}</p>}
        <Button type="submit" disabled={isSubmitting} className="w-full bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)] hover:bg-[var(--cor-primaria-hover)] min-h-[44px]">{isSubmitting?"Entrando…":"Entrar"}</Button>
        <div className="flex justify-between text-xs"><Link href="/recuperar-senha" className="text-[var(--cor-primaria)] hover:underline">Esqueci a senha</Link><Link href="/cadastro" className="text-[var(--cor-primaria)] hover:underline">Criar conta</Link></div>
      </form></CardContent></Card>
    <Card className="bento border-[var(--cor-neon-ciano)] bg-[var(--cor-fundo-elevado)]"><CardContent className="p-3 text-xs text-[var(--cor-texto-suave)]">HUD • paper <span className="text-[var(--cor-texto)]">#FDFBF7</span> / ink #0B0B1A / signal <span className="text-[var(--cor-sinal)]">#FF2E2E</span></CardContent></Card></div>);
}
