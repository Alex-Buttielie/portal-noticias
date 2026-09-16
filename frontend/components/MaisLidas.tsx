"use client";
import Link from "next/link";
import { useMaisLidas } from "@/lib/queries";
import { cn } from "@/lib/utils";

const formatoDataHora = new Intl.DateTimeFormat("pt-BR", {
  day: "2-digit",
  month: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
});

function MetaData({ ts }: { ts: string }) {
  const data = new Date(ts);
  if (Number.isNaN(data.getTime())) return <span>{ts}</span>;
  return <time dateTime={ts}>{formatoDataHora.format(data)}</time>;
}

export default function MaisLidas({ limite = 5 }: { limite?: number }) {
  const { data: itens, isLoading } = useMaisLidas(limite);
  if (isLoading)
    return (
      <div className={cn("rounded-xl border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] p-6")}>
        <p className={cn("text-sm text-[var(--cor-texto-suave)]")}>Carregando…</p>
      </div>
    );
  if (!itens?.length) return null;
  return (
    <div className={cn("w-full min-w-0 overflow-hidden rounded-xl border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] shadow-sm")}>
      <h2 className={cn("break-words border-b border-[var(--cor-borda)] px-4 py-3 font-[var(--fonte-titulo,Georgia)] text-base font-extrabold tracking-[-0.01em]")}>
        Mais lidas
      </h2>
      <ol className={cn("divide-y divide-[var(--cor-borda)]")}>
        {itens.map((e, idx) => (
<li key={`${e.tipo}-${e.id}`} className={cn("grid min-w-0 grid-cols-[2.5rem_1fr] gap-3 overflow-hidden px-4 py-3 hover:bg-[var(--cor-primaria-suave)]/50 motion-reduce:transition-none transition-colors")}>
            <span className={cn("shrink-0 font-[var(--fonte-titulo,Georgia)] text-2xl font-extrabold leading-none text-[var(--cor-borda)] tabular-nums")}>
              {String(idx + 1).padStart(2, "0")}
            </span>
            <div className={cn("min-w-0 overflow-hidden")}>
              <Link
                href={`/noticia/${e.tipo}/${e.id}`}
                className={cn(
                  "min-w-0 break-words line-clamp-2 text-sm font-semibold leading-snug hover:underline touch-manipulation",
                  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] rounded-sm"
                )}
              >
                {e.titulo}
              </Link>
              <span className={cn("mt-1 block min-w-0 break-words text-xs text-[var(--cor-texto-suave)]")}>
                {e.categoria || "geral"} · {e.numero_fontes} {e.numero_fontes === 1 ? "fonte" : "fontes"} · <MetaData ts={e.timestamp} />
              </span>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}
