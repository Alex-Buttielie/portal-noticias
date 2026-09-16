"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname, notFound } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { LayoutDashboard, Users, Inbox, CreditCard, Receipt, ShieldAlert, BarChart3, Bot, Menu } from "lucide-react";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/admin", label: "Visão geral", exact: true, icone: LayoutDashboard },
  { href: "/admin/usuarios", label: "Usuários", icone: Users },
  { href: "/admin/fila", label: "Fila editorial", icone: Inbox },
  { href: "/admin/planos", label: "Planos e limites", icone: CreditCard },
  { href: "/admin/assinaturas", label: "Assinaturas", icone: Receipt },
  { href: "/admin/moderacao", label: "Moderação", icone: ShieldAlert },
  { href: "/admin/metricas", label: "Métricas", icone: BarChart3 },
  { href: "/admin/robos", label: "Robôs", icone: Bot },
];

function ListaNavegacao({ pathname, aoNavegar }: { pathname: string | null; aoNavegar?: () => void }) {
  return (
    <ul className="grid gap-1">
      {NAV.map((item) => {
        const ativo = item.exact ? pathname === item.href : pathname?.startsWith(item.href);
        const Icone = item.icone;
        return (
          <li key={item.href}>
            <Link
              href={item.href}
              aria-current={ativo ? "page" : undefined}
              onClick={aoNavegar}
              className={cn(
                "flex min-h-[44px] touch-manipulation items-center gap-3 rounded-md px-3 py-2 text-sm font-medium",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] focus-visible:ring-offset-2",
                ativo
                  ? "bg-[var(--cor-primaria)] text-white shadow-sm"
                  : "text-[var(--cor-texto-suave)] hover:bg-[var(--cor-primaria-suave)] hover:text-[var(--cor-primaria)]"
              )}
            >
              <Icone className="h-4 w-4 shrink-0" aria-hidden="true" />
              {item.label}
            </Link>
          </li>
        );
      })}
    </ul>
  );
}

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const { usuario, carregando } = useAuth();
  const pathname = usePathname();
  const [menuAberto, setMenuAberto] = useState(false);

  if (carregando) {
    return (
      <div className="mx-auto w-full max-w-6xl px-4 py-10">
        <p className="text-sm text-[var(--cor-texto-suave)]">Carregando…</p>
      </div>
    );
  }
  if (!usuario || usuario.papel !== "admin") notFound();

  return (
    <div className="mx-auto w-full max-w-6xl min-w-0 px-4 py-6 sm:px-6">
      <div className="mb-4 lg:hidden">
        <Sheet open={menuAberto} onOpenChange={setMenuAberto}>
          <SheetTrigger asChild>
            <Button variant="outline" aria-expanded={menuAberto} aria-controls="menu-admin">
              <Menu className="h-4 w-4" aria-hidden="true" />
              Menu do painel
            </Button>
          </SheetTrigger>
          <SheetContent side="left" id="menu-admin" aria-label="Menu do painel admin">
            <SheetHeader>
              <SheetTitle>Painel admin</SheetTitle>
            </SheetHeader>
            <nav aria-label="Painel admin">
              <ListaNavegacao pathname={pathname} aoNavegar={() => setMenuAberto(false)} />
            </nav>
          </SheetContent>
        </Sheet>
      </div>
      <div className="grid gap-6 lg:grid-cols-[220px_minmax(0,1fr)]">
        <aside className="hidden lg:block">
          <nav
            aria-label="Painel admin"
            className="min-w-0 rounded-xl border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-3 shadow-sm lg:sticky lg:top-20"
          >
            <h2 className="px-2 py-1 text-xs font-bold uppercase tracking-widest text-[var(--cor-texto-suave)]">
              Painel
            </h2>
            <ListaNavegacao pathname={pathname} />
          </nav>
        </aside>
        <div className="min-w-0">{children}</div>
      </div>
    </div>
  );
}
