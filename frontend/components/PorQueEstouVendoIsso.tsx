"use client";

import { useEffect, useId, useRef, useState } from "react";

/**
 * IA visível e transparente: cada cartão do feed pode explicar em
 * linguagem simples por que aquele conteúdo apareceu ali. Acessível via
 * teclado (Enter/Espaço abre, Escape fecha, foco não escapa da página) e
 * via leitor de tela (aria-expanded, aria-controls, role="dialog").
 */
export default function PorQueEstouVendoIsso({ motivos }: { motivos: string[] }) {
  const [aberto, setAberto] = useState(false);
  const painelId = useId();
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!aberto) return;

    function aoClicarFora(evento: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(evento.target as Node)) {
        setAberto(false);
      }
    }

    function aoPressionarTecla(evento: KeyboardEvent) {
      if (evento.key === "Escape") setAberto(false);
    }

    document.addEventListener("mousedown", aoClicarFora);
    document.addEventListener("keydown", aoPressionarTecla);
    return () => {
      document.removeEventListener("mousedown", aoClicarFora);
      document.removeEventListener("keydown", aoPressionarTecla);
    };
  }, [aberto]);

  if (motivos.length === 0) return null;

  return (
    <div className="explicacao-ia" ref={containerRef}>
      <button
        type="button"
        className="explicacao-ia-gatilho"
        aria-expanded={aberto}
        aria-controls={painelId}
        onClick={(evento) => {
          evento.preventDefault();
          evento.stopPropagation();
          setAberto((valor) => !valor);
        }}
      >
        <span aria-hidden="true">ⓘ</span> Por que estou vendo isso?
      </button>
      {aberto && (
        <div
          id={painelId}
          role="dialog"
          aria-label="Motivo desta recomendação"
          className="explicacao-ia-painel"
          onClick={(evento) => evento.stopPropagation()}
        >
          <h3>Por que este conteúdo apareceu</h3>
          <ul>
            {motivos.map((motivo) => (
              <li key={motivo}>{motivo}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
