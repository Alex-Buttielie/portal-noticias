"use client";

// Grade que ajusta colunas/densidade por dispositivo sem que cada página
// precise repetir breakpoints. Usa o perfil do DeviceProvider + CSS grid.

import type { CSSProperties, ReactNode } from "react";
import { useDispositivo } from "@/lib/dispositivos/DeviceProvider";
import { cn } from "@/lib/utils";

export type Densidade = "confortavel" | "compacta";

export function useColunasAdaptativas(opcoes?: {
  mobile?: number;
  tablet?: number;
  desktop?: number;
}): number {
  const { mobile = 1, tablet = 2, desktop = 3 } = opcoes ?? {};
  const { classe } = useDispositivo();
  if (classe === "mobile") return mobile;
  if (classe === "tablet") return tablet;
  return desktop;
}

export function GradeAdaptativa({
  children,
  mobile = 1,
  tablet = 2,
  desktop = 3,
  densidade,
  className,
  style,
}: {
  children: ReactNode;
  mobile?: number;
  tablet?: number;
  desktop?: number;
  /** "compacta" força respiro menor no mobile (listas densas de notícias). */
  densidade?: Densidade;
  className?: string;
  style?: CSSProperties;
}) {
  const { classe } = useDispositivo();
  const colunas = classe === "mobile" ? mobile : classe === "tablet" ? tablet : desktop;
  const compacta = densidade === "compacta" || (densidade === undefined && classe === "mobile");

  return (
    <div
      data-grade-adaptativa
      data-colunas={colunas}
      className={cn("grid w-full", compacta ? "gap-2.5" : "gap-4 md:gap-5", className)}
      style={{
        gridTemplateColumns: `repeat(${colunas}, minmax(0, 1fr))`,
        ...style,
      }}
    >
      {children}
    </div>
  );
}

/** Container de leitura com largura máxima por dispositivo. */
export function ConteudoAdaptativo({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      data-conteudo-adaptativo
      className={cn("mx-auto w-full max-w-full px-0 sm:px-1 md:max-w-[820px] lg:max-w-[960px]", className)}
    >
      {children}
    </div>
  );
}
