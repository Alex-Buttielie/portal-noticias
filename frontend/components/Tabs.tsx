"use client";

import * as React from "react";
import * as TabsPrimitive from "@radix-ui/react-tabs";
import { cn } from "@/lib/utils";

const Tabs = TabsPrimitive.Root;

const TabsList = React.forwardRef<
  React.ElementRef<typeof TabsPrimitive.List>,
  React.ComponentPropsWithoutRef<typeof TabsPrimitive.List>
>(({ className, ...props }, ref) => (
  <TabsPrimitive.List
    ref={ref}
    className={cn(
      "inline-flex min-h-[44px] w-full min-w-0 touch-manipulation items-center justify-start gap-1 overflow-x-auto rounded-lg bg-[var(--cor-primaria-suave)] p-1 text-[var(--cor-texto-suave)] [overscroll-behavior:contain]",
      className
    )}
    {...props}
  />
));
TabsList.displayName = TabsPrimitive.List.displayName;

const TabsTrigger = React.forwardRef<
  React.ElementRef<typeof TabsPrimitive.Trigger>,
  React.ComponentPropsWithoutRef<typeof TabsPrimitive.Trigger>
>(({ className, ...props }, ref) => (
  <TabsPrimitive.Trigger
    ref={ref}
    className={cn(
      "inline-flex min-h-[44px] touch-manipulation items-center justify-center whitespace-nowrap break-words rounded-md px-3 py-1.5 text-sm font-medium ring-offset-[var(--cor-fundo)] transition-[background-color,color,box-shadow]",
      "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] focus-visible:ring-offset-2",
      "disabled:pointer-events-none disabled:opacity-50",
      "data-[state=active]:bg-white data-[state=active]:text-[var(--cor-primaria)] data-[state=active]:shadow-sm",
      "motion-reduce:transition-none",
      className
    )}
    {...props}
  />
));
TabsTrigger.displayName = TabsPrimitive.Trigger.displayName;

const TabsContent = React.forwardRef<
  React.ElementRef<typeof TabsPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof TabsPrimitive.Content>
>(({ className, ...props }, ref) => (
  <TabsPrimitive.Content
    ref={ref}
    className={cn(
      "mt-4 min-w-0 break-words ring-offset-[var(--cor-fundo)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] focus-visible:ring-offset-2",
      className
    )}
    {...props}
  />
));
TabsContent.displayName = TabsPrimitive.Content.displayName;

export interface AbaTab {
  chave: string;
  rotulo: React.ReactNode;
  conteudo: React.ReactNode;
  disabled?: boolean;
}

export default function TabsComponent({ abas, abaInicial }: { abas: AbaTab[]; abaInicial?: string }) {
  const defaultValue = abaInicial || abas.find((a) => !a.disabled)?.chave || abas[0]?.chave;
  return (
    <Tabs defaultValue={defaultValue} className="w-full">
      <TabsList>
        {abas.map((aba) => (
          <TabsTrigger key={aba.chave} value={aba.chave} disabled={aba.disabled}>
            {aba.rotulo}
          </TabsTrigger>
        ))}
      </TabsList>
      {abas.map((aba) => (
        <TabsContent key={aba.chave} value={aba.chave}>
          {aba.conteudo}
        </TabsContent>
      ))}
    </Tabs>
  );
}

export { Tabs, TabsList, TabsTrigger, TabsContent };
