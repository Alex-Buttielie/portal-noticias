"use client";

import { useState } from "react";
import Link from "next/link";
import * as api from "@/lib/api";
import * as bookmarks from "@/lib/bookmarks";
import { useToast } from "@/components/ToastProvider";
import MaisLidas from "@/components/MaisLidas";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

interface HomeSidebarProps {
  inicial: {
    feed: api.FeedResposta;
    urgentes: api.FeedEntrada[];
    maisLidas: api.FeedEntrada[];
    onboarding: { interesses: string[] };
  };
}

export default function HomeSidebar({ inicial }: HomeSidebarProps) {
  void inicial;
  const { notificar } = useToast();
  const [emailNewsletter, setEmailNewsletter] = useState("");
  const [carregandoNewsletter, setCarregandoNewsletter] = useState(false);
  const [salvos] = useState<api.FeedEntrada[]>(() => {
    try {
      return bookmarks.obterSalvos();
    } catch {
      return [];
    }
  });

  async function onNewsletter(e: React.FormEvent) {
    e.preventDefault();
    const email = emailNewsletter.trim();
    if (!email) return;
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      notificar("Digite um e-mail válido.", "erro");
      return;
    }
    setCarregandoNewsletter(true);
    try {
      const r = await api.assinarNewsletterPublica(email, "geral");
      notificar(r.detail || "Inscrição confirmada — confira seu e-mail!", "sucesso");
      setEmailNewsletter("");
    } catch (err: unknown) {
      notificar(err instanceof api.ApiError ? err.message : "Não foi possível inscrever. Tente novamente.", "erro");
    } finally {
      setCarregandoNewsletter(false);
    }
  }

  return (
    <>
      <MaisLidas limite={5} />
      <Card className="min-w-0 space-y-2 bg-[var(--cor-secundaria)] p-5 text-[var(--cor-texto-invertido)]">
        <h2 className="break-words font-[var(--fonte-titulo)] text-base font-bold text-wrap-balance">
          Receba as principais
        </h2>
        <p className="break-words text-sm opacity-80">As manchetes do dia no seu e-mail.</p>
        <form onSubmit={onNewsletter} className="mt-3 flex min-w-0 flex-wrap gap-2">
          <label htmlFor="newsletter-email-sidebar" className="sr-only">
            E-mail para newsletter
          </label>
          <Input
            id="newsletter-email-sidebar"
            type="email"
            name="email"
            autoComplete="email"
            placeholder="Seu e-mail…"
            value={emailNewsletter}
            onChange={(e) => setEmailNewsletter(e.target.value)}
            required
            className={cn(
              "min-w-0 flex-1 border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] text-[16px] text-[var(--cor-texto)] sm:text-sm"
            )}
          />
          <Button type="submit" loading={carregandoNewsletter} className="shrink-0">
            Assinar
          </Button>
        </form>
      </Card>
      <Card className="min-w-0 overflow-hidden p-0">
        <div className="flex min-w-0 items-center justify-between gap-2 border-b border-[var(--cor-borda)] px-4 py-3">
          <h2 className="break-words font-[var(--fonte-titulo)] text-sm font-extrabold">Salvos para ler depois</h2>
          <Button variante="fantasma" tamanho="pequeno" asChild className="shrink-0">
            <Link href="/comunidade">Ver todos</Link>
          </Button>
        </div>
        <div className="px-4 py-3">
          {salvos.length === 0 ? (
            <p className="m-0 break-words text-sm text-[var(--cor-texto-suave)]">
              Salve notícias para ler depois — elas aparecem aqui.
            </p>
          ) : (
            <ul className="m-0 flex min-w-0 flex-col gap-1.5 pl-4 text-sm">
              {salvos.slice(0, 3).map((s) => (
                <li key={`${s.tipo}-${s.id}`} className="min-w-0 break-words marker:text-[var(--cor-texto-suave)]">
                  <Link href={`/noticia/${s.tipo}/${s.id}`} className="break-words text-[var(--cor-primaria)] hover:underline">
                    {s.titulo}
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </div>
      </Card>
    </>
  );
}
