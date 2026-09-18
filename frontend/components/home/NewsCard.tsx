"use client";
import { memo } from "react";
import Link from "next/link";
import { Bookmark, BookmarkCheck, MapPin } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { ImagemNoticia } from "@/components/ImagemNoticia";
import { cn } from "@/lib/utils";
import type { FeedEntrada } from "@/lib/api";
import {
  derivarSelo,
  formatarCredito,
  formatarDataHora,
  formatarLocalidade,
  timeAgo,
  type SeloEditorial,
} from "@/lib/editorial";

const SELO_ESTILO: Record<SeloEditorial, string> = {
  Urgente: "bg-[var(--cor-sinal)] text-[var(--cor-texto-invertido)]",
  Exclusivo: "bg-[var(--cor-premium)] text-[var(--cor-texto-invertido)]",
  Especial: "bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]",
  Análise: "bg-[var(--cor-fundo-elevado)] text-[var(--cor-primaria)] border border-[var(--cor-primaria)]",
  Opinião: "bg-[var(--cor-fundo-elevado)] text-[var(--cor-texto)] border border-[var(--cor-borda)]",
  Entrevista: "bg-[var(--cor-fundo-elevado)] text-[var(--cor-primaria)] border border-dashed border-[var(--cor-primaria)]",
};

export function SeloBadge({ selo }: { selo: SeloEditorial }) {
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center rounded-full px-2 py-0.5 text-[11px] font-bold leading-4",
        SELO_ESTILO[selo]
      )}
    >
      {selo}
    </span>
  );
}

export function LocalidadeTag({ entrada, className }: { entrada: FeedEntrada; className?: string }) {
  const local = formatarLocalidade(entrada);
  if (!local) return null;
  return (
    <span className={cn("inline-flex min-w-0 items-center gap-1 text-xs text-[var(--cor-texto-suave)]", className)}>
      <MapPin className="h-3 w-3 shrink-0" aria-hidden />
      <span className="truncate">{local}</span>
    </span>
  );
}

export function MetaLinha({ entrada, mostrarFontes = true }: { entrada: FeedEntrada; mostrarFontes?: boolean }) {
  const credito = formatarCredito(entrada);
  return (
    <p className="flex min-w-0 flex-wrap items-center gap-x-1.5 gap-y-0.5 text-xs text-[var(--cor-texto-suave)]">
      <Link
        href={`/categoria/${encodeURIComponent(entrada.categoria)}`}
        onClick={(e) => e.stopPropagation()}
        className="font-medium capitalize text-[var(--cor-primaria)] hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] rounded-full"
      >
        {entrada.categoria || "geral"}
      </Link>
      <LocalidadeTag entrada={entrada} />
      <time dateTime={entrada.timestamp} title={formatarDataHora(entrada.timestamp)}>
        {formatarDataHora(entrada.timestamp)} ({timeAgo(entrada.timestamp)})
      </time>
      {mostrarFontes && <span aria-label={`${entrada.numero_fontes} fontes`}>• {entrada.numero_fontes} {entrada.numero_fontes === 1 ? "fonte" : "fontes"}</span>}
      {credito && <span className="truncate">• {credito}</span>}
    </p>
  );
}

interface NewsCardProps {
  entrada: FeedEntrada;
  variante?: "destaque" | "secundaria" | "lista";
  salvo?: boolean;
  onToggleSalvar?: (entrada: FeedEntrada) => void;
  eager?: boolean;
}

/**
 * Card clicável por inteiro (link estendido) — sem botões grandes.
 * O "Salvar" é um ícone discreto que não quebra o clique no card.
 */
export const NewsCard = memo(function NewsCard({ entrada, variante = "secundaria", salvo, onToggleSalvar, eager }: NewsCardProps) {
  const selo = derivarSelo(entrada);
  const href = `/noticia/${entrada.id}`;
  const resumoCurto = (entrada.resumo || "").trim().slice(0, variante === "destaque" ? 220 : 140);

  return (
    <article
      className={cn(
        "group relative flex overflow-hidden rounded-[var(--raio-lg)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] motion-safe:transition-all hover:shadow-[var(--sombra-2)] hover:-translate-y-0.5",
        variante === "destaque" ? "flex-col md:grid md:grid-cols-[1.5fr_1fr]" : "flex-col"
      )}
    >
      <Link
        href={href}
        aria-label={entrada.titulo}
        className="block overflow-hidden bg-[var(--cor-fundo-elevado)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[var(--cor-foco)]"
      >
        <ImagemNoticia
          src={entrada.imagem_url}
          seed={`${entrada.categoria || "geral"}-${entrada.id}`}
          alt={entrada.titulo}
          eager={eager}
          sizes={variante === "destaque" ? "(max-width: 768px) 100vw, 60vw" : "(max-width: 640px) 100vw, (max-width: 1024px) 50vw, 33vw"}
          className={cn(
            "w-full object-cover motion-safe:transition motion-safe:duration-300 group-hover:motion-safe:scale-[1.02]",
            variante === "destaque" ? "aspect-[16/9] md:h-full md:min-h-[320px]" : "aspect-[16/9]"
          )}
        />
      </Link>
      <div className={cn("flex min-w-0 flex-1 flex-col gap-2", variante === "destaque" ? "p-5 md:p-6" : "p-4")}>
        <div className="flex flex-wrap items-center gap-2">
          {selo && <SeloBadge selo={selo} />}
          {entrada.urgente && selo !== "Urgente" && (
            <span className="h-1.5 w-1.5 rounded-full bg-[var(--cor-sinal)] motion-safe:animate-pulse" aria-label="Urgente" />
          )}
          {onToggleSalvar && (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onToggleSalvar(entrada);
              }}
              aria-pressed={!!salvo}
              aria-label={salvo ? "Remover dos salvos" : "Salvar para ler depois"}
              title={salvo ? "Remover dos salvos" : "Salvar para ler depois"}
              className="ml-auto inline-flex h-7 w-7 items-center justify-center rounded-full border border-[var(--cor-borda)] text-[var(--cor-texto-suave)] hover:bg-[var(--cor-fundo-elevado)] hover:text-[var(--cor-texto)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]"
            >
              {salvo ? <BookmarkCheck className="h-3.5 w-3.5" /> : <Bookmark className="h-3.5 w-3.5" />}
            </button>
          )}
        </div>
        <Link
          href={href}
          className={cn(
            "text-balance font-bold leading-tight text-[var(--cor-texto)] hover:text-[var(--cor-primaria)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] motion-safe:transition-colors",
            variante === "destaque" ? "text-2xl md:text-3xl line-clamp-3" : "text-[15px] line-clamp-2"
          )}
        >
          {entrada.titulo}
        </Link>
        {resumoCurto && (
          <Link
            href={href}
            className={cn(
              "leading-snug text-[var(--cor-texto-suave)] hover:text-[var(--cor-texto)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] motion-safe:transition-colors",
              variante === "destaque" ? "text-sm line-clamp-3" : "text-sm line-clamp-2"
            )}
          >
            {resumoCurto}
          </Link>
        )}
        <div className="mt-auto pt-1">
          <MetaLinha entrada={entrada} />
        </div>
      </div>
      {variante === "destaque" && <Badge className="sr-only">Manchete principal</Badge>}
    </article>
  );
});
