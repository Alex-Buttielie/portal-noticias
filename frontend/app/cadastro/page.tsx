"use client";
import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { MailCheck } from "lucide-react";
import * as api from "@/lib/api";
import BuscaCep from "@/components/BuscaCep";
export default function Page(){
  const r=useRouter(); const [erro,setErro]=useState<string|null>(null); const [ok,setOk]=useState(false);
  const [cepLoc,setCepLoc]=useState<string|null>(null);
  const {register,handleSubmit,formState:{errors,isSubmitting}}=useForm<{email:string;senha:string;nome:string;aceite_termos:boolean}>({defaultValues:{email:"",senha:"",nome:"",aceite_termos:false}});
  const onSubmit=async(d:any)=>{ setErro(null); if(!d.aceite_termos){setErro("Aceite os termos para continuar.");return;} try{ const payload:any={email:d.email,senha:d.senha,nome:d.nome,aceite_termos:true}; if(cepLoc) payload.localidade=cepLoc; await api.cadastrar(payload); if(cepLoc) try{localStorage.setItem("brd.localidade.pendente",cepLoc);}catch{} setOk(true);}catch(e:any){setErro(e?.message||"Falha no cadastro.");}};
  if(ok) return (<div className="mx-auto max-w-md py-10"><Dialog open={ok} onOpenChange={(o)=>{ if(!o) r.push("/login"); }}><DialogContent className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]"><DialogHeader className="items-center text-center sm:items-center sm:text-center"><div className="flex h-12 w-12 items-center justify-center rounded-full bg-[var(--cor-primaria-suave)] text-[var(--cor-primaria)]"><MailCheck className="h-6 w-6" /></div><DialogTitle className="text-center">Bem-vindo!</DialogTitle><DialogDescription className="text-center">Cadastro realizado com sucesso. Verifique seu email para ativar sua conta e continuar.</DialogDescription></DialogHeader><div className="rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-3 text-sm text-[var(--cor-texto-suave)]">Dica: confira a caixa de spam se não encontrar o email em alguns minutos.</div><DialogFooter className="sm:justify-center"><Button onClick={()=>r.push("/login")} className="w-full bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)] min-h-[44px]">Ir para login</Button></DialogFooter><p className="text-center text-xs text-[var(--cor-texto-suave)]"><Link href="/" className="underline hover:text-[var(--cor-texto)]">Voltar ao início</Link></p></DialogContent></Dialog><Card className="bento border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]"><CardContent className="p-6 text-center"><p className="text-sm text-[var(--cor-texto)]">Cadastro realizado — verifique seu email.</p><Link href="/login" className="text-sm text-[var(--cor-primaria)] hover:underline">Ir para login</Link></CardContent></Card></div>);
  return (<div className="mx-auto max-w-md space-y-4 py-6"><div className="hud-line" aria-hidden /><Card className="bento border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]"><CardHeader><CardTitle>Criar conta</CardTitle><CardDescription className="text-[var(--cor-texto-suave)]">Bento HUD • vidro • neon contido</CardDescription></CardHeader><CardContent><form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
    <div className="space-y-2"><Label htmlFor="nome">Nome</Label><Input id="nome" autoComplete="name" placeholder="Seu nome" {...register("nome")} /></div>
    <div className="space-y-2"><Label htmlFor="email">Email</Label><Input id="email" type="email" autoComplete="email" placeholder="voce@exemplo.com" {...register("email",{required:"Informe o email"})} />{errors.email&&<p className="text-xs text-[var(--cor-erro)]">{errors.email.message as string}</p>}</div>
    <div className="space-y-2"><Label htmlFor="senha">Senha</Label><Input id="senha" type="password" autoComplete="new-password" placeholder="••••••••" {...register("senha",{required:"Informe a senha",minLength:{value:6,message:"Mínimo 6"}})} />{errors.senha&&<p className="text-xs text-[var(--cor-erro)]">{errors.senha.message as string}</p>}</div>
    <label className="flex items-center gap-2 text-sm"><input type="checkbox" {...register("aceite_termos")} className="h-4 w-4 rounded border-[var(--cor-borda)]" /> Aceito <Link href="/termos" className="text-[var(--cor-primaria)] underline">termos</Link></label>
    {erro&&<p role="alert" className="rounded-md border border-[var(--cor-erro)] bg-[var(--cor-erro-suave)] px-3 py-2 text-sm text-[var(--cor-erro)]">{erro}</p>}
    <Button type="submit" disabled={isSubmitting} className="w-full bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)] min-h-[44px]">{isSubmitting?"Enviando…":"Cadastrar"}</Button>
    <p className="text-center text-xs text-[var(--cor-texto-suave)]">Já tem conta? <Link href="/login" className="text-[var(--cor-primaria)] hover:underline">Entrar</Link></p></form>
      <div className="mt-4 border-t border-[var(--cor-borda)] pt-4">
        <p className="mb-2 text-sm font-medium text-[var(--cor-texto)]">CEP para personalizar feed local <span className="font-normal text-[var(--cor-texto-suave)]">(opcional)</span></p>
        <BuscaCep compact onEndereco={(e)=> setCepLoc(`${e.localidade}, ${e.uf}`)} />
        {cepLoc && <p className="mt-2 text-xs text-[var(--cor-sucesso)]">Localidade selecionada: {cepLoc} — será usada no seu perfil.</p>}
        <p className="mt-1 text-xs text-[var(--cor-texto-suave)]">Você poderá ajustar em Onboarding depois.</p>
      </div>
      </CardContent></Card></div>);
}
