import type { Metadata } from "next";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { SITE_NAME } from "@/lib/site";
import ContatoCepIsland from "./ContatoCepIsland";
export const metadata: Metadata = { title: `Contato — ${SITE_NAME}`, description: `Fale com o ${SITE_NAME}.` };
export default function Page() {
  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <div className="rounded-[var(--raio-lg)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] p-5"><div className="hud-line mb-3" aria-hidden /><h1 className="text-2xl font-bold text-[var(--cor-texto)]">Contato</h1><p className="text-sm text-[var(--cor-texto-suave)]">Resposta em até 2 dias úteis.</p></div>
      <Card className="bento border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
        <CardHeader><CardTitle className="text-[var(--cor-texto)]">Enviar mensagem</CardTitle></CardHeader>
        <CardContent>
          <form className="space-y-3">
            <div className="grid gap-1.5"><Label htmlFor="nome">Nome</Label><Input id="nome" placeholder="Seu nome…" autoComplete="name" className="bg-[var(--cor-fundo-card)]" /></div>
            <div className="grid gap-1.5"><Label htmlFor="email">Email</Label><Input id="email" type="email" placeholder="seu@email.com" autoComplete="email" className="bg-[var(--cor-fundo-card)]" /></div>
            <div className="grid gap-1.5"><Label htmlFor="msg">Mensagem</Label><Textarea id="msg" placeholder="Como podemos ajudar?…" rows={5} className="bg-[var(--cor-fundo-card)]" /></div>
            <ContatoCepIsland />
            <Button type="submit" className="min-h-[44px] bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)] hover:bg-[var(--cor-primaria-hover)]">Enviar</Button>
            <p className="text-xs text-[var(--cor-texto-suave)]">Responderemos em até 2 dias úteis.</p>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
