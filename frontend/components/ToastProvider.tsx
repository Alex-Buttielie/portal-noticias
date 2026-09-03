"use client";

import {
  createContext,
  useCallback,
  useContext,
  useRef,
  useState,
  type ReactNode,
} from "react";

export type TipoNotificacao = "sucesso" | "erro" | "info";

interface Notificacao {
  id: number;
  mensagem: string;
  tipo: TipoNotificacao;
}

interface ToastContextValue {
  notificar: (mensagem: string, tipo?: TipoNotificacao) => void;
}

const ToastContext = createContext<ToastContextValue | undefined>(undefined);

const DURACAO_MS = 4500;

/**
 * Feedback global e imediato para ações do usuário (seguir, comentar,
 * assinar, etc.) — substitui mensagens estáticas que só aparecem depois de
 * um recarregamento de estado, reforçando a sensação de interface viva.
 */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [notificacoes, setNotificacoes] = useState<Notificacao[]>([]);
  const proximoId = useRef(0);
  const temporizadores = useRef(new Map<number, number>());

  const dispensar = useCallback((id: number) => {
    const temporizador = temporizadores.current.get(id);
    if (temporizador) {
      window.clearTimeout(temporizador);
      temporizadores.current.delete(id);
    }
    setNotificacoes((atual) => atual.filter((n) => n.id !== id));
  }, []);

  const agendarDispensa = useCallback(
    (id: number) => {
      const temporizador = window.setTimeout(() => dispensar(id), DURACAO_MS);
      temporizadores.current.set(id, temporizador);
    },
    [dispensar]
  );

  const notificar = useCallback(
    (mensagem: string, tipo: TipoNotificacao = "info") => {
      const id = proximoId.current++;
      setNotificacoes((atual) => [...atual, { id, mensagem, tipo }]);
      agendarDispensa(id);
    },
    [agendarDispensa]
  );

  // Passar o mouse pausa a contagem — evita que uma mensagem mais longa
  // suma antes do usuário terminar de ler.
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
      {children}
      <div className="toast-container" aria-live="polite" aria-atomic="false">
        {notificacoes.map((n) => (
          <div
            key={n.id}
            role="status"
            className={`toast toast--${n.tipo}`}
            onMouseEnter={() => aoPassarMouse(n.id)}
            onMouseLeave={() => aoTirarMouse(n.id)}
          >
            <span>{n.mensagem}</span>
            <button
              type="button"
              className="toast-fechar"
              aria-label="Dispensar notificação"
              onClick={() => dispensar(n.id)}
            >
              ✕
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const contexto = useContext(ToastContext);
  if (!contexto) {
    throw new Error("useToast precisa ser usado dentro de um ToastProvider.");
  }
  return contexto;
}
