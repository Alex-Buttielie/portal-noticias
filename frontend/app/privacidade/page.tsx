import type { Metadata } from "next";
import { Card, CardContent } from "@/components/ui/card";
import { SITE_NAME } from "@/lib/site";
export const metadata: Metadata = { title: `Privacidade — ${SITE_NAME}`, description: `Política de privacidade do ${SITE_NAME} — LGPD.`, alternates: { canonical: "/privacidade" } };
export default function Page() {
  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <div className="rounded-[var(--raio-lg)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] p-6"><div className="hud-line mb-4" aria-hidden /><h1 className="text-2xl font-bold text-[var(--cor-texto)]">Privacidade</h1><p className="text-sm text-[var(--cor-texto-suave)]">LGPD • Banner de consentimento preservado.</p></div>
      <Card className="bento border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]"><CardContent className="prose max-w-none p-5 prose-p:text-[var(--cor-texto-suave)] prose-headings:text-[var(--cor-texto)]"><h2>Dados que coletamos</h2><p>Apenas o necessário para operar o portal. Cookies analíticos só com consentimento.</p><h2>Publicidade</h2><p>Usamos o Google AdSense para exibir anúncios. O Google e seus parceiros podem usar cookies para exibir anúncios com base em visitas anteriores suas a este e a outros sites — só com seu consentimento (categoria “Personalização” do banner de cookies). Você pode desativar a publicidade personalizada nas <a href="https://adssettings.google.com" target="_blank" rel="noopener noreferrer">configurações de anúncios do Google</a>. Assinantes Premium nunca veem anúncio.</p><h2>Seus direitos</h2><p>Acesso, correção e exclusão via Contato. Você pode mudar seu consentimento a qualquer momento.</p><h2>Retenção</h2><p>Dados mantidos enquanto a conta existir ou por obrigação legal.</p></CardContent></Card>
    </div>
  );
}
