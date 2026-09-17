import type { Metadata } from "next";
import { Card, CardContent } from "@/components/ui/card";
import { SITE_NAME } from "@/lib/site";
export const metadata: Metadata = { title: `Politica de privacidade - ${SITE_NAME}` };
export default function Page(){ return (<div className="mx-auto max-w-3xl space-y-4 py-6"><div className="hud-line" aria-hidden /><Card className="bento border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]"><CardContent className="prose max-w-none p-6 prose-p:text-[var(--cor-texto-suave)] prose-headings:text-[var(--cor-texto)]"><h1>Politica de privacidade</h1><p>LGPD - dados coletados apenas para operar o portal. Consentimento gerenciado via BannerConsentimentoCookies e lib/cookie-consent.ts.</p><h2>Direitos</h2><p>Acesso, correcao e exclusao via /contato.</p></CardContent></Card></div>); }
