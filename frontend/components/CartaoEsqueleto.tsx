import * as React from "react";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

export function CartaoEsqueleto({ variant = "default" }: { variant?: "default" | "horizontal" | "compact" }) {
  if (variant === "horizontal") {
    return (
      <div
        className={cn("flex min-w-0 gap-4 overflow-hidden rounded-xl border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-4")}
        aria-hidden="true"
      >
        <div className="min-w-0 flex-1 space-y-3">
          <Skeleton className="h-3 w-1/4" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-5/6" />
        </div>
      </div>
    );
  }

  if (variant === "compact") {
    return (
      <div
        className={cn("rounded-xl border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-4")}
        aria-hidden="true"
      >
        <Skeleton className="h-4 w-1/3" />
        <Skeleton className="mt-2 h-5 w-full" />
      </div>
    );
  }

  return (
    <div
      className={cn("rounded-xl border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-4 shadow-sm")}
      aria-hidden="true"
    >
      <Skeleton className="h-40 w-full rounded-lg" />
      <div className="mt-4 space-y-2">
        <Skeleton className="h-3 w-1/3" />
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-5/6" />
        <Skeleton className="h-4 w-3/5" />
      </div>
    </div>
  );
}

export function SkeletonLista({ quantidade = 6 }: { quantidade?: number }) {
  return (
    <div
      role="status"
      aria-live="polite"
      aria-label="Carregando conteúdo…"
      className="grid w-full grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3"
    >
      {Array.from({ length: quantidade }).map((_, i) => (
        <CartaoEsqueleto key={i} />
      ))}
    </div>
  );
}
