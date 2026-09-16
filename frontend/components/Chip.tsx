"use client";

import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

const chipVariants = cva(
  "inline-flex min-h-[44px] touch-manipulation items-center gap-1.5 break-words rounded-full border px-3 py-1 text-sm font-medium transition-colors motion-reduce:transition-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] focus-visible:ring-offset-2",
  {
    variants: {
      selecionado: {
        true: "border-[var(--cor-primaria)] bg-[var(--cor-primaria-suave)] text-[var(--cor-primaria)]",
        false: "border-[var(--cor-borda)] bg-white text-[var(--cor-texto)] hover:border-[var(--cor-primaria)]",
      },
    },
    defaultVariants: {
      selecionado: false,
    },
  }
);

export default function Chip({
  children,
  selecionado = false,
  disabled = false,
  aoClicar,
  aoRemover,
  removerRotulo,
  className,
}: {
  children: React.ReactNode;
  selecionado?: boolean;
  disabled?: boolean;
  aoClicar?: () => void;
  aoRemover?: () => void;
  removerRotulo?: string;
  className?: string;
} & VariantProps<typeof chipVariants>) {
  return (
    <span className={cn(chipVariants({ selecionado }), disabled && "opacity-50 pointer-events-none", className)}>
      {aoClicar ? (
        <button
          type="button"
          aria-pressed={selecionado}
          disabled={disabled}
          onClick={aoClicar}
          className="inline-flex min-h-[44px] touch-manipulation items-center bg-transparent p-0 font-inherit text-inherit focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] motion-reduce:transition-none"
        >
          {children}
        </button>
      ) : (
        <span className="break-words">{children}</span>
      )}
      {aoRemover && (
        <button
          type="button"
          className={cn(
            "inline-flex min-h-[44px] min-w-[44px] touch-manipulation items-center justify-center rounded-full hover:bg-black/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] motion-reduce:transition-none"
          )}
          aria-label={removerRotulo || "Remover"}
          disabled={disabled}
          onClick={aoRemover}
        >
          <X className="h-3 w-3" aria-hidden="true" />
        </button>
      )}
    </span>
  );
}

export { chipVariants };
