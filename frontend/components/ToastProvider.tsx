"use client";
import * as React from "react";
import { Toaster, toast as sonnerToast } from "sonner";
export function ToastProvider({ children }: { children: React.ReactNode }) {
  return (
    <>
      {children}
      <Toaster richColors closeButton position="bottom-right" toastOptions={{ style: { background: "var(--cor-fundo-card)", color: "var(--cor-texto)", border: "1px solid var(--cor-borda)" } }} />
    </>
  );
}
type TipoNotificacao = "sucesso" | "erro" | "info";
export function useToast() {
  const notificar = React.useCallback((mensagem: string, tipo: TipoNotificacao = "info") => {
    if (tipo === "sucesso") sonnerToast.success(mensagem);
    else if (tipo === "erro") sonnerToast.error(mensagem);
    else sonnerToast(mensagem);
  }, []);
  return { notificar, toast: sonnerToast };
}
