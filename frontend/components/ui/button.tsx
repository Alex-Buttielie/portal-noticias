"use client"
import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-[var(--raio-md)] text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0 touch-manipulation",
  {
    variants: {
      variant: {
        default: "bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)] hover:bg-[var(--cor-primaria-hover)] shadow-[var(--sombra-1)]",
        destructive: "bg-[var(--cor-erro)] text-[var(--cor-texto-invertido)] hover:bg-[var(--cor-erro-hover)]",
        outline: "border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] text-[var(--cor-texto)] hover:bg-[var(--cor-fundo-elevado)]",
        secondary: "bg-[var(--cor-secundaria)] text-[var(--cor-texto-invertido)] hover:bg-[var(--cor-secundaria-hover)]",
        ghost: "text-[var(--cor-texto)] hover:bg-[var(--cor-borda)] hover:text-[var(--cor-texto)]",
        link: "text-[var(--cor-primaria)] underline-offset-4 hover:underline",
      },
      size: {
        default: "h-10 min-h-[44px] px-4 py-2",
        sm: "h-9 min-h-[36px] rounded-[var(--raio-sm)] px-3",
        lg: "h-11 min-h-[44px] rounded-[var(--raio-md)] px-8",
        icon: "h-10 w-10 min-h-[44px] min-w-[44px]",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  }
)

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof buttonVariants> { asChild?: boolean }

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(({ className, variant, size, asChild = false, ...props }, ref) => {
  const Comp = asChild ? Slot : "button"
  return <Comp className={cn(buttonVariants({ variant, size, className }))} ref={ref} {...props} />
})
Button.displayName = "Button"
export { Button, buttonVariants }
