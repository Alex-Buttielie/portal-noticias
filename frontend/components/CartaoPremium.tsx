"use client";

import Link from "next/link";
import { Crown } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useQueryPlanos } from "@/lib/queries";
import { planoPagoMaisBarato } from "@/lib/planos";
import { ALTURA_FORMATO, type FormatoAnuncio } from "@/lib/anuncios";

/**
 * M-09 (run 20261012-1806-monetizacao-sprint1) — substituto do espaço de
 * anúncio quando não há anúncio para mostrar (sem consentimento, ou sem
 * publisher ID — ver `AdsSlot.tsx`). Vira oportunidade de conversão em vez
 * de um buraco vazio: mostra o preço real do plano pago mais barato ativo
 * (nunca um número inventado) e leva para `/planos`. Nunca usa as palavras
 * "publicidade"/"AdSense" (critério de aceite 9 do implementation-contract.md).
 */
export function CartaoPremium({ formato, className }: { formato: FormatoAnuncio; className?: string }) {
  const planosQuery = useQueryPlanos();
  const planos = planosQuery.data?.filter((p) => p.ativo !== false) ?? [];
  const maisBarato = planoPagoMaisBarato(planos);

  return (
    <div
      role="complementary"
      aria-label="Assine o Premium e leia sem anúncios"
      className={cn(
        "flex flex-col items-center justify-center gap-1.5 overflow-hidden rounded-[var(--raio-lg)] border border-[var(--cor-premium)] bg-[var(--cor-premium-suave)] p-4 text-center",
        className
      )}
      style={{ minHeight: ALTURA_FORMATO[formato] }}
    >
      <span className="flex h-8 w-8 items-center justify-center rounded-full bg-[var(--cor-premium)] text-[var(--cor-texto-invertido)]">
        <Crown className="h-4 w-4" />
      </span>
      <p className="max-w-[28ch] text-balance text-sm font-medium leading-tight text-[var(--cor-texto)]">
        Leia sem interrupções com o Premium
      </p>
      {maisBarato && (
        <p className="text-xs text-[var(--cor-texto-suave)]">
          a partir de R$ {maisBarato.preco} / {maisBarato.duracao_dias} dias
        </p>
      )}
      <Button asChild size="sm" className="min-h-[44px] bg-[var(--cor-premium)] text-[var(--cor-texto-invertido)] hover:bg-[var(--cor-premium-hover)]">
        <Link href="/planos" aria-label="Ver planos Premium">Ver planos</Link>
      </Button>
    </div>
  );
}
