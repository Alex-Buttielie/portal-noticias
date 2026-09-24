import type { Metadata } from "next";
import { Card, CardContent } from "@/components/ui/card";
import { SITE_NAME } from "@/lib/site";
import { formatarDataCurta } from "@/lib/datas";
export const metadata: Metadata = { title: `Termos de uso — ${SITE_NAME}`, description: `Termos de uso do ${SITE_NAME}.` };
export default function Page() {
  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <div className="rounded-[var(--raio-lg)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] p-6"><div className="hud-line mb-4" aria-hidden /><h1 className="text-2xl font-bold text-[var(--cor-texto)]">Termos de uso</h1><p className="text-sm text-[var(--cor-texto-suave)]">Última atualização: {formatarDataCurta(new Date())}</p></div>
      <Card className="bento border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]"><CardContent className="prose max-w-none p-5 prose-p:text-[var(--cor-texto-suave)] prose-headings:text-[var(--cor-texto)]"><h2>1. Aceite</h2><p>Ao acessar o {SITE_NAME} você concorda com estes termos. Conteúdo agregado com citação de fontes originais.</p><h2>2. Uso</h2><p>Não reproduza conteúdo sem citar a fonte original. Uso indevido pode levar a bloqueio.</p><h2>3. Contato</h2><p>Dúvidas? Fale em /contato.</p></CardContent></Card>
    </div>
  );
}
