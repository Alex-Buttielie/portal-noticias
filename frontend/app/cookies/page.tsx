import type { Metadata } from "next";
import { Card, CardContent } from "@/components/ui/card";
import { SITE_NAME } from "@/lib/site";
export const metadata: Metadata = { title: `Cookies — ${SITE_NAME}`, description: `Política de cookies do ${SITE_NAME}.` };
export default function Page() {
  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <div className="rounded-[var(--raio-lg)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] p-6"><div className="hud-line mb-4" aria-hidden /><h1 className="text-2xl font-bold text-[var(--cor-texto)]">Cookies</h1><p className="text-sm text-[var(--cor-texto-suave)]">Você controla tudo pelo banner. Se estiver logado, suas preferências ficam salvas na sua conta.</p></div>
      <Card className="bento border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]"><CardContent className="prose max-w-none p-5 prose-p:text-[var(--cor-texto-suave)] prose-headings:text-[var(--cor-texto)]"><h2>Essenciais</h2><p>Sessão e segurança — sempre ativos.</p><h2>Analytics</h2><p>Medição de audiência — só com seu consentimento.</p><h2>Personalização</h2><p>Feed “para você” — só com consentimento.</p></CardContent></Card>
    </div>
  );
}
