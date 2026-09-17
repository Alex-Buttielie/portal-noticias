import type { ReactNode } from "react";
export const metadata = { title: "Admin — Painel de controle" };
const NAV = [
  { href: "/admin", label: "Dashboard" },
  { href: "/admin/usuarios", label: "Usuários" },
  { href: "/admin/fila", label: "Fila" },
  { href: "/admin/planos", label: "Planos" },
  { href: "/admin/limites", label: "Limites" },
  { href: "/admin/assinaturas", label: "Assinaturas" },
  { href: "/admin/moderacao", label: "Moderação" },
  { href: "/admin/metricas", label: "Métricas" },
  { href: "/admin/robos", label: "Robôs" },
  { href: "/admin/configuracoes", label: "Configurações" },
];
export default function Layout({ children }: { children: ReactNode }) {
  return (
    <div className="space-y-4">
      <div className="rounded-[var(--raio-lg)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] p-3">
        <p className="text-xs tracking-[0.2em] text-[var(--cor-texto-suave)]">ADMIN — PAINEL DE CONTROLE</p>
        <p className="text-xs text-[var(--cor-texto-suave)]">Operação completa do sistema — usuários, fila, planos, limites, assinaturas, moderação, métricas e robôs</p>
        <div className="mt-3 flex flex-wrap gap-2 text-xs">
          {NAV.map((n) => (
            <a key={n.href} href={n.href} className="rounded-full border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] px-3 py-1.5 text-[var(--cor-texto)] hover:bg-[var(--cor-primaria-suave)] hover:text-[var(--cor-primaria)] transition-colors">
              {n.label}
            </a>
          ))}
        </div>
      </div>
      {children}
    </div>
  );
}
