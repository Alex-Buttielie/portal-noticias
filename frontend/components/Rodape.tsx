import Link from "next/link";
import { Rss } from "lucide-react";
import { cn } from "@/lib/utils";

const COLUNAS_RODAPE = [
  {
    titulo: "Institucional",
    links: [
      { label: "Sobre nós", href: "/paginas/sobre" },
      { label: "Equipe editorial", href: "/paginas/equipe" },
      { label: "Código de ética", href: "/paginas/codigo-etica" },
      { label: "Carreiras", href: "/paginas/carreiras" },
    ],
  },
  {
    titulo: "Produto",
    links: [
      { label: "Planos Premium", href: "/planos" },
      { label: "Comunidade", href: "/comunidade" },
      { label: "Radar de tendências", href: "/radar" },
      { label: "Soluções B2B", href: "/empresa" },
    ],
  },
  {
    titulo: "Legal",
    links: [
      { label: "Política de privacidade", href: "/privacidade/politica" },
      { label: "Termos de uso", href: "/paginas/termos" },
      { label: "Preferências de cookies", href: "/privacidade/preferencias-cookies" },
      { label: "LGPD", href: "/privacidade/politica" },
    ],
  },
  {
    titulo: "Redes",
    links: [
      { label: "Twitter / X", href: "https://twitter.com/brdportal", external: true },
      { label: "LinkedIn", href: "https://linkedin.com/company/brdportal", external: true },
      { label: "Instagram", href: "https://instagram.com/brdportal", external: true },
      { label: "Newsletter", href: "/lista-de-espera" },
    ],
  },
];

const LINKS_BASE = [
  { label: "RSS", href: "/rss.xml", icon: true },
  { label: "Termos de uso", href: "/paginas/termos", icon: false },
  { label: "Privacidade", href: "/privacidade/politica", icon: false },
  { label: "Cookies", href: "/privacidade/preferencias-cookies", icon: false },
];

export default function Rodape() {
  const ano = new Intl.DateTimeFormat("pt-BR", { year: "numeric" }).format(new Date());

  return (
    <footer
      className={cn(
        "border-t border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)]",
        "pb-[calc(2rem+env(safe-area-inset-bottom))] pt-10 sm:pb-12",
        "motion-reduce:transition-none"
      )}
      role="contentinfo"
    >
      <div className={cn("container base__linhas", "flex flex-col gap-8")}>
        <nav
          aria-label="Rodapé - navegação institucional"
          className="grid grid-cols-1 flex-col gap-8 md:grid-cols-2 xl:grid-cols-4"
        >
          {COLUNAS_RODAPE.map((coluna) => (
            <section key={coluna.titulo} aria-labelledby={`rodape-${coluna.titulo.toLowerCase()}`}>
              <h2
                id={`rodape-${coluna.titulo.toLowerCase()}`}
                className="text-sm font-semibold text-[var(--cor-texto)] text-balance"
              >
                {coluna.titulo}
              </h2>
              <ul className="mt-3 space-y-2" role="list">
                {coluna.links.map((link) => (
                  <li key={link.label}>
                    <Link
                      href={link.href}
                      target={link.external ? "_blank" : undefined}
                      rel={link.external ? "noopener noreferrer" : undefined}
                      className={cn(
                        "inline-flex min-h-[44px] items-center rounded-sm text-sm touch-manipulation",
                        "text-[var(--cor-texto-suave)] hover:text-[var(--cor-primaria)] transition-colors",
                        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] focus-visible:ring-offset-2",
                        "motion-reduce:transition-none"
                      )}
                    >
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </nav>

        <div className="flex flex-col gap-4 border-t border-[var(--cor-borda)] pt-6 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-sm text-[var(--cor-texto-suave)]">
            © {ano} BRD Portal de Notícias. Todos os direitos reservados.
          </p>

          <ul role="list" className="flex flex-wrap items-center gap-x-4 gap-y-2">
            {LINKS_BASE.map((link) => (
              <li key={link.label}>
                <Link
                  href={link.href}
                  className={cn(
                    "inline-flex min-h-[44px] items-center gap-1.5 rounded-sm text-sm touch-manipulation",
                    "text-[var(--cor-texto-suave)] hover:text-[var(--cor-primaria)] transition-colors",
                    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] focus-visible:ring-offset-2",
                    "motion-reduce:transition-none"
                  )}
                >
                  {link.icon && <Rss className="h-4 w-4" aria-hidden="true" />}
                  {link.label}
                </Link>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </footer>
  );
}
