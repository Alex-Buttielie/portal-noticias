"use client"
import * as React from "react"
import { cn } from "@/lib/utils"
import { toggleVariants } from "@/components/ui/toggle"
const ToggleGroupContext = React.createContext<{ variant?: string; size?: string }>({})
export interface ToggleGroupProps extends React.HTMLAttributes<HTMLDivElement> { type?: "single" | "multiple"; variant?: "default" | "outline"; size?: "default" | "sm" | "lg"; value?: string; onValueChange?: (v: string) => void }
const ToggleGroup = React.forwardRef<HTMLDivElement, ToggleGroupProps>(({ className, variant, size, children, ...props }, ref) => (
  <ToggleGroupContext.Provider value={{ variant, size }}><div ref={ref} className={cn("flex items-center justify-center gap-1", className)} {...props}>{children}</div></ToggleGroupContext.Provider>
))
ToggleGroup.displayName = "ToggleGroup"
export interface ToggleGroupItemProps extends React.ButtonHTMLAttributes<HTMLButtonElement> { value: string; variant?: "default" | "outline"; size?: "default" | "sm" | "lg" }
const ToggleGroupItem = React.forwardRef<HTMLButtonElement, ToggleGroupItemProps>(({ className, children, variant, size, ...props }, ref) => {
  const ctx = React.useContext(ToggleGroupContext)
  return <button ref={ref} className={cn(toggleVariants({ variant: ctx.variant as any || variant, size: ctx.size as any || size }), className)} {...props}>{children}</button>
})
ToggleGroupItem.displayName = "ToggleGroupItem"
export { ToggleGroup, ToggleGroupItem }
