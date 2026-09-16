import * as React from "react";
import Link from "next/link";
import type { FeedEntrada } from "@/lib/api";
import { obterVisualCategoria } from "@/lib/categoryVisuals";
import BotaoSalvar from "@/components/BotaoSalvar";
import { cn } from "@/lib/utils";

// shadcn Card primitives — min-w-0 + break-words evita estouro em 360 (M3)
const Card = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        "min-w-0 overflow-hidden break-words rounded-xl border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] text-[var(--cor-texto)] shadow-sm transition-colors motion-reduce:transition-none",
        className
      )}
      {...props}
    />
  )
);
Card.displayName = "Card";

const CardHeader = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn("flex min-w-0 flex-col space-y-1.5 p-4", className)} {...props} />
  )
);
CardHeader.displayName = "CardHeader";

const CardTitle = React.forwardRef<HTMLParagraphElement, React.HTMLAttributes<HTMLHeadingElement>>(
  ({ className, ...props }, ref) => (
    <h3
      ref={ref}
      className={cn(
        "min-w-0 break-words font-[var(--fonte-titulo,Georgia)] text-base font-semibold leading-tight tracking-[-0.025em] text-wrap-balance",
        className
      )}
      {...props}
    />
  )
);
CardTitle.displayName = "CardTitle";

const CardDescription = React.forwardRef<HTMLParagraphElement, React.HTMLAttributes<HTMLParagraphElement>>(
  ({ className, ...props }, ref) => (
    <p ref={ref} className={cn("min-w-0 break-words text-sm text-[var(--cor-texto-suave)] line-clamp-3", className)} {...props} />
  )
);
CardDescription.displayName = "CardDescription";

const CardContent = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => <div ref={ref} className={cn("min-w-0 p-4 pt-0", className)} {...props} />
);
CardContent.displayName = "CardContent";

const CardFooter = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn("flex min-w-0 items-center p-4 pt-0", className)} {...props} />
  )
);
CardFooter.displayName = "CardFooter";

function hrefDaEntrada(entrada: FeedEntrada): string {
  return entrada.tipo === "cluster" ? `/noticia/cluster/${entrada.id}` : `/noticia/item/${entrada.id}`;
}

const formatoDiaMes = new Intl.DateTimeFormat("pt-BR", { day: "2-digit", month: "short" });

function Meta({ entrada }: { entrada: FeedEntrada }) {
  const data = new Date(entrada.timestamp);
  const dataValida = !Number.isNaN(data.getTime());
  return (
    <div className="flex min-w-0 flex-wrap items-center gap-2 break-words text-xs text-[var(--cor-texto-suave)]">
      <span className="min-w-0 break-words font-medium text-[var(--cor-texto)]">{entrada.categoria}</span>
      {entrada.urgente && (
        <span className="inline-flex items-center rounded bg-[var(--cor-erro)] px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide text-white">
          Urgente
        </span>
      )}
      {entrada.numero_fontes > 1 && <span>{entrada.numero_fontes} fontes</span>}
      {dataValida && (
        <time dateTime={entrada.timestamp} className="tabular-nums">
          {formatoDiaMes.format(data)}
        </time>
      )}
    </div>
  );
}

export function NewsCard({ entrada }: { entrada: FeedEntrada }) {
  const visual = obterVisualCategoria(entrada.categoria);
  return (
    <Card className="overflow-hidden transition-all hover:shadow-md hover:border-[var(--cor-primaria)] motion-reduce:hover:shadow-sm">
      <Link
        href={hrefDaEntrada(entrada)}
        className="block h-40 w-full overflow-hidden bg-[var(--cor-borda)]"
        style={{ background: visual.gradiente }}
        aria-hidden="true"
        tabIndex={-1}
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={`data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='400' height='160'><rect width='100%' height='100%' fill='transparent'/><text x='50%' y='50%' dominant-baseline='middle' text-anchor='middle' font-size='48'>${visual.emoji}</text></svg>`}
          alt=""
          width={400}
          height={160}
          className="h-full w-full object-cover opacity-90"
          aria-hidden="true"
        />
      </Link>
      <CardHeader className="pb-2">
        <Meta entrada={entrada} />
        <CardTitle className="line-clamp-3">
          <Link
            href={hrefDaEntrada(entrada)}
            className="hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] rounded-sm"
          >
            {entrada.titulo}
          </Link>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="min-w-0 break-words line-clamp-3 text-sm leading-relaxed text-[var(--cor-texto-suave)]">{entrada.resumo}</p>
        <BotaoSalvar entrada={entrada} />
      </CardContent>
    </Card>
  );
}

export function FeaturedNewsCard({ entrada }: { entrada: FeedEntrada }) {
  const visual = obterVisualCategoria(entrada.categoria);
  return (
    <Card className="overflow-hidden border-[var(--cor-primaria)]/20 transition-all hover:shadow-lg motion-reduce:hover:shadow-sm">
      <Link
        href={hrefDaEntrada(entrada)}
        className="block h-56 w-full overflow-hidden"
        style={{ background: visual.gradiente }}
        aria-hidden="true"
        tabIndex={-1}
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={`data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='600' height='224'><rect width='100%' height='100%' fill='transparent'/><text x='50%' y='50%' dominant-baseline='middle' text-anchor='middle' font-size='56'>${visual.emoji}</text></svg>`}
          alt=""
          width={600}
          height={224}
          className="h-full w-full object-cover"
          aria-hidden="true"
        />
      </Link>
      <CardHeader>
        <Meta entrada={entrada} />
        <h2 className="min-w-0 break-words font-[var(--fonte-titulo,Georgia)] text-xl font-bold leading-tight tracking-[-0.025em] text-wrap-balance line-clamp-3">
          <Link
            href={hrefDaEntrada(entrada)}
            className="break-words hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] rounded-sm"
          >
            {entrada.titulo}
          </Link>
        </h2>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="min-w-0 break-words line-clamp-4 text-sm leading-relaxed text-[var(--cor-texto-suave)]">{entrada.resumo}</p>
        <BotaoSalvar entrada={entrada} />
      </CardContent>
    </Card>
  );
}

export function CompactNewsCard({ entrada }: { entrada: FeedEntrada }) {
  return (
    <Card className="p-4 transition-colors hover:bg-[var(--cor-primaria-suave)]/50">
      <Meta entrada={entrada} />
      <h3 className="mt-1 min-w-0 break-words font-[var(--fonte-titulo,Georgia)] text-sm font-semibold leading-snug line-clamp-2">
        <Link
          href={hrefDaEntrada(entrada)}
          className="break-words hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] rounded-sm"
        >
          {entrada.titulo}
        </Link>
      </h3>
    </Card>
  );
}

export function HorizontalNewsCard({ entrada, posicao }: { entrada: FeedEntrada; posicao?: number }) {
  return (
    <Card className="flex min-w-0 gap-4 overflow-hidden p-4">
      {typeof posicao === "number" && (
        <span
          className="shrink-0 font-[var(--fonte-titulo,Georgia)] text-3xl font-extrabold leading-none text-[var(--cor-borda)] tabular-nums"
          aria-hidden="true"
        >
          {String(posicao).padStart(2, "0")}
        </span>
      )}
      <div className="min-w-0 flex-1 overflow-hidden">
        <Meta entrada={entrada} />
        <h3 className="mt-1 min-w-0 break-words font-[var(--fonte-titulo,Georgia)] text-sm font-semibold leading-snug line-clamp-2">
          <Link
            href={hrefDaEntrada(entrada)}
            className="break-words hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] rounded-sm"
          >
            {entrada.titulo}
          </Link>
        </h3>
      </div>
    </Card>
  );
}

export { Card, CardHeader, CardFooter, CardTitle, CardDescription, CardContent };
