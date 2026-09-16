"use client";

import Link from "next/link";
import Image from "next/image";
import type { FeedEntrada } from "@/lib/api";
import { obterVisualCategoria } from "@/lib/categoryVisuals";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

interface HeroPrincipalProps {
  entrada: FeedEntrada;
  onClick?: () => void;
}

function hrefDaEntrada(entrada: FeedEntrada): string {
  return `/noticia/${entrada.tipo}/${entrada.id}`;
}

/**
 * Hero notícia protagonista: imagem + título + lead + CTA "Leia agora".
 * Backend não entrega imagem (FeedEntrada sem campo de foto) — usa a
 * imagem OG padrão do portal com width/height explícitos (anti-CLS).
 */
export function HeroPrincipal({ entrada, onClick }: HeroPrincipalProps) {
  const visual = obterVisualCategoria(entrada.categoria);
  const href = hrefDaEntrada(entrada);

  return (
    <Card
      className={cn(
        "relative min-w-0 overflow-hidden border-[var(--cor-borda)] p-0",
        "shadow-[var(--sombra-2)]"
      )}
    >
      <article className="relative min-w-0">
        <div className="relative aspect-[16/9] w-full overflow-hidden sm:aspect-[21/9]" style={{ background: visual.gradiente }}>
          <Image
            src="/og-padrao.svg"
            alt=""
            width={1200}
            height={630}
            priority
            className="h-full w-full object-cover opacity-90"
          />
          <div
            className="pointer-events-none absolute inset-0 bg-gradient-to-t from-black/70 via-black/25 to-transparent"
            aria-hidden="true"
          />
        </div>
        <div className="absolute inset-x-0 bottom-0 min-w-0 space-y-3 p-5 sm:p-8">
          <div className="flex min-w-0 flex-wrap items-center gap-2">
            {entrada.urgente && (
              <Badge variant="destructive" className="min-h-0 uppercase">
                Urgente
              </Badge>
            )}
            <Badge variant="secondary" className="min-h-0 uppercase">
              {entrada.categoria}
            </Badge>
            <span className="text-xs text-white/80">
              {entrada.numero_fontes} {entrada.numero_fontes === 1 ? "fonte" : "fontes"}
            </span>
          </div>
          <h1 className="min-w-0 max-w-[32ch] break-words font-[var(--fonte-titulo)] text-2xl font-bold leading-tight tracking-tight text-white text-wrap-balance sm:text-4xl">
            <Link
              href={href}
              onClick={onClick}
              className="rounded-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white focus-visible:ring-offset-2 focus-visible:ring-offset-black/50 hover:underline"
            >
              {entrada.titulo}
            </Link>
          </h1>
          <p className="min-w-0 max-w-[62ch] break-words text-sm leading-relaxed text-white/90 line-clamp-2 sm:text-lg sm:line-clamp-3">
            {entrada.resumo}
          </p>
          <Link
            href={href}
            onClick={onClick}
            className={cn(
              "inline-flex min-h-[44px] touch-manipulation items-center justify-center rounded-full bg-white px-6 py-3 text-base font-semibold text-[var(--cor-texto)]",
              "transition-colors hover:bg-white/90 motion-reduce:transition-none",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white focus-visible:ring-offset-2 focus-visible:ring-offset-black/50"
            )}
          >
            Leia agora
          </Link>
        </div>
      </article>
    </Card>
  );
}

interface HeroSecundarioProps {
  entrada: FeedEntrada;
  posicao?: number;
}

export function HeroSecundario({ entrada, posicao }: HeroSecundarioProps) {
  const visual = obterVisualCategoria(entrada.categoria);
  const href = hrefDaEntrada(entrada);

  return (
    <Card className="min-w-0 overflow-hidden p-0 transition-shadow hover:shadow-[var(--sombra-2)] motion-reduce:transition-none">
      <article className="min-w-0">
        <div className="relative aspect-video w-full overflow-hidden" style={{ background: visual.gradiente }}>
          <Image
            src="/og-padrao.svg"
            alt=""
            width={600}
            height={338}
            loading="lazy"
            className="h-full w-full object-cover opacity-80"
          />
        </div>
        <div className="min-w-0 space-y-2 p-4">
          <div className="flex min-w-0 flex-wrap items-center gap-2">
            {typeof posicao === "number" && (
              <span className="shrink-0 font-[var(--fonte-titulo)] text-sm font-extrabold tabular-nums text-[var(--cor-texto-suave)]" aria-hidden="true">
                {String(posicao).padStart(2, "0")}
              </span>
            )}
            {entrada.urgente && (
              <Badge variant="destructive" className="min-h-0 uppercase">
                Urgente
              </Badge>
            )}
            <span className="min-w-0 break-words text-[11px] font-bold uppercase tracking-widest" style={{ color: visual.cor }}>
              {entrada.categoria}
            </span>
          </div>
          <h2 className="min-w-0 break-words font-[var(--fonte-titulo)] text-lg font-semibold leading-snug line-clamp-2 text-wrap-balance">
            <Link
              href={href}
              className="rounded-sm hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]"
            >
              {entrada.titulo}
            </Link>
          </h2>
          <p className="min-w-0 break-words text-sm leading-relaxed text-[var(--cor-texto-suave)] line-clamp-2">
            {entrada.resumo}
          </p>
          <Link
            href={href}
            className="inline-flex min-h-[44px] touch-manipulation items-center rounded-sm text-sm font-medium text-[var(--cor-primaria)] hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]"
          >
            Leia agora
          </Link>
        </div>
      </article>
    </Card>
  );
}
