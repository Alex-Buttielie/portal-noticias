import type { Metadata } from "next";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { SITE_NAME } from "@/lib/site";
export const metadata: Metadata = { title: `Newsletter — ${SITE_NAME}`, description: `Assine a newsletter do ${SITE_NAME}.` };
const CATS = ["geral", "política", "economia", "tecnologia", "esportes", "cultura", "saúde", "mundo", "cidades"];
export default function Page() {
  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <div className="rounded-[var(--raio-lg)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] p-5"><div className="hud-line mb-3" aria-hidden /><h1 className="text-2xl font-bold text-[var(--cor-texto)]">Newsletter</h1><p className="text-sm text-[var(--cor-texto-suave)]">Resumo diário sem ruído — escolha editorias e receba no seu horário.</p></div>
      <Card className="bento border-[var(--cor-neon-ciano)] bg-[var(--cor-fundo-elevado)]">
        <CardHeader><CardTitle className="text-[var(--cor-texto)]">Assinar</CardTitle></CardHeader>
        <CardContent>
          <form className="space-y-3">
            <div className="grid gap-1.5"><Label htmlFor="nl-email">Email</Label><Input id="nl-email" type="email" placeholder="seu@email.com" autoComplete="email" required className="bg-[var(--cor-fundo-card)]" /></div>
            <div className="space-y-1.5"><Label>Editorias</Label><div className="flex flex-wrap gap-1.5">{CATS.map((c)=>(<Badge key={c} variant="outline" className="cursor-pointer border-[var(--cor-borda)] capitalize hover:bg-[var(--cor-primaria-suave)]">{c}</Badge>))}</div><p className="text-xs text-[var(--cor-texto-suave)]">Placeholder — seleção visual; integração via lib/api.ts assinarNewsletterPublica quando API online.</p></div>
            <Button type="submit" className="min-h-[44px] bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)] hover:bg-[var(--cor-primaria-hover)]">Quero receber</Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
