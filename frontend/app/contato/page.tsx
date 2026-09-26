import type { Metadata } from "next";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { SITE_NAME } from "@/lib/site";
import ContatoForm from "./ContatoForm";
export const metadata: Metadata = { title: `Contato — ${SITE_NAME}`, description: `Fale com o ${SITE_NAME}.` };
export default function Page() {
  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <div className="rounded-[var(--raio-lg)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] p-5"><div className="hud-line mb-3" aria-hidden /><h1 className="text-2xl font-bold text-[var(--cor-texto)]">Contato</h1><p className="text-sm text-[var(--cor-texto-suave)]">Resposta em até 2 dias úteis.</p></div>
      <Card className="bento border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
        <CardHeader><CardTitle className="text-[var(--cor-texto)]">Enviar mensagem</CardTitle></CardHeader>
        <CardContent>
          <ContatoForm />
        </CardContent>
      </Card>
    </div>
  );
}
