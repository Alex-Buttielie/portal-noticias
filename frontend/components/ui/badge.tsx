"use client";

import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] focus-visible:ring-offset-2 motion-reduce:transition-none touch-manipulation min-h-[44px]",
  {
    variants: {
      variant: {
        default:
          "border-transparent bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)] hover:bg-[var(--cor-primaria-hover)]",
        secondary:
          "border-transparent bg-[var(--cor-fundo-elevado)] text-[var(--cor-texto)] hover:bg-[var(--cor-borda)]",
        destructive:
          "border-transparent bg-[var(--cor-erro)] text-[var(--cor-texto-invertido)] hover:opacity-90",
        outline: "border-[var(--cor-borda)] text-[var(--cor-texto)]",
        success:
          "border-transparent bg-[var(--cor-sucesso)] text-[var(--cor-texto-invertido)] hover:opacity-90",
        warning:
          "border-transparent bg-[var(--cor-alerta)] text-[var(--cor-texto-invertido)] hover:opacity-90",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export { Badge, badgeVariants };