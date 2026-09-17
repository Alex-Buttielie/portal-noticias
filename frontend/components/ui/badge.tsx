import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/utils"
const badgeVariants = cva("inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-[var(--cor-foco)]", {
  variants: {
    variant: {
      default: "border-transparent bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]",
      secondary: "border-transparent bg-[var(--cor-secundaria-suave)] text-[var(--cor-texto)]",
      destructive: "border-transparent bg-[var(--cor-erro)] text-[var(--cor-texto-invertido)]",
      outline: "border-[var(--cor-borda)] text-[var(--cor-texto)]",
    },
  },
  defaultVariants: { variant: "default" },
})
export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement>, VariantProps<typeof badgeVariants> {}
function Badge({ className, variant, ...props }: BadgeProps) { return <div className={cn(badgeVariants({ variant }), className)} {...props} /> }
export { Badge, badgeVariants }
