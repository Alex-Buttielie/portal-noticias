"use client";
import Link from "next/link";
import type { FeedEntrada } from "@/lib/api";
import { obterVisualCategoria } from "@/lib/categoryVisuals";
import { cn } from "@/lib/utils";

const formatoDiaMes = new Intl.DateTimeFormat("pt-BR", { day: "2-digit", month: "short" });

function formatData(ts: string): { texto: string; valido: boolean; data: Date | null } {
  const data = new Date(ts);
  if (Number.isNaN(data.getTime())) return { texto: ts, valido: false, data: null };
  return { texto: formatoDiaMes.format(data), valido: true, data };
}

export default function BlocoEditoria({
  categoria,
  itens,
  onVerTodas,
}: {
  categoria: string;
  itens: FeedEntrada[];
  onVerTodas?: () => void;
}) {
  if (!itens.length) return null;
  const visual = obterVisualCategoria(categoria);
  return (
    <section className={cn("w-full min-w-0 space-y-4 overflow-hidden")}>
      <div className={cn("flex min-w-0 items-baseline justify-between gap-3 border-b border-[var(--cor-borda)] pb-3")}>
        <h2
          className={cn(
            "inline-flex items-center gap-2 border-l-[3px] pl-3 font-[var(--fonte-titulo,Georgia)] text-lg font-extrabold tracking-[-0.01em]"
          )}
          style={{ borderColor: visual.cor }}
        >
          <span className={cn("h-1.5 w-1.5 rounded-full shrink-0 hidden")} style={{ background: visual.cor }} aria-hidden="true" />
          {categoria}
        </h2>
{onVerTodas ? (
          <button
            type="button"
            onClick={onVerTodas}
            className={cn(
              "editoria-ver inline-flex min-h-[44px] shrink-0 touch-manipulation items-center justify-center rounded-sm px-2 text-xs font-semibold uppercase tracking-widest text-[var(--cor-texto-suave)] hover:text-[var(--cor-texto)]",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] focus-visible:ring-offset-2",
              "motion-reduce:transition-none transition-colors"
            )}
          >
            Ver tudo →
          </button>
        ) : (
          <Link
            href={`/?categoria=${encodeURIComponent(categoria)}`}
            className={cn(
              "editoria-ver inline-flex min-h-[44px] shrink-0 touch-manipulation items-center justify-center rounded-sm px-2 text-xs font-semibold uppercase tracking-widest text-[var(--cor-texto-suave)] hover:text-[var(--cor-texto)]",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] focus-visible:ring-offset-2",
              "motion-reduce:transition-none transition-colors"
            )}
          >
            Ver tudo →
          </Link>
        )}
      </div>
      <div className={cn("grid min-w-0 gap-4 md:grid-cols-3 editoria-grade")}>
        {itens.slice(0, 3).map((e) => {
          const data = formatData(e.timestamp);
          return (
            <Link
              key={`${e.tipo}-${e.id}`}
              href={`/noticia/${e.tipo}/${e.id}`}
              className={cn(
                "group flex min-w-0 w-full flex-col gap-2 overflow-hidden rounded-lg border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] p-4 touch-manipulation",
                "hover:border-[var(--cor-primaria)] hover:shadow-sm",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] focus-visible:ring-offset-2",
                "motion-reduce:transition-none transition-colors"
              )}
            >
              <span className={cn("min-w-0 break-words text-[11px] font-bold uppercase tracking-widest")} style={{ color: visual.cor }}>
                {e.categoria}
              </span>
              <h3 className={cn("min-w-0 break-words font-[var(--fonte-titulo,Georgia)] text-base font-semibold leading-snug line-clamp-3 group-hover:underline")}>
                {e.titulo}
              </h3>
              <p className={cn("min-w-0 break-words line-clamp-2 text-sm leading-relaxed text-[var(--cor-texto-suave)]")}>{e.resumo}</p>
              <span className={cn("min-w-0 break-words text-xs text-[var(--cor-texto-suave)]")}>
                {data.valido && data.data ? (
                  <time dateTime={e.timestamp}>{data.texto}</time>
                ) : (
                  <span>{data.texto}</span>
                )}
                {" · "}
                {e.numero_fontes} {e.numero_fontes === 1 ? "fonte" : "fontes"}
              </span>
            </Link>
          );
        })}
      </div>
    </section>
  );
}
