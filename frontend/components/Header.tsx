"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";
import { Menu, X, Search, LogOut } from "lucide-react";
import { cn } from "@/lib/utils";
import { NAV_ITENS, NAV_ITEM_CONTA, NAV_ITEM_LOGIN, NAV_ITEM_ADMIN } from "@/lib/nav-itens";
import { useAuth } from "@/lib/auth-context";
import { ThemeToggle } from "./ThemeToggle";
export function Header() {
  const pathname = usePathname();
  const router = useRouter();
  const { usuario, fazerLogout } = useAuth();
  const isAdmin = usuario?.papel === "admin";
  const [aberto, setAberto] = useState(false);
  const [busca, setBusca] = useState("");
  function onBusca(e: React.FormEvent) {
    e.preventDefault();
    const q = busca.trim();
    router.push(q ? `/?busca=${encodeURIComponent(q)}` : "/");
    setAberto(false);
  }
  return (
    <header className="sticky top-0 z-[var(--z-cabecalho)] glass border-b border-[var(--cor-borda)]">
      <div className="hud-line" />
      <div className="mx-auto flex h-14 max-w-[1280px] items-center gap-3 px-4 md:h-16 md:px-6">
        <Link href="/" className="flex items-center gap-2 shrink-0">
          <span className="flex h-8 w-8 items-center justify-center rounded-md text-sm font-bold text-[var(--cor-texto-invertido)]" style={{ background: "var(--gradiente-marca)", boxShadow: "0 0 12px var(--cor-neon-ciano)" }} aria-hidden>
            ◈
          </span>
          <span className="hidden text-sm font-bold tracking-tight text-[var(--cor-texto)] sm:block">Portal</span>
          <span className="hidden text-xs text-[var(--cor-texto-suave)] sm:block">HUD</span>
        </Link>
        <nav className="hidden items-center gap-1 md:flex" aria-label="Principal">
          {[...NAV_ITENS, ...(isAdmin ? [NAV_ITEM_ADMIN] : [])].map((item) => {
            const ativo = pathname === item.href || (item.href === "/admin" && pathname.startsWith("/admin"));
            return (
              <Link key={item.href} href={item.href} className={cn("rounded-md px-3 py-2 text-sm font-medium transition-colors", ativo ? "bg-[var(--cor-primaria-suave)] text-[var(--cor-primaria)]" : "text-[var(--cor-texto-suave)] hover:bg-[var(--cor-borda)] hover:text-[var(--cor-texto)]")}>
                {item.label}
              </Link>
            );
          })}
        </nav>
        <form onSubmit={onBusca} className="ml-auto hidden items-center gap-2 md:flex" role="search">
          <div className="relative">
            <Search className="pointer-events-none absolute left-2.5 top-2.5 h-4 w-4 text-[var(--cor-texto-suave)]" />
            <input value={busca} onChange={(e) => setBusca(e.target.value)} placeholder="Buscar…" aria-label="Buscar notícias" className="h-9 w-44 rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] pl-8 pr-3 text-sm text-[var(--cor-texto)] placeholder:text-[var(--cor-texto-suave)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] lg:w-64" />
          </div>
        </form>
        <div className="hidden items-center gap-2 md:flex">
          <ThemeToggle />
          {usuario ? (
            <>
              <Link href={NAV_ITEM_CONTA.href} className="inline-flex h-9 items-center rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] px-3 text-sm font-medium text-[var(--cor-texto)] hover:bg-[var(--cor-borda)]">{usuario.nome?.split(" ")[0] ?? "Conta"}</Link>
              <button type="button" onClick={() => void fazerLogout()} aria-label="Sair" className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] text-[var(--cor-texto-suave)] hover:text-[var(--cor-texto)]"><LogOut className="h-4 w-4" /></button>
            </>
          ) : (
            <Link href={NAV_ITEM_LOGIN.href} className="inline-flex h-9 items-center rounded-md bg-[var(--cor-primaria)] px-4 text-sm font-medium text-[var(--cor-texto-invertido)] hover:bg-[var(--cor-primaria-hover)]">Entrar</Link>
          )}
        </div>
        <button type="button" aria-label={aberto ? "Fechar menu" : "Abrir menu"} aria-expanded={aberto} onClick={() => setAberto((v) => !v)} className="ml-auto inline-flex h-9 w-9 items-center justify-center rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] md:hidden">
          {aberto ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
        </button>
      </div>
      {aberto && (
        <div className="border-t border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] px-4 py-4 md:hidden">
          <form onSubmit={onBusca} className="mb-3 flex gap-2" role="search">
            <input value={busca} onChange={(e) => setBusca(e.target.value)} placeholder="Buscar…" aria-label="Buscar notícias" className="h-10 flex-1 rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo)] px-3 text-sm" />
            <button type="submit" className="inline-flex h-10 items-center rounded-md bg-[var(--cor-primaria)] px-4 text-sm font-medium text-[var(--cor-texto-invertido)]"><Search className="h-4 w-4" /></button>
          </form>
          <nav className="grid gap-1" aria-label="Principal mobile">
            {[...NAV_ITENS, ...(isAdmin ? [NAV_ITEM_ADMIN] : [])].map((item) => {
              const ativo = pathname === item.href || (item.href === "/admin" && pathname.startsWith("/admin"));
              return (
                <Link key={item.href} href={item.href} onClick={() => setAberto(false)} className={cn("rounded-md px-3 py-2.5 text-sm font-medium", ativo ? "bg-[var(--cor-primaria-suave)] text-[var(--cor-primaria)]" : "text-[var(--cor-texto)] hover:bg-[var(--cor-borda)]")}>
                  {item.label}
                </Link>
              );
            })}
            <div className="mt-2 flex items-center justify-between border-t border-[var(--cor-borda)] pt-3">
              <ThemeToggle />
              {usuario ? (
                <button type="button" onClick={() => void fazerLogout()} className="text-sm text-[var(--cor-texto-suave)]">Sair</button>
              ) : (
                <Link href={NAV_ITEM_LOGIN.href} onClick={() => setAberto(false)} className="rounded-md bg-[var(--cor-primaria)] px-4 py-2 text-sm font-medium text-[var(--cor-texto-invertido)]">Entrar</Link>
              )}
            </div>
          </nav>
        </div>
      )}
    </header>
  );
}
