"use client";

import { Suspense, useEffect, useId, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Menu, X, Search } from "lucide-react";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { cva } from "class-variance-authority";
import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/auth-context";
import ThemeToggle from "@/components/ThemeToggle";
import CommandPalette from "@/components/CommandPalette";
import { NAV_ITENS, NAV_ITEM_CONTA, NAV_ITEM_LOGIN } from "@/lib/nav-itens";

// Re-export NAV_ITENS como fonte única para BottomNav/Sheet (contrato M1)
export { NAV_ITENS, NAV_ITEM_CONTA, NAV_ITEM_LOGIN } from "@/lib/nav-itens";

// shadcn Button (CVA) — Button primitive local ao shell (Frente B)
// preserva variantes/tamanhos do contrato e usa focus-visible:ring + motion-reduce
const buttonVariants = cva(
  "inline-flex items-center justify-center gap-1.5 rounded-full border font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 motion-reduce:transition-none",
  {
    variants: {
      variant: {
        default: "border-transparent bg-[var(--cor-primaria)] text-white hover:bg-[var(--cor-primaria-hover)]",
        ghost: "border-transparent bg-transparent text-[var(--cor-texto-suave)] hover:bg-[var(--cor-primaria-suave)] hover:text-[var(--cor-texto)]",
        outline: "border-[var(--cor-borda)] bg-transparent text-[var(--cor-texto)] hover:border-[var(--cor-primaria)] hover:text-[var(--cor-primaria)]",
      },
      size: {
        default: "h-9 px-4 py-2 text-sm",
        sm: "h-7 rounded-full px-3 text-xs",
        icon: "h-9 w-9 p-0",
        lg: "h-11 px-6 text-sm",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  }
);

// Input shadcn — usado na busca do topo
const inputClass = cn(
  "flex h-9 w-full rounded-full border border-[var(--cor-borda)] bg-[var(--cor-fundo)] px-3 py-1 text-sm",
  "placeholder:text-[var(--cor-texto-suave)] placeholder:opacity-70",
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] focus-visible:ring-offset-0 focus-visible:border-[var(--cor-primaria)]",
  "disabled:cursor-not-allowed disabled:opacity-50",
  "motion-reduce:transition-none"
);

const CATEGORIAS_NAV = [
  { label: "Política", slug: "política" },
  { label: "Economia", slug: "economia" },
  { label: "Esportes", slug: "esportes" },
  { label: "Tecnologia", slug: "tecnologia" },
  { label: "Saúde", slug: "saúde" },
  { label: "Cultura", slug: "cultura" },
  { label: "Mundo", slug: "mundo" },
  { label: "Ciência", slug: "ciência" },
];

const NAV_PRINCIPAL = [
  { href: "/", rotulo: "Últimas" },
  { href: "/comunidade", rotulo: "Comunidade" },
  { href: "/radar", rotulo: "Radar" },
  { href: "/planos", rotulo: "Premium", destaque: true },
];

export default function Header() {
  const { usuario, carregando, fazerLogout } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const [menuAberto, setMenuAberto] = useState(false);
  const [busca, setBusca] = useState("");
  const [paletteAberto, setPaletteAberto] = useState(false);
  const navId = useId();

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteAberto((v) => !v);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    if (!menuAberto) return;
    function onEscape(e: KeyboardEvent) {
      if (e.key === "Escape") setMenuAberto(false);
    }
    window.addEventListener("keydown", onEscape);
    return () => window.removeEventListener("keydown", onEscape);
  }, [menuAberto]);

  function ehAtual(href: string): boolean {
    return href === "/" ? pathname === "/" : pathname?.startsWith(href) ?? false;
  }

  function onSubmitBusca(e: React.FormEvent) {
    e.preventDefault();
    const q = busca.trim();
    router.push(q ? `/?busca=${encodeURIComponent(q)}` : "/");
    setMenuAberto(false);
  }

  const inicial = (usuario?.nome || usuario?.email || "?").trim().charAt(0).toUpperCase();

  const itemConta = usuario ? NAV_ITEM_CONTA : NAV_ITEM_LOGIN;
  const itensSheet = [...NAV_ITENS, itemConta];

  return (
    <header
      className={cn(
        // `topo` legado preservado como alias; Tailwind sticky + glass
        "topo",
        "sticky top-0 z-[var(--z-cabecalho)] border-b border-[var(--cor-borda)] bg-[var(--vidro)] backdrop-blur-[14px]",
        "motion-reduce:transition-none"
      )}
    >
      <div className={cn("container topo__barra", "flex items-center gap-3 sm:gap-4 min-h-[64px]")}>
        <button
          type="button"
          className={cn(
            "topo__menu",
            buttonVariants({ variant: "outline", size: "icon" }),
            "shrink-0 rounded-xl border-[var(--cor-borda)] sm:hidden",
            "aria-expanded:bg-[var(--cor-primaria-suave)]",
            "touch-manipulation min-h-[44px] min-w-[44px]",
            "motion-reduce:transition-none"
          )}
          aria-expanded={menuAberto}
          aria-controls="mobile-nav-sheet"
          aria-label={menuAberto ? "Fechar menu" : "Abrir menu"}
          onClick={() => setMenuAberto((v) => !v)}
        >
          <span aria-hidden="true" className="inline-flex">
            {menuAberto ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
          </span>
        </button>

        <Link
          href="/"
          className={cn(
            "topo__marca",
            "inline-flex items-center gap-2 rounded-md no-underline shrink-0",
            "text-[var(--cor-texto)] hover:text-[var(--cor-texto)]",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] focus-visible:ring-offset-2"
          )}
          aria-label="Portal de Notícias — início"
        >
          <span className="topo__orbe h-[22px] w-[22px] shrink-0 rounded-full bg-[var(--gradiente-marca)] shadow-[0_0_16px_rgba(79,70,229,0.45)]" aria-hidden="true" />
          <span className="topo__nome text-base font-bold tracking-tight">
            Portal<em className="not-italic text-[var(--cor-primaria)]">·</em>
          </span>
        </Link>

        <nav className={cn("topo__nav", "hidden items-center gap-1 sm:flex")} aria-label="Navegação principal">
          {NAV_PRINCIPAL.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              aria-current={ehAtual(item.href) ? "page" : undefined}
              className={cn(
                "topo__link rounded-full px-3 py-2 text-sm font-medium no-underline transition-colors",
                "text-[var(--cor-texto-suave)] hover:bg-[var(--cor-primaria-suave)] hover:text-[var(--cor-texto)]",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] focus-visible:ring-offset-2 motion-reduce:transition-none",
                ehAtual(item.href) && "bg-[var(--cor-primaria-suave)] text-[var(--cor-texto)]",
                item.destaque && "text-[var(--cor-primaria)] hover:text-[var(--cor-primaria)]",
                item.destaque && ehAtual(item.href) && "bg-[var(--cor-primaria-suave)]"
              )}
            >
              {item.rotulo}
            </Link>
          ))}
        </nav>

        <div className={cn("topo__acoes", "ml-auto flex items-center gap-2")}>
          <form className={cn("topo__busca hidden items-center sm:flex")} onSubmit={onSubmitBusca} role="search">
            <label className="sr-only" htmlFor="busca-topo">
              Buscar notícias
            </label>
            <input
              id="busca-topo"
              name="busca"
              type="search"
              autoComplete="off"
              placeholder="Buscar…"
              value={busca}
              onChange={(e) => setBusca(e.target.value)}
              className={cn(inputClass, "w-[160px] lg:w-[190px]")}
            />
          </form>
          <button
            type="button"
            onClick={() => setPaletteAberto(true)}
            aria-label="Busca rápida (Ctrl K)"
            title="Busca rápida (Ctrl K)"
            className={cn(
              "topo__icone",
              "inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-[var(--cor-borda)] bg-transparent text-[var(--cor-texto-suave)]",
              "hover:border-[var(--cor-primaria)] hover:text-[var(--cor-primaria)]",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] focus-visible:ring-offset-2 motion-reduce:transition-none"
            )}
          >
            <Search className="h-4 w-4" aria-hidden="true" />
          </button>
          <ThemeToggle />
          {!carregando &&
            (usuario ? (
              <>
                <Link
                  href="/minha-conta"
                  className={cn(
                    "topo__avatar inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[var(--gradiente-marca)] text-sm font-bold text-white no-underline",
                    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] focus-visible:ring-offset-2"
                  )}
                  aria-label="Minha conta"
                >
                  {inicial}
                </Link>
                <button
                  type="button"
                  className={cn(
                    "topo__sair hidden sm:inline-flex rounded-full px-2 py-1 text-sm text-[var(--cor-texto-suave)] transition-colors",
                    "hover:text-[var(--cor-erro)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]",
                    "motion-reduce:transition-none"
                  )}
                  onClick={() => fazerLogout()}
                >
                  Sair
                </button>
              </>
            ) : (
              <>
                <Link
                  href="/login"
                  className={cn(
                    "topo__link hidden sm:inline-flex rounded-full px-3 py-1.5 text-sm font-medium text-[var(--cor-texto)] hover:bg-[var(--cor-primaria-suave)] no-underline",
                    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]"
                  )}
                >
                  Entrar
                </Link>
                <Link
                  href="/cadastro"
                  className={cn(buttonVariants({ variant: "default", size: "sm" }), "botao botao--primaria botao--pequeno no-underline")}
                >
                  Assine
                </Link>
              </>
            ))}
        </div>
      </div>

      {/* Sheet mobile — Radix Dialog com foco preso, Escape e backdrop */}
      <DialogPrimitive.Root open={menuAberto} onOpenChange={setMenuAberto}>
        <DialogPrimitive.Portal>
          <DialogPrimitive.Overlay
            className={cn(
              "fixed inset-0 z-[var(--z-modal-fundo)] bg-black/40 backdrop-blur-sm",
              "data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0",
              "motion-reduce:animate-none motion-reduce:transition-none",
              "overscroll-contain touch-manipulation"
            )}
            aria-hidden="true"
          />
          <DialogPrimitive.Content
            id="mobile-nav-sheet"
            className={cn(
              "fixed inset-y-0 left-0 z-[var(--z-modal)] flex w-[280px] max-w-[85vw] flex-col",
              "bg-[var(--cor-fundo)] border-r border-[var(--cor-borda)] shadow-lg",
              "overscroll-contain touch-manipulation overflow-y-auto",
              "pb-[env(safe-area-inset-bottom)]",
              "data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:slide-out-to-left data-[state=open]:slide-in-from-left",
              "motion-reduce:animate-none motion-reduce:transition-none",
              "focus-visible:outline-none"
            )}
          >
            <DialogPrimitive.Title className="sr-only">Menu de navegação</DialogPrimitive.Title>
            <div className="flex items-center justify-between gap-3 border-b border-[var(--cor-borda)] p-4">
              <span className="inline-flex items-center gap-2 text-sm font-bold tracking-tight text-[var(--cor-texto)]">
                <span className="h-[18px] w-[18px] shrink-0 rounded-full bg-[var(--gradiente-marca)]" aria-hidden="true" />
                Menu
              </span>
              <DialogPrimitive.Close
                aria-label="Fechar menu"
                className={cn(
                  "inline-flex h-9 w-9 items-center justify-center rounded-full border border-[var(--cor-borda)] bg-transparent",
                  "text-[var(--cor-texto-suave)] hover:text-[var(--cor-texto)] hover:border-[var(--cor-primaria)]",
                  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] focus-visible:ring-offset-2",
                  "touch-manipulation min-h-[44px] min-w-[44px] motion-reduce:transition-none"
                )}
              >
                <X className="h-4 w-4" aria-hidden="true" />
              </DialogPrimitive.Close>
            </div>

            <nav aria-label="Navegação móvel" className="flex flex-col gap-1 p-3">
              {itensSheet.map((item) => {
                const Icon = item.icon;
                const ativo = ehAtual(item.href);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    aria-current={ativo ? "page" : undefined}
                    data-active={ativo ? "true" : undefined}
                    onClick={() => setMenuAberto(false)}
                    className={cn(
                      "flex items-center gap-3 rounded-md px-3 py-1.5",
                      "min-h-[44px] touch-manipulation",
                      "text-sm font-medium no-underline transition-colors",
                      "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] focus-visible:ring-offset-2",
                      "motion-reduce:transition-none",
                      ativo
                        ? "bg-[var(--cor-primaria-suave)] text-[var(--cor-primaria)]"
                        : "text-[var(--cor-texto-suave)] hover:bg-[var(--cor-primaria-suave)] hover:text-[var(--cor-texto)]"
                    )}
                  >
                    <Icon className="h-5 w-5 shrink-0" aria-hidden="true" />
                    <span className="text-sm leading-none">{item.label}</span>
                  </Link>
                );
              })}
            </nav>

            <div className="mt-auto border-t border-[var(--cor-borda)] p-4">
              <form onSubmit={onSubmitBusca} role="search" className="flex items-center gap-2">
                <label htmlFor="busca-sheet" className="sr-only">
                  Buscar notícias
                </label>
                <input
                  id="busca-sheet"
                  name="busca"
                  type="search"
                  autoComplete="off"
                  placeholder="Buscar…"
                  value={busca}
                  onChange={(e) => setBusca(e.target.value)}
                  className={cn(inputClass, "flex-1 min-h-[44px] touch-manipulation text-[16px] sm:text-sm")}
                />
                <button
                  type="submit"
                  aria-label="Buscar"
                  className={cn(
                    buttonVariants({ variant: "default", size: "icon" }),
                    "shrink-0 rounded-full touch-manipulation min-h-[44px] min-w-[44px]"
                  )}
                >
                  <Search className="h-4 w-4" aria-hidden="true" />
                </button>
              </form>
            </div>
          </DialogPrimitive.Content>
        </DialogPrimitive.Portal>
      </DialogPrimitive.Root>

      <div className="container">
        <Suspense fallback={null}>
          <TrilhasNavegacao navId={navId} menuAberto={menuAberto} pathname={pathname} usuario={usuario} />
        </Suspense>
      </div>
      <CommandPalette aberto={paletteAberto} aoFechar={() => setPaletteAberto(false)} />
    </header>
  );
}

function TrilhasNavegacao({
  navId,
  menuAberto,
  pathname,
  usuario,
}: {
  navId: string;
  menuAberto: boolean;
  pathname: string | null;
  usuario: { papel?: string } | null;
}) {
  const searchParams = useSearchParams();
  const categoriaAtiva = pathname === "/" ? searchParams.get("categoria") || "" : null;
  void menuAberto;

  function ehAtual(href: string): boolean {
    return href === "/" ? pathname === "/" : pathname?.startsWith(href) ?? false;
  }

  return (
    <nav
      id={navId}
      className={cn(
        "topo__trilhas hidden items-center gap-4 border-t border-transparent py-3 sm:flex lg:py-0 lg:pb-3"
      )}
      aria-label="Editorias e áreas"
    >
      <div className={cn("topo__pills flex flex-1 gap-1.5 overflow-x-auto scrollbar-none", "[&::-webkit-scrollbar]:hidden")} role="group" aria-label="Filtrar por editoria">
        <Link
          href="/"
          className={cn(
            "topo__pill inline-flex shrink-0 items-center rounded-full border px-3 py-1.5 text-xs font-medium no-underline transition-colors",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] focus-visible:ring-offset-2 motion-reduce:transition-none",
            categoriaAtiva === ""
              ? "topo__pill--ativa border-[var(--cor-primaria)] bg-[var(--cor-primaria)] text-white"
              : "border-[var(--cor-borda)] bg-transparent text-[var(--cor-texto-suave)] hover:border-[var(--cor-primaria)] hover:text-[var(--cor-primaria)]"
          )}
          aria-current={categoriaAtiva === "" ? "page" : undefined}
        >
          Todas
        </Link>
        {CATEGORIAS_NAV.map((c) => (
          <Link
            key={c.slug}
            href={`/?categoria=${encodeURIComponent(c.slug)}`}
            className={cn(
              "topo__pill inline-flex shrink-0 items-center rounded-full border px-3 py-1.5 text-xs font-medium no-underline transition-colors",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] focus-visible:ring-offset-2 motion-reduce:transition-none",
              categoriaAtiva === c.slug
                ? "topo__pill--ativa border-[var(--cor-primaria)] bg-[var(--cor-primaria)] text-white"
                : "border-[var(--cor-borda)] bg-transparent text-[var(--cor-texto-suave)] hover:border-[var(--cor-primaria)] hover:text-[var(--cor-primaria)]"
            )}
            aria-current={categoriaAtiva === c.slug ? "page" : undefined}
          >
            {c.label}
          </Link>
        ))}
      </div>
      <div className={cn("topo__areas flex shrink-0 flex-wrap items-center gap-3")}>
        <Link
          href="/comunidade"
          aria-current={ehAtual("/comunidade") ? "page" : undefined}
          className={cn(
            "rounded-sm px-1 py-1 text-xs font-medium no-underline transition-colors",
            "text-[var(--cor-texto-suave)] hover:text-[var(--cor-texto)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]",
            ehAtual("/comunidade") && "text-[var(--cor-texto)] underline decoration-[var(--cor-texto)] underline-offset-4"
          )}
        >
          Comunidade
        </Link>
        <Link
          href="/radar"
          aria-current={ehAtual("/radar") ? "page" : undefined}
          className={cn(
            "rounded-sm px-1 py-1 text-xs font-medium no-underline transition-colors",
            "text-[var(--cor-texto-suave)] hover:text-[var(--cor-texto)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]",
            ehAtual("/radar") && "text-[var(--cor-texto)] underline decoration-[var(--cor-texto)] underline-offset-4"
          )}
        >
          Radar
        </Link>
        <Link
          href="/planos"
          aria-current={ehAtual("/planos") ? "page" : undefined}
          className={cn(
            "topo__link--destaque rounded-sm px-1 py-1 text-xs font-semibold no-underline",
            "text-[var(--cor-primaria)] hover:text-[var(--cor-primaria-hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]",
            ehAtual("/planos") && "underline underline-offset-4"
          )}
        >
          Premium
        </Link>
        {usuario && (
          <>
            <Link
              href="/jornalista/status"
              aria-current={ehAtual("/jornalista") ? "page" : undefined}
              className={cn(
                "rounded-sm px-1 py-1 text-xs font-medium no-underline text-[var(--cor-texto-suave)] hover:text-[var(--cor-texto)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]",
                ehAtual("/jornalista") && "text-[var(--cor-texto)] underline underline-offset-4"
              )}
            >
              Jornalista
            </Link>
            <Link
              href="/empresa"
              aria-current={ehAtual("/empresa") ? "page" : undefined}
              className={cn(
                "rounded-sm px-1 py-1 text-xs font-medium no-underline text-[var(--cor-texto-suave)] hover:text-[var(--cor-texto)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]",
                ehAtual("/empresa") && "text-[var(--cor-texto)] underline underline-offset-4"
              )}
            >
              Empresa
            </Link>
            {usuario.papel === "admin" && (
              <Link
                href="/admin"
                aria-current={ehAtual("/admin") ? "page" : undefined}
                className={cn(
                  "rounded-sm px-1 py-1 text-xs font-medium no-underline text-[var(--cor-texto-suave)] hover:text-[var(--cor-texto)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]",
                  ehAtual("/admin") && "text-[var(--cor-texto)] underline underline-offset-4"
                )}
              >
                Admin
              </Link>
            )}
          </>
        )}
      </div>
    </nav>
  );
}
