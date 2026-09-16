import Link from "next/link";
import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

function cn(...inputs: (string | boolean | undefined)[]) {
  return twMerge(clsx(inputs));
}

export default function Rodape() {
  const ano = new Intl.DateTimeFormat("pt-BR", { year: "numeric" }).format(new Date());
  return (
    <footer
      className={cn(
        // `base` preservado como alias; grid Tailwind 4→2→1
        "base",
        "border-t border-[var(--cor-borda)] bg-[var(--cor-fundo)]",
        "mt-16 py-10 sm:py-12 pb-[calc(2.5rem+env(safe-area-inset-bottom))] sm:pb-12"
      )}
    >
      <div className={cn("container base__linhas", "flex flex-col gap-8")}>
        {/* grid 4 → 2 → 1 */}
        <div className="grid grid-cols-1 gap-8 md:grid-cols-2 lg:grid-cols-4">
          {/* Marca */}
          <div className="base__marca flex flex-col gap-3">
            <Link
              href="/"
              className={cn(
                "topo__marca inline-flex items-center gap-2 self-start rounded-md",
                "text-[var(--cor-texto)] no-underline hover:no-underline",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] focus-visible:ring-offset-2",
                "motion-reduce:transition-none"
              )}
              aria-label="Portal de Notícias — início"
            >
              <span className="topo__orbe h-[22px] w-[22px] shrink-0 rounded-full bg-[var(--gradiente-marca)] shadow-[0_0_16px_rgba(79,70,229,0.45)]" aria-hidden="true" />
              <span className="topo__nome text-base font-bold tracking-tight">
                Portal<em className="not-italic text-[var(--cor-primaria)]">·</em>
              </span>
            </Link>
            <p className="max-w-[32ch] text-sm leading-6 text-[var(--cor-texto-suave)]">
              Você lê rápido, confia e assina — jornalismo agregado e transparente.
            </p>
          </div>

          <nav className="base__links flex flex-col gap-2" aria-label="Seções">
            <h3 className="mb-1 text-xs font-bold uppercase tracking-widest text-[var(--cor-texto)]">Seções</h3>
            {[
              { href: "/", label: "Últimas" },
              { href: "/comunidade", label: "Comunidade" },
              { href: "/radar", label: "Radar" },
              { href: "/planos", label: "Premium" },
            ].map((l) => (
              <Link
                key={l.href}
                href={l.href}
                className={cn(
                  "w-fit rounded-sm text-sm text-[var(--cor-texto-suave)] no-underline transition-colors",
                  "hover:text-[var(--cor-primaria)] hover:underline hover:decoration-[var(--cor-primaria)] hover:underline-offset-4",
                  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] focus-visible:ring-offset-2",
                  "motion-reduce:transition-none"
                )}
              >
                {l.label}
              </Link>
            ))}
          </nav>

          <nav className="base__links flex flex-col gap-2" aria-label="Institucional">
            <h3 className="mb-1 text-xs font-bold uppercase tracking-widest text-[var(--cor-texto)]">Institucional</h3>
            {[
              { href: "/paginas/termos-de-uso", label: "Termos de uso" },
              { href: "/paginas/politica-editorial", label: "Política editorial" },
            ].map((l) => (
              <Link
                key={l.href}
                href={l.href}
                className={cn(
                  "w-fit rounded-sm text-sm text-[var(--cor-texto-suave)] no-underline transition-colors",
                  "hover:text-[var(--cor-primaria)] hover:underline hover:underline-offset-4",
                  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] focus-visible:ring-offset-2",
                  "motion-reduce:transition-none"
                )}
              >
                {l.label}
              </Link>
            ))}
          </nav>

          <nav className="base__links flex flex-col gap-2" aria-label="Privacidade e assinatura">
            <h3 className="mb-1 text-xs font-bold uppercase tracking-widest text-[var(--cor-texto)]">Privacidade</h3>
            <Link
              href="/privacidade/politica"
              className={cn(
                "w-fit rounded-sm text-sm text-[var(--cor-texto-suave)] no-underline transition-colors",
                "hover:text-[var(--cor-primaria)] hover:underline hover:underline-offset-4",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] focus-visible:ring-offset-2",
                "motion-reduce:transition-none"
              )}
            >
              Privacidade
            </Link>
            <Link
              href="/privacidade/preferencias-cookies"
              className={cn(
                "w-fit rounded-sm text-sm text-[var(--cor-texto-suave)] no-underline transition-colors",
                "hover:text-[var(--cor-primaria)] hover:underline hover:underline-offset-4",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] focus-visible:ring-offset-2",
                "motion-reduce:transition-none"
              )}
            >
              Preferências de cookies
            </Link>
            <a
              href="/rss.xml"
              target="_blank"
              rel="noreferrer"
              className={cn(
                "w-fit rounded-sm text-sm text-[var(--cor-texto-suave)] no-underline transition-colors",
                "hover:text-[var(--cor-primaria)] hover:underline hover:underline-offset-4",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] focus-visible:ring-offset-2",
                "motion-reduce:transition-none"
              )}
            >
              RSS
            </a>
          </nav>
        </div>

        <p className="base__fino border-t border-[var(--cor-borda)] pt-6 text-xs leading-5 text-[var(--cor-texto-suave)]">
          © {ano} Portal de Notícias · Você acompanha o essencial do dia
        </p>
      </div>
    </footer>
  );
}
