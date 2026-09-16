import * as React from "react";
import { cn } from "@/lib/utils";

function Skeleton({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("animate-pulse rounded-md bg-[var(--cor-skeleton-base)] motion-reduce:animate-none", className)} {...props} />;
}

export default function CartaoEsqueleto() {
  return (
    <div
      className={cn("rounded-xl border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] p-4 shadow-sm")}
      aria-hidden="true"
    >
      <Skeleton className="h-40 w-full rounded-lg cartao-noticia cartao-noticia--esqueleto esqueleto-cartao cartao-noticia__imagem cartao-noticia__corpo esqueleto--linha-curta" />
      <div className="mt-4 space-y-2">
        <Skeleton className="h-3 w-1/3" />
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-5/6" />
        <Skeleton className="h-4 w-3/5" />
      </div>
    </div>
  );
}
