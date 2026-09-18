"use client";

import { useEffect, useRef } from "react";
import { cn } from "@/lib/utils";
import { ADSENSE_CLIENT_ID } from "./AdsScript";

type Formato = "horizontal" | "retangulo" | "vertical" | "in-feed";

const ALTURA: Record<Formato, string> = {
  horizontal: "90px",
  retangulo: "250px",
  vertical: "600px",
  "in-feed": "200px",
};

/** Slot numérico por formato (criado na conta AdSense). Sem slot, o bloco
 *  segue como placeholder mesmo com publisher ID configurado. */
const SLOT_POR_FORMATO: Record<Formato, string> = {
  horizontal: process.env.NEXT_PUBLIC_ADSENSE_SLOT_HORIZONTAL || "",
  retangulo: process.env.NEXT_PUBLIC_ADSENSE_SLOT_RETANGULO || "",
  vertical: process.env.NEXT_PUBLIC_ADSENSE_SLOT_VERTICAL || "",
  "in-feed": process.env.NEXT_PUBLIC_ADSENSE_SLOT_INFEED || "",
};

declare global {
  interface Window {
    adsbygoogle?: unknown[];
  }
}

export function AdsSlot({
  id,
  formato,
  className,
  rotulo,
}: {
  id: string;
  formato: Formato;
  className?: string;
  rotulo?: string;
}) {
  const ref = useRef<HTMLModElement>(null);
  const slot = SLOT_POR_FORMATO[formato];

  useEffect(() => {
    if (!ADSENSE_CLIENT_ID || !slot || !ref.current) return;
    try {
      (window.adsbygoogle = window.adsbygoogle || []).push({});
    } catch {
      /* AdSense indisponível (adblock/offline) — mantém o espaço reservado */
    }
  }, [slot]);

  if (ADSENSE_CLIENT_ID && slot) {
    return (
      <div
        role="complementary"
        aria-label={`Publicidade ${id}`}
        className={cn("overflow-hidden", className)}
        style={{ minHeight: ALTURA[formato] }}
      >
        <ins
          ref={ref}
          className="adsbygoogle"
          style={{ display: "block" }}
          data-ad-client={ADSENSE_CLIENT_ID}
          data-ad-slot={slot}
          data-ad-format="auto"
          data-full-width-responsive="true"
        />
      </div>
    );
  }

  return (
    <div
      role="complementary"
      aria-label={`Publicidade ${id}`}
      className={cn(
        "relative flex flex-col items-center justify-center overflow-hidden rounded-[var(--raio-lg)] border border-dashed bg-[var(--cor-fundo-elevado)] p-4 text-center",
        className
      )}
      style={{ minHeight: ALTURA[formato], borderColor: "var(--cor-borda)" }}
    >
      <div className="hud-grid absolute inset-0 opacity-[0.12]" aria-hidden />
      <div className="relative flex flex-col items-center gap-1">
        <span className="text-[10px] font-medium tracking-[0.14em] text-[var(--cor-texto-suave)]">
          PUBLICIDADE{rotulo ? ` • ${rotulo.toUpperCase()}` : ""}
        </span>
        <span className="max-w-[28ch] text-balance text-sm font-medium leading-tight text-[var(--cor-texto-suave)]">
          Anúncio — Google AdSense (slot {id})
        </span>
        <span className="rounded-full border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] px-2.5 py-0.5 text-[10px] tracking-wide text-[var(--cor-texto-suave)]">
          Conteúdo publicitário
        </span>
      </div>
    </div>
  );
}
