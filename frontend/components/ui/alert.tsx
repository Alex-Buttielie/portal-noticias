import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/utils"
const alertVariants = cva("relative w-full rounded-[var(--raio-lg)] border border-[var(--cor-borda)] p-4 [&>svg~*]:pl-7 [&>svg+div]:translate-y-[-3px] [&>svg]:absolute [&>svg]:left-4 [&>svg]:top-4 [&>svg]:text-[var(--cor-texto)]", {
  variants: { variant: { default: "bg-[var(--cor-fundo-card)] text-[var(--cor-texto)]", destructive: "border-[var(--cor-erro)]/50 text-[var(--cor-erro)] bg-[var(--cor-erro-suave)] [&>svg]:text-[var(--cor-erro)]" } },
  defaultVariants: { variant: "default" },
})
const Alert = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement> & VariantProps<typeof alertVariants>>(({ className, variant, ...props }, ref) => <div ref={ref} role="alert" className={cn(alertVariants({ variant }), className)} {...props} />)
Alert.displayName = "Alert"
const AlertTitle = React.forwardRef<HTMLParagraphElement, React.HTMLAttributes<HTMLHeadingElement>>(({ className, ...props }, ref) => <h5 ref={ref} className={cn("mb-1 font-medium leading-none tracking-tight text-[var(--cor-texto)]", className)} {...props} />)
AlertTitle.displayName = "AlertTitle"
const AlertDescription = React.forwardRef<HTMLParagraphElement, React.HTMLAttributes<HTMLParagraphElement>>(({ className, ...props }, ref) => <div ref={ref} className={cn("text-sm text-[var(--cor-texto-suave)] [&_p]:leading-relaxed", className)} {...props} />)
AlertDescription.displayName = "AlertDescription"
export { Alert, AlertTitle, AlertDescription }
