import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import Script from "next/script";
import { Inter, Source_Serif_4 } from "next/font/google";
import "./globals.css";
import { Providers } from "./providers";
import Header from "@/components/Header";
import Rodape from "@/components/Rodape";
import BottomNav from "@/components/BottomNav";
import PularParaConteudo from "@/components/PularParaConteudo";
import BannerConsentimentoCookies from "@/components/BannerConsentimentoCookies";
import JsonLd from "@/components/JsonLd";
import { organizationJsonLd } from "@/lib/schema";
import { IMAGEM_OG_PADRAO, SITE_DESCRIPTION, SITE_NAME, SITE_URL } from "@/lib/site";

// Tipografia editorial: serifada nos títulos (identidade de jornalismo,
// como grandes veículos internacionais) + Inter na interface/corpo do
// texto. next/font hospeda os arquivos localmente (build-time) — nenhuma
// requisição a fonts.googleapis.com em runtime, alinhado ao trabalho de
// LGPD/privacidade já em andamento no projeto.
const fonteCorpo = Inter({
  subsets: ["latin"],
  variable: "--fonte-corpo",
  display: "swap",
});

const fonteTitulo = Source_Serif_4({
  subsets: ["latin"],
  variable: "--fonte-titulo",
  display: "swap",
});

// SEO técnico (implementation-contract.md run
// 20260903-1134-seo-lgpd-design-system, escopo A): metadata base herdada por
// toda página que não sobrescreve os próprios campos via `generateMetadata`.
// `metadataBase` é o que permite às páginas filhas declarar `images`/
// `canonical` com caminhos relativos.
export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 5,
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#fdfcf8" },
    { media: "(prefers-color-scheme: dark)", color: "#0f0f0f" },
  ],
  colorScheme: "light dark",
};

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: { default: SITE_NAME, template: `%s — ${SITE_NAME}` },
  description: SITE_DESCRIPTION,
  alternates: {
    canonical: "/",
    types: { "application/rss+xml": [{ url: "/rss.xml", title: `${SITE_NAME} — últimas notícias` }] },
  },
  openGraph: {
    type: "website",
    siteName: SITE_NAME,
    title: SITE_NAME,
    description: SITE_DESCRIPTION,
    url: SITE_URL,
    images: [{ url: IMAGEM_OG_PADRAO, width: 1200, height: 630 }],
  },
  twitter: {
    card: "summary_large_image",
    title: SITE_NAME,
    description: SITE_DESCRIPTION,
    images: [IMAGEM_OG_PADRAO],
  },
};

// Aplica a preferência de tema salva antes da primeira pintura, evitando o
// flash de tema errado (light->dark) na carga da página.
// Mantido idêntico para contrato anti-flash + LGPD + SEO — não remover.
const SCRIPT_TEMA_INICIAL = `
(function () {
  try {
    var tema = window.localStorage.getItem("portal_noticias_tema");
    if (tema === "dark" || tema === "light") {
      document.documentElement.setAttribute("data-theme", tema);
    }
  } catch (erro) {}
})();
`;

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="pt-BR" suppressHydrationWarning className={`${fonteCorpo.variable} ${fonteTitulo.variable} scroll-smooth`}>
      <body className="min-h-screen bg-[var(--cor-fundo)] font-[var(--fonte-corpo)] text-[var(--cor-texto)] antialiased selection:bg-[var(--cor-texto)] selection:text-[var(--cor-fundo)]">
        <JsonLd data={organizationJsonLd()} />
        <Script id="tema-inicial" strategy="beforeInteractive">
          {SCRIPT_TEMA_INICIAL}
        </Script>
        <Providers>
          <PularParaConteudo />
          <Header />
          <main
            id="conteudo-principal"
            tabIndex={-1}
            className="container scroll-mt-24 py-6 pb-[calc(4rem+env(safe-area-inset-bottom))] focus:outline-none focus-visible:outline-none sm:py-8 sm:pb-6 motion-reduce:transition-none"
          >
            {children}
          </main>
          <div className="pb-[calc(4rem+env(safe-area-inset-bottom)+1rem)] sm:pb-0">
            <Rodape />
          </div>
          <BottomNav />
          <BannerConsentimentoCookies />
        </Providers>
      </body>
    </html>
  );
}
