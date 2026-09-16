"use client";
import Link from "next/link";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/Cards";
import { cn } from "@/lib/utils";

const CARDS = [
  { href: "/admin/usuarios", titulo: "Usuários", desc: "Busque, filtre e gerencie as contas" },
  { href: "/admin/fila", titulo: "Fila editorial", desc: "Aprove ou rejeite notícias pendentes" },
  { href: "/admin/planos", titulo: "Planos & Limites", desc: "Preços e recursos Free/Premium" },
  { href: "/admin/assinaturas", titulo: "Assinaturas", desc: "Filtre por status e veja o histórico" },
  { href: "/admin/moderacao", titulo: "Moderação", desc: "Trate denúncias e aplique ações" },
  { href: "/admin/metricas", titulo: "Métricas", desc: "Acompanhe os dashboards do negócio" },
  { href: "/admin/robos", titulo: "Robôs", desc: "Fontes RSS, parâmetros e execuções" },
];
export default function AdminHome() {
  return (
<section className="secao-bloco grid gap-6 min-w-0 w-full max-w-full overflow-hidden" aria-labelledby="admin-home-titulo">
      <div className="grid gap-1 min-w-0">
        <p className="text-xs font-bold uppercase tracking-widest text-[var(--cor-primaria)] secao-eyebrow">Administração</p>
        <h1 id="admin-home-titulo" className="font-[var(--fonte-titulo)] text-3xl font-bold tracking-tight text-[var(--cor-texto)] secao-titulo">Painel de controle</h1>
        <p className="text-sm text-[var(--cor-texto-suave)]">Gerencie o portal — acesso restrito a administradores.</p>
      </div>
      <div className="grade-cartoes grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {CARDS.map((c) => (
          <Link key={c.href} href={c.href} className="block">
            <Card className={cn("h-full p-0 transition-colors hover:border-[var(--cor-primaria)] hover:shadow-md")}>
              <CardHeader className="p-5">
                <CardTitle className="text-base">{c.titulo}</CardTitle>
                <CardDescription>{c.desc}</CardDescription>
              </CardHeader>
            </Card>
          </Link>
        ))}
      </div>
    </section>
  );
}
