"use client";
import Link from "next/link";
import type { FeedEntrada } from "@/lib/api";
import { useMaisLidas } from "@/lib/queries";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

const formatoDataHora = new Intl.DateTimeFormat("pt-BR", {
  day: "2-digit",
  month: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
});

function MetaData({ ts }: { ts: string }) {
  const data = new Date(ts);
  if (Number.isNaN(data.getTime())) return <span className="min-w-0 break-words">{ts}</span>;
  return <time dateTime={ts}>{formatoDataHora.format(data)}</time>;
}

function hrefDaEntrada(e: FeedEntrada): string {
  return `/noticia/${e.tipo}/${e.id}`;
}

export default function MaisLidas({ limite = 5 }: { limite?: number }) {
  const { data: itens, isLoading, isError } = useMaisLidas(limite);

  if (isLoading) {
    return (
      <Card className="w-full min-w-0 space-y-3 p-4" aria-hidden="true">
        <Skeleton className="h-5 w-1/3" />
        {Array.from({ length: limite }).map((_, i) => (
          <div key={i} className="space-y-2">
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-3 w-2/3" />
          </div>
        ))}
        <span className="sr-only" role="status">
          Carregando mais lidas…
        </span>
      </Card>
    );
  }

  if (isError || !itens?.length) return null;

  return (
    <Card className="w-full min-w-0 overflow-hidden p-0">
      <h2 className="break-words border-b border-[var(--cor-borda)] px-4 py-3 font-[var(--fonte-titulo)] text-base font-extrabold tracking-tight text-wrap-balance">
        Mais lidas
      </h2>
      <ol className="divide-y divide-[var(--cor-borda)]" aria-live="polite">
        {itens.map((e, idx) => (
          <li
            key={`${e.tipo}-${e.id}`}
            className={cn(
              "grid min-w-0 grid-cols-[2.5rem_minmax(0,1fr)] gap-3 overflow-hidden px-4 py-3",
              "transition-colors hover:bg-[var(--cor-primaria-suave)]/50 motion-reduce:transition-none"
            )}
          >
            <span
              className="shrink-0 font-[var(--fonte-titulo)] text-2xl font-extrabold leading-none tabular-nums text-[var(--cor-borda)]"
              aria-hidden="true"
            >
              {String(idx + 1).padStart(2, "0")}
            </span>
            <div className="min-w-0 overflow-hidden">
              <Link
                href={hrefDaEntrada(e)}
                className={cn(
                  "min-w-0 break-words text-sm font-semibold leading-snug line-clamp-2 hover:underline",
                  "rounded-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]"
                )}
              >
                {e.titulo}
              </Link>
              <span className="mt-1 block min-w-0 break-words text-xs text-[var(--cor-texto-suave)]">
                {e.categoria || "geral"} · {e.numero_fontes} {e.numero_fontes === 1 ? "fonte" : "fontes"} ·{" "}
                <MetaData ts={e.timestamp} />
              </span>
            </div>
          </li>
        ))}
      </ol>
    </Card>
  );
}
