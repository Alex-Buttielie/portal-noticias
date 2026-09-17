"use client"
import * as React from "react"
import { cn } from "@/lib/utils"
export interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {}
const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(({ className, ...props }, ref) => (
  <textarea className={cn("flex min-h-[80px] w-full rounded-[var(--raio-md)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] px-3 py-2 text-sm text-[var(--cor-texto)] placeholder:text-[var(--cor-texto-suave)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] disabled:opacity-50", className)} ref={ref} {...props} />
))
Textarea.displayName = "Textarea"
export { Textarea }
