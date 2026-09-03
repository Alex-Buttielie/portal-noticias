import type { MetadataRoute } from "next";
import { SITE_URL } from "@/lib/site";

/**
 * `robots.txt` nativo do Next.js (implementation-contract.md run
 * 20260903-1134-seo-lgpd-design-system, escopo A) — responde em `/robots.txt`.
 * Bloqueia fluxos de conta/privados (nenhum valor de indexação, potencial
 * exposição de rotas de sessão), libera o restante do conteúdo editorial
 * público.
 */
export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: "*",
      allow: "/",
      disallow: [
        "/login",
        "/cadastro",
        "/onboarding",
        "/minha-conta",
        "/admin/",
        "/recuperar-senha",
        "/redefinir-senha",
        "/verificar-email",
        "/jornalista/solicitar",
        "/jornalista/status",
        "/comunidade/nova",
      ],
    },
    sitemap: `${SITE_URL}/sitemap.xml`,
  };
}
