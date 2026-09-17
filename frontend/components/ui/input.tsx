"use client"
import * as React from "react"
import { cn } from "@/lib/utils"
export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {}
const Input = React.forwardRef<HTMLInputElement, InputProps>(({ className, type, ...props }, ref) => (
  <input type={type} className={cn("flex h-10 min-h-[44px] w-full rounded-[var(--raio-md)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] px-3 py-2 text-sm text-[var(--cor-texto)] placeholder:text-[var(--cor-texto-suave)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] focus-visible:ring-offset-0 disabled:opacity-50 disabled:cursor-not-allowed touch-manipulation", className)} ref={ref} {...props} />
))
Input.displayName = "Input"
export { Input }
