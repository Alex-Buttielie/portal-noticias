"use client";

import Link from "next/link";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Inbox, Users, CreditCard, Receipt, ShieldAlert, BarChart3, Bot } from "lucide-react";

const CARDS = [
  { href: "/admin/usuarios", titulo: "Usuários", desc: "Busque, filtre e gerencie as contas", icone: Users },
  { href: "/admin/fila", titulo: "Fila editorial", desc: "Aprove ou rejeite notícias pendentes", icone: Inbox },
  { href: "/admin/planos", titulo: "Planos e limites", desc: "Preços e recursos Free e Premium", icone: CreditCard },
  { href: "/admin/assinaturas", titulo: "Assinaturas", desc: "Filtre por status e veja o histórico", icone: Receipt },
  { href: "/admin/moderacao", titulo: "Moderação", desc: "Trate denúncias e aplique ações", icone: ShieldAlert },
  { href: "/admin/metricas", titulo: "Métricas", desc: "Acompanhe os números do negócio", icone: BarChart3 },
  { href: "/admin/robos", titulo: "Robôs", desc: "Fontes RSS, parâmetros e execuções", icone: Bot },
];

export default function AdminHome() {
  return (
    <section className="grid min-w-0 gap-6" aria-labelledby="admin-home-titulo">
      <div className="grid min-w-0 gap-1">
        <h1
          id="admin-home-titulo"
          className="font-[var(--fonte-titulo)] text-3xl font-bold tracking-tight text-balance text-[var(--cor-texto)]"
        >
          Painel de controle
        </h1>
        <p className="text-sm text-[var(--cor-texto-suave)]">Gerencie o portal — acesso restrito a administradores.</p>
      </div>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {CARDS.map((c) => {
          const Icone = c.icone;
          return (
            <Link
              key={c.href}
              href={c.href}
              className="block rounded-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] focus-visible:ring-offset-2"
            >
              <Card className="h-full transition-colors hover:border-[var(--cor-primaria)] hover:shadow-md">
                <CardHeader className="flex flex-row items-start gap-3">
                  <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-[var(--cor-primaria-suave)] text-[var(--cor-primaria)]">
                    <Icone className="h-5 w-5" aria-hidden="true" />
                  </span>
                  <span className="grid gap-1">
                    <CardTitle className="text-base">{c.titulo}</CardTitle>
                    <CardDescription>{c.desc}</CardDescription>
                  </span>
                </CardHeader>
              </Card>
            </Link>
          );
        })}
      </div>
    </section>
  );
}
