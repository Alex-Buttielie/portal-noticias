"use client"
import * as React from "react"
import * as HoverCardPrimitive from "@radix-ui/react-hover-card"
import { cn } from "@/lib/utils"
const HoverCard = HoverCardPrimitive.Root
const HoverCardTrigger = HoverCardPrimitive.Trigger
const HoverCardContent = React.forwardRef<React.ElementRef<typeof HoverCardPrimitive.Content>, React.ComponentPropsWithoutRef<typeof HoverCardPrimitive.Content>>(({ className, align = "center", sideOffset = 4, ...props }, ref) => (
  <HoverCardPrimitive.Content ref={ref} align={align} sideOffset={sideOffset} className={cn("z-[var(--z-painel-flutuante)] w-64 rounded-[var(--raio-md)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] p-4 shadow-[var(--sombra-2)] outline-none data-[state=open]:animate-in", className)} {...props} />
))
HoverCardContent.displayName = HoverCardPrimitive.Content.displayName
export { HoverCard, HoverCardTrigger, HoverCardContent }
