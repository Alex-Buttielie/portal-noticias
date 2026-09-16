import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex touch-manipulation items-center break-words rounded-full border px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wide transition-colors motion-reduce:transition-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] focus-visible:ring-offset-2",
  {
    variants: {
      variante: {
        padrao: "border-transparent bg-[var(--cor-primaria)] text-white",
        sucesso: "border-transparent bg-[var(--cor-sucesso)] text-white",
        erro: "border-transparent bg-[var(--cor-erro)] text-white",
        neutro: "border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] text-[var(--cor-texto-suave)]",
        premium: "border-transparent bg-[var(--cor-premium)] text-white",
      },
    },
    defaultVariants: {
      variante: "padrao",
    },
  }
);

export type VarianteBadge = "padrao" | "sucesso" | "erro" | "neutro" | "premium";

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {
  variante?: VarianteBadge;
}

export default function Badge({ className, variante = "padrao", ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variante }), className)} {...props} />;
}

export { badgeVariants };
