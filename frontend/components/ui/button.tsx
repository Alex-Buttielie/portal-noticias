"use client";

import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 motion-reduce:transition-none touch-manipulation min-h-[44px]",
  {
    variants: {
      variant: {
        default:
          "bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)] hover:bg-[var(--cor-primaria-hover)] shadow-sm",
        destructive:
          "bg-[var(--cor-erro)] text-[var(--cor-texto-invertido)] hover:opacity-90 shadow-sm",
        outline:
          "border border-[var(--cor-borda)] bg-transparent hover:bg-[var(--cor-primaria-suave)] hover:text-[var(--cor-primaria)]",
        secondary:
          "bg-[var(--cor-fundo-elevado)] text-[var(--cor-texto)] hover:bg-[var(--cor-borda)]",
        ghost:
          "hover:bg-[var(--cor-primaria-suave)] hover:text-[var(--cor-primaria)]",
        link: "text-[var(--cor-primaria)] underline-offset-4 hover:underline",
        premium:
          "bg-[var(--gradiente-marca)] text-[var(--cor-texto-invertido)] hover:opacity-90 shadow-sm",
      },
      size: {
        default: "h-10 px-4 py-2",
        sm: "h-9 rounded-md px-3",
        lg: "h-11 rounded-md px-8",
        xl: "h-12 rounded-lg px-10 text-base",
        icon: "h-10 w-10",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
);

type Variant = VariantProps<typeof buttonVariants>["variant"];
type Size = VariantProps<typeof buttonVariants>["size"];

const variantMap: Record<string, Variant> = {
  default: "default",
  primaria: "default",
  secundaria: "secondary",
  secondary: "secondary",
  destrutivo: "destructive",
  destructive: "destructive",
  perigo: "destructive",
  outline: "outline",
  fantasma: "ghost",
  ghost: "ghost",
  link: "link",
  premium: "premium",
};

const sizeMap: Record<string, Size> = {
  default: "default",
  padrao: "default",
  sm: "sm",
  pequeno: "sm",
  medio: "default",
  lg: "lg",
  grande: "lg",
  xl: "xl",
  icone: "icon",
  icon: "icon",
};

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
  loading?: boolean;
  carregando?: boolean;
  variante?: string;
  tamanho?: string;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, loading, carregando, variante, tamanho, disabled, children, ...props }, ref) => {
    const resolvedVariant = (variante ?? variant ?? "default") as string;
    const resolvedSize = (tamanho ?? size ?? "default") as string;
    const buttonVariant = variantMap[resolvedVariant] ?? variant ?? "default";
    const buttonSize = sizeMap[resolvedSize] ?? size ?? "default";
    const resolvedLoading = loading ?? carregando;
    // asChild (Radix Slot) exige exatamente UM elemento filho — o spinner
    // condicional injetaria um segundo filho (false) e quebra o prerender
    // ("Slot failed to slot onto its children"). Com asChild, repassa
    // somente children; o estado de loading vai via aria-busy/aria-disabled.
    // LIMITAÇÃO: `disabled` nativo e bloqueio de navegação NÃO se aplicam ao
    // filho (ex.: <Link> continua navegável) — o chamador deve evitar
    // asChild+loading em ações destrutivas/assíncronas ou bloquear no filho.
    if (asChild) {
      return (
        <Slot
          className={cn(buttonVariants({ variant: buttonVariant, size: buttonSize, className }))}
          ref={ref}
          aria-busy={resolvedLoading}
          aria-disabled={disabled || resolvedLoading || undefined}
          {...props}
        >
          {children}
        </Slot>
      );
    }
    return (
      <button
        className={cn(buttonVariants({ variant: buttonVariant, size: buttonSize, className }))}
        ref={ref}
        disabled={disabled || resolvedLoading}
        aria-busy={resolvedLoading}
        {...props}
      >
        {resolvedLoading && (
          <svg
            className="mr-2 h-4 w-4 animate-spin motion-reduce:animate-none"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
            />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
            />
          </svg>
        )}
        {children}
      </button>
    );
  }
);
Button.displayName = "Button";

export { Button, buttonVariants };
