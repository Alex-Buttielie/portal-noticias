"use client";

import * as React from "react";
import * as TooltipPrimitive from "@radix-ui/react-tooltip";
import { cn } from "@/lib/utils";

const TooltipProvider = TooltipPrimitive.Provider;
const TooltipRoot = TooltipPrimitive.Root;
const TooltipTrigger = TooltipPrimitive.Trigger;

const TooltipContent = React.forwardRef<
  React.ElementRef<typeof TooltipPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof TooltipPrimitive.Content>
>(({ className, sideOffset = 4, ...props }, ref) => (
  <TooltipPrimitive.Content
    ref={ref}
    sideOffset={sideOffset}
    className={cn(
      "z-50 overflow-hidden break-words rounded-md bg-[var(--cor-texto)] px-3 py-1.5 text-xs font-medium text-[var(--cor-fundo)] shadow-md [overscroll-behavior:contain]",
      "animate-in fade-in-0 zoom-in-95 data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95 data-[side=bottom]:slide-in-from-top-2 data-[side=top]:slide-in-from-bottom-2",
      "motion-reduce:animate-none max-w-[240px] text-wrap-balance",
      className
    )}
    {...props}
  />
));
TooltipContent.displayName = TooltipPrimitive.Content.displayName;

export default function Tooltip({
  texto,
  children,
  posicao = "cima",
}: {
  texto: string;
  children: React.ReactNode;
  posicao?: "cima" | "baixo";
}) {
  return (
    <TooltipProvider>
      <TooltipRoot>
        <TooltipTrigger asChild>
          <span className={cn("inline-flex min-h-[44px] touch-manipulation items-center")}>{children}</span>
        </TooltipTrigger>
        <TooltipContent side={posicao === "baixo" ? "bottom" : "top"}>{texto}</TooltipContent>
      </TooltipRoot>
    </TooltipProvider>
  );
}

export { TooltipProvider, TooltipRoot, TooltipTrigger, TooltipContent };
