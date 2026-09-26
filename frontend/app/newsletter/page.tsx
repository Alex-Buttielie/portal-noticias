import type { Metadata } from "next";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { SITE_NAME } from "@/lib/site";
import NewsletterForm, { DescadastrarForm } from "./NewsletterForm";
export const metadata: Metadata = { title: `Newsletter — ${SITE_NAME}`, description: `Assine a newsletter do ${SITE_NAME}.` };
export default function Page() {
  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <div className="rounded-[var(--raio-lg)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] p-5"><div className="hud-line mb-3" aria-hidden /><h1 className="text-2xl font-bold text-[var(--cor-texto)]">Newsletter</h1><p className="text-sm text-[var(--cor-texto-suave)]">Resumo diário sem ruído — escolha editorias e receba no seu horário.</p></div>
      <Card className="bento border-[var(--cor-neon-ciano)] bg-[var(--cor-fundo-elevado)]">
        <CardHeader><CardTitle className="text-[var(--cor-texto)]">Assinar</CardTitle></CardHeader>
        <CardContent>
          <NewsletterForm />
        </CardContent>
      </Card>
      <Card className="bento border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
        <CardHeader><CardTitle className="text-[var(--cor-texto)]">Descadastrar</CardTitle></CardHeader>
        <CardContent>
          <p className="mb-3 text-sm text-[var(--cor-texto-suave)]">Recebeu o e-mail e não quer mais receber? Use o token do link de descadastro.</p>
          <DescadastrarForm />
        </CardContent>
      </Card>
    </div>
  );
}
