"use client";

import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const alertVariants = cva(
  "relative w-full rounded-lg border p-4 [&>svg~*]:pl-7 [&>svg+div]:translate-y-[-3px] [&>svg]:absolute [&>svg]:left-4 [&>svg]:top-4 [&>svg]:text-[var(--cor-texto-suave)]",
  {
    variants: {
      variant: {
        default: "bg-[var(--cor-fundo-elevado)] text-[var(--cor-texto)] border-[var(--cor-borda)]",
        destructive:
          "border-[var(--cor-erro)]/50 text-[var(--cor-erro)] dark:border-[var(--cor-erro)] [&>svg]:text-[var(--cor-erro)]",
        success: "border-[var(--cor-sucesso)]/50 text-[var(--cor-sucesso)] [&>svg]:text-[var(--cor-sucesso)]",
        warning: "border-[var(--cor-alerta)]/50 text-[var(--cor-alerta)] [&>svg]:text-[var(--cor-alerta)]",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
);

const Alert = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement> & VariantProps<typeof alertVariants>>(
  ({ className, variant, children, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(alertVariants({ variant }), className)}
      role="alert"
      {...props}
    >
      {children}
    </div>
  )
);
Alert.displayName = "Alert";

const AlertTitle = React.forwardRef<HTMLHeadingElement, React.HTMLAttributes<HTMLHeadingElement>>(
  ({ className, ...props }, ref) => (
    <h5 ref={ref} className={cn("mb-1 font-medium leading-none tracking-tight", className)} {...props} />
  )
);
AlertTitle.displayName = "AlertTitle";

const AlertDescription = React.forwardRef<HTMLParagraphElement, React.HTMLAttributes<HTMLParagraphElement>>(
  ({ className, ...props }, ref) => (
    <p ref={ref} className={cn("text-sm [&_p]:leading-relaxed", className)} {...props} />
  )
);
AlertDescription.displayName = "AlertDescription";

export { Alert, AlertTitle, AlertDescription };