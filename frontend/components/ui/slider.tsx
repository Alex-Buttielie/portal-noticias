"use client"
import * as React from "react"
import { cn } from "@/lib/utils"
export interface SliderProps extends React.InputHTMLAttributes<HTMLInputElement> {}
const Slider = React.forwardRef<HTMLInputElement, SliderProps>(({ className, ...props }, ref) => (
  <input type="range" ref={ref} className={cn("w-full h-2 accent-[var(--cor-primaria)] cursor-pointer touch-manipulation", className)} {...props} />
))
Slider.displayName = "Slider"
export { Slider }
