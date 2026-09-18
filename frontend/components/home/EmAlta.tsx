"use client";
import { memo, useMemo } from "react";
import Link from "next/link";
import { Flame } from "lucide-react";
import type { FeedEntrada } from "@/lib/api";
import {
  explicarScoreEmAlta,
  lerSinaisLocais,
  ordenarEmAlta,
  sinaisNeutros,
  timeAgo,
} from "@/lib/editorial";
import { useHidratado } from "@/lib/hooks/use-hidratado";
import { cn } from "@/lib/utils";

interface EmAltaProps {
  feed: FeedEntrada[];
  limite: number;
  categoriaBuscada?: string | null;
}

/**
 * Em Alta — ranking visual numerado por score composto
 * (cobertura + recência + urgência + engajamento), não só views absolutas.
 * O backend não expõe views/cliques por item; o score usa os sinais
 * disponíveis e cada item explica seus componentes (title + linha auxiliar).
 */
export const EmAlta = memo(function EmAlta({ feed, limite, categoriaBuscada }: EmAltaProps) {
  // Sinais locais (localStorage) só após hidratar — senão o ranking diverge
  // do SSR e quebra a hidratação. Ver `useHidratado`.
  const hidratado = useHidratado();
  const sinais = useMemo(
    () => (hidratado ? lerSinaisLocais(categoriaBuscada) : sinaisNeutros(categoriaBuscada)),
    [hidratado, categoriaBuscada, feed]
  );
  const ranking = useMemo(() => ordenarEmAlta(feed, sinais).slice(0, limite), [feed, sinais, limite]);

  if (ranking.length === 0) {
    return (
      <section aria-label="Em alta" className="rounded-[var(--raio-lg)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] p-4 shadow-[var(--sombra-1)]">
        <h2 className="flex items-center gap-2 text-base font-bold text-[var(--cor-texto)]">
          <Flame className="h-4 w-4 text-[var(--cor-sinal)]" aria-hidden /> Em alta
        </h2>
        <p className="mt-2 text-sm text-[var(--cor-texto-suave)]">Nenhum destaque no momento.</p>
      </section>
    );
  }

  const maxScore = Math.max(...ranking.map((r) => r.score), 1);

  return (
    <section aria-label="Em alta" className="rounded-[var(--raio-lg)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] p-4 shadow-[var(--sombra-1)]">
      <div className="mb-1 flex flex-wrap items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 text-base font-bold text-[var(--cor-texto)]">
          <Flame className="h-4 w-4 text-[var(--cor-sinal)]" aria-hidden /> Em alta
        </h2>
        <span className="rounded-full border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] px-2.5 py-1 text-xs text-[var(--cor-texto-suave)]">
          top {ranking.length} • cobertura + recência + engajamento
        </span>
      </div>
      <ol className="divide-y divide-[var(--cor-borda)]">
        {ranking.map(({ entrada, score }, i) => (
          <li key={`alta-${entrada.tipo}-${entrada.id}`}>
            <Link
              href={`/noticia/${entrada.id}`}
              title={`Score ${score} — ${explicarScoreEmAlta(entrada, sinais)}`}
              className="group flex gap-3 py-2.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] rounded-md"
            >
              <span
                aria-hidden
                className={cn(
                  "w-7 shrink-0 text-center text-xl font-black leading-6 tabular-nums",
                  i < 3 ? "text-[var(--cor-primaria)]" : "text-[var(--cor-texto-suave)]"
                )}
              >
                {i + 1}
              </span>
              <span className="min-w-0 flex-1">
                <span className="line-clamp-2 block text-sm font-semibold leading-tight text-[var(--cor-texto)] group-hover:text-[var(--cor-primaria)] motion-safe:transition-colors">
                  {entrada.titulo}
                </span>
                <span className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-[var(--cor-texto-suave)]">
                  <span className="capitalize">{entrada.categoria || "geral"}</span>
                  <span>• {timeAgo(entrada.timestamp)}</span>
                  <span className="inline-flex items-center gap-1">
                    <span
                      aria-hidden
                      className="inline-block h-1 w-14 overflow-hidden rounded-full bg-[var(--cor-fundo-elevado)] align-middle"
                    >
                      <span
                        className="block h-full rounded-full bg-[var(--cor-primaria)]"
                        style={{ width: `${Math.max(6, Math.round((score / maxScore) * 100))}%` }}
                      />
                    </span>
                    <span className="sr-only">relevância {Math.round((score / maxScore) * 100)} por cento</span>
                  </span>
                </span>
                <span className="mt-0.5 block truncate text-[11px] text-[var(--cor-texto-suave)]">
                  {explicarScoreEmAlta(entrada, sinais)}
                </span>
              </span>
            </Link>
          </li>
        ))}
      </ol>
      <Link href="/ao-vivo" className="mt-2 inline-flex text-xs font-medium text-[var(--cor-primaria)] hover:underline">
        Ver cobertura ao vivo →
      </Link>
    </section>
  );
});
