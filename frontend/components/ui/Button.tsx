import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex min-h-[44px] touch-manipulation items-center justify-center gap-2 rounded-md text-sm font-semibold transition-colors motion-reduce:transition-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variante: {
        primaria:
          "bg-[var(--cor-primaria)] text-white hover:bg-[var(--cor-primaria-hover)] shadow-sm",
        secundaria:
          "border border-[var(--cor-primaria)] bg-transparent text-[var(--cor-primaria)] hover:bg-[var(--cor-primaria-suave)]",
        fantasma:
          "bg-transparent text-[var(--cor-texto)] hover:bg-[var(--cor-primaria-suave)]",
        perigo:
          "bg-[var(--cor-erro)] text-white hover:bg-[var(--cor-destaque-hover)] shadow-sm",
      },
      tamanho: {
        pequeno: "h-8 px-3 text-xs rounded-full",
        medio: "h-10 px-4 py-2",
        grande: "h-11 px-8 text-base",
      },
    },
    defaultVariants: {
      variante: "primaria",
      tamanho: "medio",
    },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
  carregando?: boolean;
  // compatibilidade com uso legado em inglês (shadcn default) — mapeado para variante/tamanho
  variant?: VariantProps<typeof buttonVariants>["variante"] | string;
  size?: VariantProps<typeof buttonVariants>["tamanho"] | string;
}

const variantMap: Record<string, NonNullable<VariantProps<typeof buttonVariants>["variante"]>> = {
  default: "primaria",
  primaria: "primaria",
  primary: "primaria",
  secundaria: "secundaria",
  secondary: "secundaria",
  ghost: "fantasma",
  fantasma: "fantasma",
  destructive: "perigo",
  perigo: "perigo",
};

const sizeMap: Record<string, NonNullable<VariantProps<typeof buttonVariants>["tamanho"]>> = {
  sm: "pequeno",
  pequeno: "pequeno",
  default: "medio",
  medio: "medio",
  lg: "grande",
  grande: "grande",
  icon: "pequeno",
};

function normalizeVariante(v?: string | null): VariantProps<typeof buttonVariants>["variante"] | undefined {
  if (!v) return undefined;
  return (variantMap[v] as VariantProps<typeof buttonVariants>["variante"]) ?? (v as VariantProps<typeof buttonVariants>["variante"]);
}
function normalizeTamanho(v?: string | null): VariantProps<typeof buttonVariants>["tamanho"] | undefined {
  if (!v) return undefined;
  return (sizeMap[v] as VariantProps<typeof buttonVariants>["tamanho"]) ?? (v as VariantProps<typeof buttonVariants>["tamanho"]);
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variante, tamanho, variant, size, asChild = false, carregando = false, disabled, children, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    const isDisabled = disabled ?? carregando;
    const varianteFinal = normalizeVariante((variante as string) ?? (variant as string)) ?? "primaria";
    const tamanhoFinal = normalizeTamanho((tamanho as string) ?? (size as string)) ?? "medio";
    // remover props legadas para não vazar ao DOM
    const { variant: _v, size: _s, ...rest } = props as Record<string, unknown>;
    void _v;
    void _s;
    return (
      <Comp
        className={cn(buttonVariants({ variante: varianteFinal, tamanho: tamanhoFinal, className }))}
        ref={ref}
        disabled={isDisabled}
        aria-busy={carregando || undefined}
        {...(rest as React.ButtonHTMLAttributes<HTMLButtonElement>)}
      >
        {carregando && <Loader2 className="animate-spin motion-reduce:animate-none spinner" aria-hidden="true" />}
        {carregando ? "Carregando…" : children}
      </Comp>
    );
  }
);
Button.displayName = "Button";

export { Button, buttonVariants };
