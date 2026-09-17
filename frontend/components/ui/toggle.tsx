"use client"
import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/utils"
const toggleVariants = cva("inline-flex items-center justify-center rounded-[var(--raio-md)] text-sm font-medium transition-colors hover:bg-[var(--cor-borda)] hover:text-[var(--cor-texto)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] disabled:opacity-50 data-[state=on]:bg-[var(--cor-borda)] data-[state=on]:text-[var(--cor-texto)]", {
  variants: { variant: { default: "bg-transparent", outline: "border border-[var(--cor-borda)] bg-transparent hover:bg-[var(--cor-borda)]" }, size: { default: "h-10 min-h-[44px] px-3", sm: "h-9 px-2.5", lg: "h-11 px-5" } },
  defaultVariants: { variant: "default", size: "default" },
})
export interface ToggleProps extends React.ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof toggleVariants> { pressed?: boolean; onPressedChange?: (pressed: boolean) => void }
const Toggle = React.forwardRef<HTMLButtonElement, ToggleProps>(({ className, variant, size, pressed, onPressedChange, onClick, ...props }, ref) => {
  const [on, setOn] = React.useState(pressed ?? false)
  const isPressed = pressed ?? on
  return <button ref={ref} type="button" aria-pressed={isPressed} data-state={isPressed ? "on" : "off"} className={cn(toggleVariants({ variant, size, className }))} onClick={(e) => { if (pressed === undefined) setOn(!on); onPressedChange?.(!isPressed); onClick?.(e) }} {...props} />
})
Toggle.displayName = "Toggle"
export { Toggle, toggleVariants }
