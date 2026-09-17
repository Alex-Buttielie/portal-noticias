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
import { Sparkles, ShieldCheck } from "lucide-react";
import { useAuth } from "@/lib/auth-context";
export default function Page(){
  const {fazerLogin}=useAuth(); const r=useRouter(); const [erro,setErro]=useState<string|null>(null);
  const [dlgOnboarding,setDlgOnboarding]=useState(false);
  const [dlgAdmin,setDlgAdmin]=useState(false);
  const {register,handleSubmit,formState:{errors,isSubmitting}}=useForm<{email:string;senha:string}>({defaultValues:{email:"",senha:""}});
  const onSubmit=async(d:{email:string;senha:string})=>{ setErro(null); try{ await fazerLogin(d.email,d.senha); let u:any=null; try{ const raw=typeof window!=="undefined"? window.localStorage.getItem("portal_noticias_usuario"):null; if(raw) u=JSON.parse(raw);}catch{} if(u && !u.onboarding_concluido){ setDlgOnboarding(true); return; } if(u?.papel==="admin"){ setDlgAdmin(true); return; } r.push("/minha-conta"); }catch(e:any){ setErro(e?.message||"Falha no login."); } };
  return (<div className="mx-auto max-w-md space-y-4 py-6"><div className="hud-line" aria-hidden />
    <Dialog open={dlgOnboarding} onOpenChange={setDlgOnboarding}><DialogContent className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]"><DialogHeader className="items-center text-center sm:items-center sm:text-center"><div className="flex h-12 w-12 items-center justify-center rounded-full bg-[var(--cor-primaria-suave)] text-[var(--cor-primaria)]"><Sparkles className="h-6 w-6" /></div><DialogTitle className="text-center">Complete seu perfil</DialogTitle><DialogDescription className="text-center">Falta pouco para personalizar seu feed. Leva menos de 1 minuto.</DialogDescription></DialogHeader><DialogFooter className="flex-col gap-2 sm:flex-col"><Button onClick={()=>{ setDlgOnboarding(false); r.push("/onboarding"); }} className="w-full bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)] min-h-[44px]">Continuar onboarding</Button><Button variant="outline" onClick={()=>{ setDlgOnboarding(false); r.push("/minha-conta"); }} className="w-full min-h-[44px]">Depois</Button></DialogFooter></DialogContent></Dialog>
    <Dialog open={dlgAdmin} onOpenChange={setDlgAdmin}><DialogContent className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]"><DialogHeader className="items-center text-center sm:items-center sm:text-center"><div className="flex h-12 w-12 items-center justify-center rounded-full bg-[var(--cor-fundo-elevado)] text-[var(--cor-texto)] border border-[var(--cor-borda)]"><ShieldCheck className="h-6 w-6" /></div><DialogTitle className="text-center">Acesso à Central</DialogTitle><DialogDescription className="text-center">Você tem perfil administrador. Acesse a Central para moderação e métricas.</DialogDescription></DialogHeader><DialogFooter className="flex-col gap-2 sm:flex-col"><Button onClick={()=>{ setDlgAdmin(false); r.push("/admin"); }} className="w-full bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)] min-h-[44px]">Abrir Central</Button><Button variant="outline" onClick={()=>{ setDlgAdmin(false); r.push("/minha-conta"); }} className="w-full min-h-[44px]">Ir para minha conta</Button></DialogFooter></DialogContent></Dialog>
    <Card className="bento border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]"><CardHeader><CardTitle className="text-[var(--cor-texto)]">Entrar</CardTitle><CardDescription className="text-[var(--cor-texto-suave)]">Acesse sua conta</CardDescription></CardHeader><CardContent>
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
        <div className="space-y-2"><Label htmlFor="email">Email</Label><Input id="email" type="email" autoComplete="email" placeholder="voce@exemplo.com" {...register("email",{required:"Informe o email"})} aria-invalid={!!errors.email} />{errors.email&&<p className="text-xs font-medium text-[var(--cor-erro)]">{errors.email.message as string}</p>}</div>
        <div className="space-y-2"><Label htmlFor="senha">Senha</Label><Input id="senha" type="password" autoComplete="current-password" placeholder="••••••••" {...register("senha",{required:"Informe a senha",minLength:{value:6,message:"Mínimo 6 caracteres"}})} aria-invalid={!!errors.senha} />{errors.senha&&<p className="text-xs font-medium text-[var(--cor-erro)]">{errors.senha.message as string}</p>}</div>
        {erro&&<p role="alert" className="rounded-md border border-[var(--cor-erro)] bg-[var(--cor-erro-suave)] px-3 py-2 text-sm text-[var(--cor-erro)]">{erro}</p>}
        <Button type="submit" disabled={isSubmitting} className="w-full bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)] hover:bg-[var(--cor-primaria-hover)] min-h-[44px]">{isSubmitting?"Entrando…":"Entrar"}</Button>
        <div className="flex justify-between text-xs"><Link href="/recuperar-senha" className="text-[var(--cor-primaria)] hover:underline">Esqueci a senha</Link><Link href="/cadastro" className="text-[var(--cor-primaria)] hover:underline">Criar conta</Link></div>
      </form></CardContent></Card>
    <Card className="bento border-[var(--cor-neon-ciano)] bg-[var(--cor-fundo-elevado)]"><CardContent className="p-3 text-xs text-[var(--cor-texto-suave)]">Leitura confortável • claro e escuro com destaque para o que importa</CardContent></Card></div>);
}
