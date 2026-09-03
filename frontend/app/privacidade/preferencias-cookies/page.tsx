import type { Metadata } from "next";
import PreferenciasCookiesConteudo from "./PreferenciasCookiesConteudo";
import { SITE_URL } from "@/lib/site";

export const metadata: Metadata = {
  title: "Preferências de cookies",
  description: "Gerencie a qualquer momento quais categorias de cookies você aceita neste site.",
  alternates: { canonical: `${SITE_URL}/privacidade/preferencias-cookies` },
  robots: { index: true, follow: true },
};

export default function PaginaPreferenciasCookies() {
  return <PreferenciasCookiesConteudo />;
}
