"use client";

import * as React from "react";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

export function Drawer({
  aberto,
  aoFechar,
  titulo,
  children,
}: {
  aberto: boolean;
  aoFechar: () => void;
  titulo: string;
  children: React.ReactNode;
}) {
return (
    <DialogPrimitive.Root open={aberto} onOpenChange={(open) => !open && aoFechar()}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay
          className={cn(
            "fixed inset-0 z-50 bg-black/40 backdrop-blur-sm [overscroll-behavior:contain]",
            "data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0",
            "motion-reduce:animate-none"
          )}
        />
        <DialogPrimitive.Content
          className={cn(
            "fixed inset-y-0 right-0 z-50 flex h-full w-full max-w-sm flex-col gap-4 overflow-hidden border-l border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-6 shadow-lg [overscroll-behavior:contain]",
            "data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:slide-out-to-right data-[state=open]:slide-in-from-right",
            "motion-reduce:animate-none focus-visible:outline-none"
          )}
          aria-describedby={undefined}
        >
          <div className="drawer__cabecalho flex min-w-0 items-center justify-between gap-2">
            <DialogPrimitive.Title className="drawer__titulo min-w-0 flex-1 break-words text-base font-semibold leading-none tracking-tight">
              {titulo}
            </DialogPrimitive.Title>
            <DialogPrimitive.Close
              className={cn(
                "botao botao--fantasma botao--pequeno inline-flex min-h-[44px] min-w-[44px] touch-manipulation items-center justify-center rounded-sm p-1 opacity-70 ring-offset-[var(--cor-fundo)] transition-opacity hover:opacity-100 motion-reduce:transition-none",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] focus-visible:ring-offset-2"
              )}
              aria-label="Fechar painel"
            >
              <X className="h-4 w-4" />
            </DialogPrimitive.Close>
          </div>
          <div className="drawer__corpo drawer-fundo flex-1 overflow-auto [overscroll-behavior:contain]">{children}</div>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
