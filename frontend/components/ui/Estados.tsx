import * as React from "react";
import { Loader2, AlertTriangle, Inbox } from "lucide-react";
import { cn } from "@/lib/utils";

// Skeleton shadcn primitive
function Skeleton({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("animate-pulse rounded-md bg-[var(--cor-skeleton-base)] motion-reduce:animate-none", className)}
      {...props}
    />
  );
}

export function LoadingSpinner({ rotulo = "Carregando…" }: { rotulo?: string }) {
  return (
<div
      className="carregando flex items-center justify-center gap-2 py-8 text-sm text-[var(--cor-texto-suave)]"
      role="status"
      aria-live="polite"
      aria-busy="true"
    >
      <Loader2 className="spinner h-5 w-5 animate-spin text-[var(--cor-primaria)] motion-reduce:animate-none" aria-hidden="true" />
      <span>{rotulo}</span>
    </div>
  );
}

export function SkeletonCard() {
  return (
    <div
      className={cn(
        "rounded-xl border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] p-4 shadow-sm",
        "animate-pulse motion-reduce:animate-none"
      )}
      aria-hidden="true"
    >
      <Skeleton className="h-40 w-full rounded-lg" />
      <div className="mt-4 space-y-2">
        <Skeleton className="h-3 w-1/3" />
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-5/6" />
      </div>
    </div>
  );
}

export function SkeletonLista({ quantidade = 3 }: { quantidade?: number }) {
  return (
<div role="status" aria-live="polite" aria-label="Carregando conteúdo…" className="grid gap-4">
      {Array.from({ length: quantidade }, (_, i) => (
        <SkeletonCard key={i} />
      ))}
    </div>
  );
}

export function EmptyState({ titulo, descricao }: { titulo: string; descricao?: string }) {
  return (
    <div
      className={cn(
        "rounded-xl border border-dashed border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] p-8 text-center",
        "flex flex-col items-center gap-2"
      )}
    >
      <div className="rounded-full bg-[var(--cor-primaria-suave)] p-3">
        <Inbox className="h-6 w-6 text-[var(--cor-primaria)]" aria-hidden="true" />
      </div>
      <p className="font-semibold text-[var(--cor-texto)]">{titulo}</p>
      {descricao && <p className="max-w-prose text-sm text-[var(--cor-texto-suave)]">{descricao}</p>}
    </div>
  );
}

export function ErrorState({ mensagem, aoTentarNovamente }: { mensagem: string; aoTentarNovamente?: () => void }) {
  return (
    <div
      className={cn(
        "rounded-xl border border-[var(--cor-erro)]/20 bg-[var(--cor-erro)]/5 p-6 text-center",
        "flex flex-col items-center gap-3"
      )}
      role="alert"
    >
      <div className="rounded-full bg-[var(--cor-erro)]/10 p-3">
        <AlertTriangle className="h-6 w-6 text-[var(--cor-erro)]" aria-hidden="true" />
      </div>
      <p className="font-semibold text-[var(--cor-texto)]">Algo não saiu como esperado</p>
      <p className="max-w-prose text-sm text-[var(--cor-texto-suave)]">{mensagem}</p>
      {aoTentarNovamente && (
        <button
          type="button"
          onClick={aoTentarNovamente}
          className={cn(
            "inline-flex min-h-[44px] touch-manipulation items-center justify-center rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] px-4 text-sm font-medium",
            "hover:bg-[var(--cor-primaria-suave)] hover:text-[var(--cor-primaria)]",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] focus-visible:ring-offset-2",
            "motion-reduce:transition-none transition-colors"
          )}
        >
          Tentar novamente
        </button>
      )}
    </div>
  );
}

export { Skeleton };
