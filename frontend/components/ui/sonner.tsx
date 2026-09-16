"use client";

import { Toaster as SonnerToaster, type ToasterProps } from "sonner";

// Toasts de ação (com botões/undo). Para compat legada Radix, ver `./toast` + `./toaster`.
function Toaster({ ...props }: ToasterProps) {
  return (
    <SonnerToaster
      theme="system"
      className="toaster group"
      toastOptions={{
        classNames: {
          toast:
            "group pointer-events-auto relative flex w-full items-center justify-between gap-4 overflow-hidden rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-4 pr-8 text-[var(--cor-texto)] shadow-lg motion-reduce:transition-none",
          description: "text-sm text-[var(--cor-texto-suave)]",
          actionButton:
            "inline-flex h-8 min-h-[44px] shrink-0 touch-manipulation items-center justify-center rounded-md border border-[var(--cor-borda)] bg-transparent px-3 text-sm font-medium text-[var(--cor-texto)] hover:bg-[var(--cor-primaria-suave)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 motion-reduce:transition-none",
          cancelButton:
            "absolute right-2 top-2 inline-flex min-h-[44px] min-w-[44px] touch-manipulation items-center justify-center rounded-md p-1 text-[var(--cor-texto-suave)] opacity-70 hover:text-[var(--cor-texto)] hover:opacity-100 focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] motion-reduce:transition-none",
          success:
            "border-[var(--cor-sucesso)] text-[var(--cor-texto)]",
          error: "border-[var(--cor-erro)] text-[var(--cor-texto)]",
        },
      }}
      {...props}
    />
  );
}

export { Toaster };
export type { ToasterProps };
