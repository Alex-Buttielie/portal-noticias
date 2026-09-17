"use client";
import { memo, useMemo, useState } from "react";
import Link from "next/link";
import { PartyPopper } from "lucide-react";
import type { FeedEntrada } from "@/lib/api";
import { CATEGORIAS_BOMBANDO } from "@/lib/editorial";
import { NewsCard } from "./NewsCard";

interface ConteudoBombandoProps {
  feed: FeedEntrada[];
  limite: number;
  salvos: Set<string>;
  onToggleSalvar: (entrada: FeedEntrada) => void;
}

const norm = (v: string) => (v || "").trim().toLowerCase();

/**
 * Conteúdo Bombando — entretenimento/cultura/celebridades com identidade
 * própria (cabeçalho vibrante) mas coerente (mesmos cards e tokens).
 * Expansão inline, sem modal.
 */
export const ConteudoBombando = memo(function ConteudoBombando({ feed, limite, salvos, onToggleSalvar }: ConteudoBombandoProps) {
  const [expandido, setExpandido] = useState(false);
  const itens = useMemo(() => {
    const conjunto = new Set(CATEGORIAS_BOMBANDO.map(norm));
    return feed.filter((n) => conjunto.has(norm(n.categoria)));
  }, [feed]);

  if (itens.length === 0) return null;

  const visiveis = expandido ? itens.slice(0, Math.max(limite, 12)) : itens.slice(0, limite);

  return (
    <section aria-label="Conteúdo bombando" className="overflow-hidden rounded-[var(--raio-lg)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] shadow-[var(--sombra-1)]">
      <div className="px-4 pt-4 md:px-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="flex items-center gap-2 text-base font-bold text-[var(--cor-texto)]">
            <span className="inline-flex h-7 w-7 items-center justify-center rounded-full bg-[var(--cor-premium-suave)] text-[var(--cor-premium)]">
              <PartyPopper className="h-4 w-4" aria-hidden />
            </span>
            Conteúdo bombando
          </h2>
          <span className="rounded-full border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] px-2.5 py-1 text-xs text-[var(--cor-texto-suave)]">
            {itens.length} {itens.length === 1 ? "matéria leve" : "matérias leves"} • cultura & entretenimento
          </span>
        </div>
        <p className="mt-1 text-xs text-[var(--cor-texto-suave)]">
          O lado leve do dia — sem misturar com o noticiário principal.
        </p>
      </div>
      <div className="grid gap-4 p-4 sm:grid-cols-2 md:px-5 lg:grid-cols-4">
        {visiveis.map((entrada) => (
          <NewsCard
            key={`bomb-${entrada.tipo}-${entrada.id}`}
            entrada={entrada}
            variante="secundaria"
            salvo={salvos.has(`${entrada.tipo}-${entrada.id}`)}
            onToggleSalvar={onToggleSalvar}
          />
        ))}
      </div>
      <div className="flex flex-wrap items-center gap-2 border-t border-[var(--cor-borda)] px-4 py-3 md:px-5">
        {itens.length > limite && (
          <button
            type="button"
            onClick={() => setExpandido((v) => !v)}
            aria-expanded={expandido}
            className="rounded-full border border-[var(--cor-borda)] px-3 py-1.5 text-xs font-medium text-[var(--cor-texto)] hover:bg-[var(--cor-fundo-elevado)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]"
          >
            {expandido ? "Mostrar menos" : `Mostrar mais (${itens.length - limite})`}
          </button>
        )}
        <Link href="/categoria/cultura" className="text-xs font-medium text-[var(--cor-primaria)] hover:underline">
          Ver tudo de cultura →
        </Link>
      </div>
    </section>
  );
});
