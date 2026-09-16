"use client";

import Link from "next/link";
import { usePathname, notFound } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/admin", label: "Visão geral", exact: true },
  { href: "/admin/usuarios", label: "Usuários" },
  { href: "/admin/fila", label: "Fila editorial" },
  { href: "/admin/planos", label: "Planos & Limites" },
  { href: "/admin/assinaturas", label: "Assinaturas" },
  { href: "/admin/moderacao", label: "Moderação" },
  { href: "/admin/metricas", label: "Métricas" },
  { href: "/admin/robos", label: "Robôs" },
];

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const { usuario, carregando } = useAuth();
  const pathname = usePathname();
  if (carregando)
    return (
      <div className={cn("container mx-auto max-w-6xl px-4 py-10")}>
        <p className="text-sm text-[var(--cor-texto-suave)]">Carregando…</p>
      </div>
    );
  if (!usuario || usuario.papel !== "admin") notFound();
  return (
    <div className={cn("container mx-auto max-w-6xl min-w-0 px-4 py-6 sm:px-6")}>
      <div className="grid gap-4 sm:gap-6 lg:grid-cols-[200px_minmax(0,1fr)]">
        <nav aria-label="Painel admin" className="flex min-w-0 flex-col gap-1 overflow-hidden break-words rounded-xl border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] p-3 shadow-sm lg:sticky lg:top-20 lg:self-start">
          <h2 className="px-2 py-1 text-xs font-bold uppercase tracking-widest text-[var(--cor-texto-suave)]">Painel</h2>
          {NAV.map((item) => {
            const ativo = item.exact ? pathname === item.href : pathname?.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={ativo ? "page" : undefined}
                className={cn(
                  "rounded-md px-3 py-2 text-sm font-medium transition-colors",
                  ativo
                    ? "bg-[var(--cor-primaria)] text-white shadow-sm"
                    : "text-[var(--cor-texto-suave)] hover:bg-[var(--cor-primaria-suave)] hover:text-[var(--cor-primaria)]"
                )}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div className="min-w-0">{children}</div>
      </div>
    </div>
  );
}
