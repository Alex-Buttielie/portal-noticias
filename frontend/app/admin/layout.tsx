"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { notFound } from "next/navigation";
import { useAuth } from "@/lib/auth-context";

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
  if (carregando) return <div className="container"><p className="texto-suave">Carregando…</p></div>;
  if (!usuario || usuario.papel !== "admin") notFound();
  return (
    <div className="container admin-layout">
      <nav className="admin-sidebar" aria-label="Painel admin">
        <h2 className="admin-sidebar-titulo">Painel</h2>
        {NAV.map((item) => {
          const ativo = item.exact ? pathname === item.href : pathname?.startsWith(item.href);
          return (
            <Link key={item.href} href={item.href} className={`admin-nav-link${ativo ? " admin-nav-link--ativo" : ""}`} aria-current={ativo ? "page" : undefined}>
              {item.label}
            </Link>
          );
        })}
      </nav>
      <div className="admin-conteudo">{children}</div>
    </div>
  );
}
