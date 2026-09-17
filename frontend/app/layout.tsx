import type { Metadata, Viewport } from "next";
import { Suspense } from "react";
import { headers } from "next/headers";
import { Inter, Source_Serif_4 } from "next/font/google";
import "./globals.css";
import { Providers } from "./providers";
import { Header } from "@/components/Header";
import { Rodape } from "@/components/Rodape";
import { NavegacaoAdaptativa } from "@/components/dispositivos/NavegacaoAdaptativa";
import { BannerConsentimentoCookies } from "@/components/BannerConsentimentoCookies";
import { AnalyticsTracker } from "@/components/AnalyticsTracker";
import { TutorialTour } from "@/components/TutorialTour";
import { PularParaConteudo } from "@/components/PularParaConteudo";
import { SITE_DESCRIPTION, SITE_NAME, SITE_URL } from "@/lib/site";
import { organizationJsonLd } from "@/lib/schema";
import { perfilPorUserAgent } from "@/lib/dispositivos/detectar";

const inter = Inter({ subsets: ["latin"], variable: "--fonte-inter", display: "swap" });
const serif = Source_Serif_4({ subsets: ["latin"], variable: "--fonte-serif", display: "swap" });

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: { default: SITE_NAME, template: `%s — ${SITE_NAME}` },
  description: SITE_DESCRIPTION,
  openGraph: { type: "website", locale: "pt_BR", siteName: SITE_NAME, title: SITE_NAME, description: SITE_DESCRIPTION, url: SITE_URL },
  robots: { index: true, follow: true },
};

export const viewport: Viewport = {
  themeColor: "#FDFBF7",
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
};

const SCRIPT_TEMA_INICIAL = `(function(){try{var t=localStorage.getItem("theme");if(!t)t=window.matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light";document.documentElement.setAttribute("data-theme",t)}catch(e){}})();`;

function JsonLd() {
  const data = organizationJsonLd();
  return <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(data) }} />;
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  // Perfil inicial SSR a partir do User-Agent: evita flash de layout
  // (mobile recebendo layout desktop) antes da hidratação.
  // O provider corrige no cliente com largura/orientação reais.
  let perfilInicial = undefined;
  try {
    perfilInicial = perfilPorUserAgent(headers().get("user-agent"));
  } catch {
    /* headers indisponível em prerender estático */
  }
  return (
    <html lang="pt-BR" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: SCRIPT_TEMA_INICIAL }} />
        <JsonLd />
      </head>
      <body className={`${inter.variable} ${serif.variable} min-h-screen bg-[var(--cor-fundo)] font-sans text-[var(--cor-texto)] antialiased`}>
        <PularParaConteudo />
        <Providers perfilInicial={perfilInicial}>
          <Header />
          <main id="conteudo-principal" className="mx-auto w-full max-w-[1280px] px-4 pb-20 pt-6 md:px-6 md:pb-8">
            {children}
          </main>
          <Rodape />
          <NavegacaoAdaptativa />
          <BannerConsentimentoCookies />
          <Suspense fallback={null}>
            <AnalyticsTracker />
          </Suspense>
          <TutorialTour />
        </Providers>
      </body>
    </html>
  );
}
