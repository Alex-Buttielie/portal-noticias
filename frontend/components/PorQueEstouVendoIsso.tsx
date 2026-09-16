"use client";

import { useState } from "react";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { Info, X } from "lucide-react";
import { cn } from "@/lib/utils";

export default function PorQueEstouVendoIsso({ motivos }: { motivos: string[] }) {
  const [aberto, setAberto] = useState(false);

  if (motivos.length === 0) return null;

  return (
    <DialogPrimitive.Root open={aberto} onOpenChange={setAberto}>
      <DialogPrimitive.Trigger asChild>
        <button
          type="button"
          className={cn(
            "inline-flex items-center gap-1.5 rounded-full border border-dashed border-[var(--cor-borda)] bg-transparent px-3 py-1.5 text-xs font-medium text-[var(--cor-texto-suave)]",
            "hover:border-[var(--cor-primaria)] hover:text-[var(--cor-primaria)] data-[state=open]:border-solid data-[state=open]:border-[var(--cor-primaria)] data-[state=open]:text-[var(--cor-primaria)]",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] focus-visible:ring-offset-2",
            "motion-reduce:transition-none transition-colors"
          )}
          aria-expanded={aberto}
        >
          <Info className="h-3.5 w-3.5" aria-hidden="true" /> Por que estou vendo isso?
        </button>
      </DialogPrimitive.Trigger>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay
          className={cn("fixed inset-0 z-50 bg-black/20 backdrop-blur-sm data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 motion-reduce:animate-none")}
        />
        <DialogPrimitive.Content
          className={cn(
            "fixed left-[50%] top-[50%] z-50 w-full max-w-sm translate-x-[-50%] translate-y-[-50%] rounded-lg border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-5 shadow-lg",
            "data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 motion-reduce:animate-none"
          )}
        >
          <DialogPrimitive.Title className="text-xs font-semibold uppercase tracking-widest text-[var(--cor-texto-suave)]">
            Por que este conteúdo apareceu
          </DialogPrimitive.Title>
          <ul className={cn("mt-3 flex flex-col gap-2 text-sm")}>
            {motivos.map((motivo) => (
              <li key={motivo} className={cn("flex gap-2 leading-relaxed")}>
                <span className="text-[var(--cor-primaria)]" aria-hidden="true">
                  •
                </span>
                <span>{motivo}</span>
              </li>
            ))}
          </ul>
          <DialogPrimitive.Close
            className={cn(
              "absolute right-3 top-3 rounded-sm opacity-70 hover:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]"
            )}
          >
            <X className="h-4 w-4" />
            <span className="sr-only">Fechar</span>
          </DialogPrimitive.Close>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
