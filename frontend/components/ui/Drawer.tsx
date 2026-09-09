"use client";

import { useEffect, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";

// Painel lateral (bottom-sheet no mobile via `.drawer*` em globals.css).
// Mesma lógica de antes: Escape fecha, clique fora fecha, scroll trava,
// foco inicial vai ao primeiro interativo. Só visual + rótulos.
export function Drawer({
  aberto,
  aoFechar,
  titulo,
  children,
}: {
  aberto: boolean;
  aoFechar: () => void;
  titulo: string;
  children: ReactNode;
}) {
  const referencia = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!aberto) return;
    function aoTeclar(evento: KeyboardEvent) {
      if (evento.key === "Escape") aoFechar();
    }
    document.addEventListener("keydown", aoTeclar);
    const anterior = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    referencia.current?.querySelector<HTMLElement>("button, a, input, select, textarea")?.focus();
    return () => {
      document.removeEventListener("keydown", aoTeclar);
      document.body.style.overflow = anterior;
    };
  }, [aberto, aoFechar]);

  if (!aberto || typeof document === "undefined") return null;

  return createPortal(
    <div className="drawer-fundo" onClick={aoFechar} role="presentation">
      <div
        ref={referencia}
        className="drawer"
        role="dialog"
        aria-modal="true"
        aria-label={titulo}
        onClick={(evento) => evento.stopPropagation()}
      >
        <div className="drawer__cabecalho">
          <h2 className="drawer__titulo">{titulo}</h2>
          <button
            type="button"
            className="botao botao--fantasma botao--pequeno"
            style={{ minHeight: 40, minWidth: 40 }}
            onClick={aoFechar}
            aria-label={`Fechar painel: ${titulo}`}
          >
            <span aria-hidden="true">✕</span>
          </button>
        </div>
        <div className="drawer__corpo">{children}</div>
      </div>
    </div>,
    document.body
  );
}
