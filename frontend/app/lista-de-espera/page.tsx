import type { Metadata } from "next";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { SITE_NAME } from "@/lib/site";
export const metadata: Metadata = { title: `Lista de espera - ${SITE_NAME}` };
export default function Page(){
  return (<div className="mx-auto max-w-xl space-y-4 py-6"><div className="hud-line" aria-hidden /><Card className="bento border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]"><CardHeader><CardTitle>Lista de espera</CardTitle></CardHeader><CardContent><form className="space-y-3"><div className="space-y-2"><Label htmlFor="nome">Nome</Label><Input id="nome" placeholder="Seu nome..." /></div><div className="space-y-2"><Label htmlFor="email">Email</Label><Input id="email" type="email" placeholder="voce@exemplo.com" /></div><Button type="submit" className="min-h-[44px] bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]">Entrar na lista</Button><p className="text-xs text-[var(--cor-texto-suave)]">Deixe seu e-mail e avisaremos quando liberar.</p></form></CardContent></Card></div>);
}
