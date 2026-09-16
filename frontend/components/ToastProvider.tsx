"use client";

import * as React from "react";
import * as ToastPrimitives from "@radix-ui/react-toast";
import { X, CheckCircle, AlertCircle, Info } from "lucide-react";
import { cn } from "@/lib/utils";

export type TipoNotificacao = "sucesso" | "erro" | "info";

interface Notificacao {
  id: number;
  mensagem: string;
  tipo: TipoNotificacao;
}

interface ToastContextValue {
  notificar: (mensagem: string, tipo?: TipoNotificacao) => void;
}

const ToastContext = React.createContext<ToastContextValue | undefined>(undefined);

const DURACAO_MS = 4500;

function ToastViewport({ className, ...props }: React.ComponentPropsWithoutRef<typeof ToastPrimitives.Viewport>) {
  return (
    <ToastPrimitives.Viewport
      className={cn(
        "fixed bottom-0 right-0 z-[100] flex max-h-screen w-full flex-col-reverse p-4 [overscroll-behavior:contain] sm:bottom-0 sm:right-0 sm:top-auto sm:flex-col md:max-w-[360px]",
        className
      )}
      {...props}
    />
  );
}

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [notificacoes, setNotificacoes] = React.useState<Notificacao[]>([]);
  const proximoId = React.useRef(0);
  const temporizadores = React.useRef(new Map<number, number>());

  const dispensar = React.useCallback((id: number) => {
    const temporizador = temporizadores.current.get(id);
    if (temporizador) {
      window.clearTimeout(temporizador);
      temporizadores.current.delete(id);
    }
    setNotificacoes((atual) => atual.filter((n) => n.id !== id));
  }, []);

  const agendarDispensa = React.useCallback(
    (id: number) => {
      const temporizador = window.setTimeout(() => dispensar(id), DURACAO_MS);
      temporizadores.current.set(id, temporizador);
    },
    [dispensar]
  );

  const notificar = React.useCallback(
    (mensagem: string, tipo: TipoNotificacao = "info") => {
      const id = proximoId.current++;
      setNotificacoes((atual) => [...atual, { id, mensagem, tipo }]);
      agendarDispensa(id);
    },
    [agendarDispensa]
  );

  function aoPassarMouse(id: number) {
    const temporizador = temporizadores.current.get(id);
    if (temporizador) {
      window.clearTimeout(temporizador);
      temporizadores.current.delete(id);
    }
  }

  function aoTirarMouse(id: number) {
    agendarDispensa(id);
  }

  return (
    <ToastContext.Provider value={{ notificar }}>
      <ToastPrimitives.Provider swipeDirection="right">
        {children}
        {notificacoes.map((n) => {
          const Icon = n.tipo === "sucesso" ? CheckCircle : n.tipo === "erro" ? AlertCircle : Info;
          const borderColor =
            n.tipo === "sucesso"
              ? "border-l-[var(--cor-sucesso)]"
              : n.tipo === "erro"
                ? "border-l-[var(--cor-erro)]"
                : "border-l-[var(--cor-primaria)]";
          return (
            <ToastPrimitives.Root
              key={n.id}
              duration={DURACAO_MS}
              className={cn(
                "group pointer-events-auto relative flex w-full min-w-0 touch-manipulation items-start gap-3 overflow-hidden rounded-lg border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-4 pr-8 shadow-lg transition-[transform,opacity,background-color,border-color] motion-reduce:transition-none [overscroll-behavior:contain]",
                "border-l-4 data-[swipe=cancel]:translate-x-0 data-[swipe=end]:translate-x-[var(--radix-toast-swipe-end-x)] data-[swipe=move]:translate-x-[var(--radix-toast-swipe-move-x)] data-[swipe=move]:transition-none",
                "data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-80 data-[state=closed]:slide-out-to-right-full data-[state=open]:slide-in-from-top-full",
                "motion-reduce:animate-none",
                borderColor
              )}
              onMouseEnter={() => aoPassarMouse(n.id)}
              onMouseLeave={() => aoTirarMouse(n.id)}
            >
              <Icon
                className={cn(
                  "h-5 w-5 shrink-0 mt-0.5",
                  n.tipo === "sucesso" && "text-[var(--cor-sucesso)]",
                  n.tipo === "erro" && "text-[var(--cor-erro)]",
                  n.tipo === "info" && "text-[var(--cor-primaria)]"
                )}
                aria-hidden="true"
              />
              <div className="min-w-0 flex-1 break-words text-sm font-medium leading-none">{n.mensagem}</div>
              <ToastPrimitives.Close
                className={cn(
                  "absolute right-2 top-2 inline-flex min-h-[44px] min-w-[44px] touch-manipulation items-center justify-center rounded-md p-1 text-[var(--cor-texto-suave)] opacity-70 transition-opacity hover:opacity-100 motion-reduce:transition-none",
                  "focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]"
                )}
                onClick={() => dispensar(n.id)}
              >
                <X className="h-4 w-4" />
              </ToastPrimitives.Close>
            </ToastPrimitives.Root>
          );
        })}
        <ToastViewport />
      </ToastPrimitives.Provider>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const contexto = React.useContext(ToastContext);
  if (!contexto) {
    throw new Error("useToast precisa ser usado dentro de um ToastProvider.");
  }
  return contexto;
}
