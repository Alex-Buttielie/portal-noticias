"use client";

import Link from "next/link";
import type { FeedEntrada } from "@/lib/api";
import { obterVisualCategoria } from "@/lib/categoryVisuals";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

const formatoDiaMes = new Intl.DateTimeFormat("pt-BR", { day: "2-digit", month: "short" });

function MetaLinha({ entrada }: { entrada: FeedEntrada }) {
  const data = new Date(entrada.timestamp);
  const valida = !Number.isNaN(data.getTime());
  return (
    <span className="min-w-0 break-words text-xs text-[var(--cor-texto-suave)]">
      {valida ? <time dateTime={entrada.timestamp}>{formatoDiaMes.format(data)}</time> : <span>{entrada.timestamp}</span>}
      {" · "}
      {entrada.numero_fontes} {entrada.numero_fontes === 1 ? "fonte" : "fontes"}
    </span>
  );
}

interface BlocoEditoriaProps {
  categoria: string;
  itens: FeedEntrada[];
  onVerTodas?: () => void;
  carrosselMobile?: boolean;
}

export default function BlocoEditoria({
  categoria,
  itens,
  onVerTodas,
  carrosselMobile = false,
}: BlocoEditoriaProps) {
  if (!itens.length) return null;
  const visual = obterVisualCategoria(categoria);
  const verTodasHref = `/?categoria=${encodeURIComponent(categoria)}`;

  const cards = itens.slice(0, 4).map((e) => (
    <Card
      key={`${e.tipo}-${e.id}`}
      className={cn(
        "min-w-0 p-4 transition-colors hover:border-[var(--cor-primaria)] motion-reduce:transition-none",
        carrosselMobile && "w-[280px] shrink-0 snap-start"
      )}
    >
      <article className="flex min-w-0 flex-col gap-2">
        <span
          className="min-w-0 break-words text-[11px] font-bold uppercase tracking-widest"
          style={{ color: visual.cor }}
        >
          {e.categoria}
        </span>
        <h3 className="min-w-0 break-words font-[var(--fonte-titulo)] text-base font-semibold leading-snug text-wrap-balance line-clamp-3">
          <Link
            href={`/noticia/${e.tipo}/${e.id}`}
            className="rounded-sm hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]"
          >
            {e.titulo}
          </Link>
        </h3>
        <p className="min-w-0 break-words text-sm leading-relaxed text-[var(--cor-texto-suave)] line-clamp-2">
          {e.resumo}
        </p>
        <MetaLinha entrada={e} />
      </article>
    </Card>
  ));

  return (
    <section className="w-full min-w-0 space-y-4 overflow-hidden" aria-label={`Editoria ${categoria}`}>
      <div className="flex min-w-0 items-baseline justify-between gap-3 border-b border-[var(--cor-borda)] pb-3">
        <h2
          className="min-w-0 break-words border-l-[3px] pl-3 font-[var(--fonte-titulo)] text-lg font-extrabold tracking-tight text-wrap-balance"
          style={{ borderColor: visual.cor }}
        >
          {categoria}
        </h2>
        {onVerTodas ? (
          <button
            type="button"
            onClick={onVerTodas}
            className={cn(
              "inline-flex min-h-[44px] shrink-0 touch-manipulation items-center justify-center rounded-sm px-2 text-xs font-semibold uppercase tracking-widest text-[var(--cor-texto-suave)]",
              "transition-colors hover:text-[var(--cor-primaria)] motion-reduce:transition-none",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] focus-visible:ring-offset-2"
            )}
          >
            Ver tudo
          </button>
        ) : (
          <Link
            href={verTodasHref}
            className={cn(
              "inline-flex min-h-[44px] shrink-0 touch-manipulation items-center justify-center rounded-sm px-2 text-xs font-semibold uppercase tracking-widest text-[var(--cor-texto-suave)]",
              "transition-colors hover:text-[var(--cor-primaria)] motion-reduce:transition-none",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] focus-visible:ring-offset-2"
            )}
          >
            Ver tudo
          </Link>
        )}
      </div>
      {carrosselMobile ? (
        <div
          className="-mx-4 flex snap-x snap-mandatory gap-4 overflow-x-auto px-4 pb-4"
          role="list"
          aria-label={`${categoria} — arraste para ver mais`}
        >
          {cards}
        </div>
      ) : (
        <div className="grid min-w-0 grid-cols-1 gap-4 sm:grid-cols-2" role="list" aria-label={`${categoria} — notícias`}>
          {cards}
        </div>
      )}
    </section>
  );
}
