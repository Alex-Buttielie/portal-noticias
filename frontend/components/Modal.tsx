"use client";

import { useEffect, useId, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";

/**
 * Diálogo modal com overlay (implementation-contract.md run
 * 20260903-1134-seo-lgpd-design-system, escopo D, critério de aceite 6):
 * `Escape` ou clique fora fecham o modal e o foco retorna ao elemento que
 * o abriu (capturado automaticamente via `document.activeElement` no
 * instante em que `aberto` vira `true` — o chamador não precisa gerenciar
 * foco manualmente). Foco preso dentro do modal enquanto aberto (Tab/
 * Shift+Tab não escapam para o resto da página). `carregando` desabilita o
 * fechamento (Escape/clique fora/botão "X") enquanto uma ação estiver em
 * andamento — evita fechar no meio de um envio.
 */
export default function Modal({
  aberto,
  aoFechar,
  titulo,
  children,
  rodape,
  carregando = false,
}: {
  aberto: boolean;
  aoFechar: () => void;
  titulo: string;
  children: ReactNode;
  rodape?: ReactNode;
  carregando?: boolean;
}) {
  const tituloId = useId();
  const modalRef = useRef<HTMLDivElement>(null);
  const elementoQueAbriuRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (aberto) {
      elementoQueAbriuRef.current = document.activeElement as HTMLElement | null;
      const temporizador = window.setTimeout(() => modalRef.current?.focus(), 0);
      return () => window.clearTimeout(temporizador);
    }
    elementoQueAbriuRef.current?.focus();
    elementoQueAbriuRef.current = null;
  }, [aberto]);

  useEffect(() => {
    if (!aberto) return;

    function aoPressionarTecla(evento: KeyboardEvent) {
      if (carregando) return;
      if (evento.key === "Escape") {
        evento.preventDefault();
        aoFechar();
        return;
      }
      if (evento.key === "Tab") {
        const focaveis = modalRef.current?.querySelectorAll<HTMLElement>(
          'a[href], button:not([disabled]), textarea, input, select, [tabindex]:not([tabindex="-1"])'
        );
        if (!focaveis || focaveis.length === 0) return;
        const primeiro = focaveis[0];
        const ultimo = focaveis[focaveis.length - 1];
        if (evento.shiftKey && document.activeElement === primeiro) {
          evento.preventDefault();
          ultimo.focus();
        } else if (!evento.shiftKey && document.activeElement === ultimo) {
          evento.preventDefault();
          primeiro.focus();
        }
      }
    }
    document.addEventListener("keydown", aoPressionarTecla);
    return () => document.removeEventListener("keydown", aoPressionarTecla);
  }, [aberto, aoFechar, carregando]);

  if (!aberto || typeof document === "undefined") return null;

  return createPortal(
    <div
      className="modal-fundo"
      onClick={(evento) => {
        if (evento.target === evento.currentTarget && !carregando) aoFechar();
      }}
    >
      <div className="modal" role="dialog" aria-modal="true" aria-labelledby={tituloId} ref={modalRef} tabIndex={-1}>
        <div className="modal-cabecalho">
          <h2 id={tituloId} className="modal-titulo">
            {titulo}
          </h2>
          <button
            type="button"
            className="modal-fechar"
            aria-label="Fechar"
            disabled={carregando}
            onClick={() => aoFechar()}
          >
            ✕
          </button>
        </div>
        <div className="modal-corpo">{children}</div>
        {rodape && <div className="modal-rodape">{rodape}</div>}
      </div>
    </div>,
    document.body
  );
}
