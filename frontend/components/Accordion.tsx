"use client";

import * as React from "react";
import * as AccordionPrimitive from "@radix-ui/react-accordion";
import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";

export interface ItemAccordion {
  chave: string;
  titulo: React.ReactNode;
  conteudo: React.ReactNode;
  disabled?: boolean;
}

const AccordionItem = React.forwardRef<
  React.ElementRef<typeof AccordionPrimitive.Item>,
  React.ComponentPropsWithoutRef<typeof AccordionPrimitive.Item>
>(({ className, ...props }, ref) => (
  <AccordionPrimitive.Item ref={ref} className={cn("border-b border-[var(--cor-borda)]", className)} {...props} />
));
AccordionItem.displayName = "AccordionItem";

const AccordionTrigger = React.forwardRef<
  React.ElementRef<typeof AccordionPrimitive.Trigger>,
  React.ComponentPropsWithoutRef<typeof AccordionPrimitive.Trigger>
>(({ className, children, ...props }, ref) => (
  <AccordionPrimitive.Header className="flex min-w-0">
    <AccordionPrimitive.Trigger
      ref={ref}
      className={cn(
        "flex min-h-[44px] flex-1 touch-manipulation items-center justify-between gap-2 break-words py-4 text-left text-sm font-medium transition-colors hover:text-[var(--cor-primaria)]",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] focus-visible:ring-offset-2",
        "motion-reduce:transition-none [&[data-state=open]>svg]:rotate-180",
        className
      )}
      {...props}
    >
      <span className="min-w-0 flex-1 break-words">{children}</span>
      <ChevronDown className="h-4 w-4 shrink-0 transition-transform duration-200 motion-reduce:transition-none" />
    </AccordionPrimitive.Trigger>
  </AccordionPrimitive.Header>
));
AccordionTrigger.displayName = AccordionPrimitive.Trigger.displayName;

const AccordionContent = React.forwardRef<
  React.ElementRef<typeof AccordionPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof AccordionPrimitive.Content>
>(({ className, children, ...props }, ref) => (
  <AccordionPrimitive.Content
    ref={ref}
    className={cn(
      "overflow-hidden break-words text-sm data-[state=closed]:animate-accordion-up data-[state=open]:animate-accordion-down motion-reduce:animate-none [overscroll-behavior:contain]",
      className
    )}
    {...props}
  >
    <div className="min-w-0 break-words pb-4 pt-0 text-[var(--cor-texto-suave)]">{children}</div>
  </AccordionPrimitive.Content>
));
AccordionContent.displayName = AccordionPrimitive.Content.displayName;

export default function Accordion({
  itens,
  permitirMultiplos = false,
  itemInicialAberto,
}: {
  itens: ItemAccordion[];
  permitirMultiplos?: boolean;
  itemInicialAberto?: string;
}) {
  if (permitirMultiplos) {
    return (
      <AccordionPrimitive.Root
        type="multiple"
        defaultValue={itemInicialAberto ? [itemInicialAberto] : undefined}
        className="w-full"
      >
        {itens.map((item) => (
          <AccordionItem key={item.chave} value={item.chave} className={cn(item.disabled && "opacity-50")}>
            <AccordionTrigger disabled={item.disabled}>{item.titulo}</AccordionTrigger>
            <AccordionContent>{item.conteudo}</AccordionContent>
          </AccordionItem>
        ))}
      </AccordionPrimitive.Root>
    );
  }
  return (
    <AccordionPrimitive.Root
      type="single"
      collapsible
      defaultValue={itemInicialAberto}
      className="w-full rounded-lg border border-[var(--cor-borda)] bg-white px-4"
    >
      {itens.map((item) => (
        <AccordionItem key={item.chave} value={item.chave}>
          <AccordionTrigger disabled={item.disabled}>{item.titulo}</AccordionTrigger>
          <AccordionContent>{item.conteudo}</AccordionContent>
        </AccordionItem>
      ))}
    </AccordionPrimitive.Root>
  );
}

export { AccordionItem, AccordionTrigger, AccordionContent };
