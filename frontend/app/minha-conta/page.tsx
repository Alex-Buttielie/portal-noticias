"use client";
import { useAuth } from "@/lib/auth-context";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import Link from "next/link";
export default function Page(){
  const { usuario, token, carregando, fazerLogout } = useAuth();
  const r = useRouter();
  const [out,setOut]=useState(false);
  useEffect(()=>{ if(!carregando && !token) r.replace("/login"); },[carregando,token,r]);
  if(carregando) return <div className="mx-auto max-w-xl py-10"><div className="h-32 animate-pulse rounded-[var(--raio-lg)] bg-[var(--cor-skeleton-base)]" /></div>;
  if(!usuario) return null;
  return (<div className="mx-auto max-w-2xl space-y-4 py-6"><div className="hud-line" aria-hidden />
    <Card className="bento border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]"><CardHeader><CardTitle>Minha conta</CardTitle><CardDescription className="text-[var(--cor-texto-suave)]">Bento HUD - vidro - paper / ink</CardDescription></CardHeader><CardContent className="space-y-3">
      <div className="grid gap-3 md:grid-cols-2">
        <div className="rounded-[var(--raio-md)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-3"><p className="text-xs tracking-widest text-[var(--cor-texto-suave)]">USUARIO</p><p className="font-medium text-[var(--cor-texto)]">{usuario.nome || usuario.email}</p><p className="text-sm text-[var(--cor-texto-suave)]">{usuario.email}</p><Badge className="mt-2 bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]">{usuario.papel}</Badge></div>
        <div className="rounded-[var(--raio-md)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-3"><p className="text-xs tracking-widest text-[var(--cor-texto-suave)]">STATUS</p><p className="text-sm text-[var(--cor-texto)]">Email {usuario.email_verificado?"verificado":"nao verificado"}</p><p className="text-xs text-[var(--cor-texto-suave)]">Onboarding {usuario.onboarding_concluido?"concluido":"pendente"}</p></div>
      </div>
      <div className="flex flex-wrap gap-2"><Button asChild variant="outline" className="min-h-[44px]"><Link href="/onboarding">Onboarding</Link></Button><Button asChild variant="outline" className="min-h-[44px]"><Link href="/personalizar">Personalizar</Link></Button><Button asChild variant="outline" className="min-h-[44px]"><Link href="/favoritos">Favoritos</Link></Button></div>
      <Button variant="destructive" disabled={out} onClick={async()=>{ setOut(true); await fazerLogout(); r.push("/"); }} className="min-h-[44px]">{out?"Saindo...":"Sair"}</Button>
    </CardContent></Card></div>);
}
