"use client";

import { useId, useState, type ReactNode } from "react";

/**
 * Dica curta associada a um elemento — aparece no hover E no foco por
 * teclado (não só no mouse, para não excluir quem navega por teclado),
 * some com `Escape` (implementation-contract.md run
 * 20260903-1134-seo-lgpd-design-system, escopo D). `aria-describedby`
 * conecta o gatilho ao texto para leitores de tela, mesmo quando o balão
 * não está visualmente aberto ainda (o leitor de tela anuncia ao focar).
 */
export default function Tooltip({
  texto,
  children,
  posicao = "cima",
}: {
  texto: string;
  children: ReactNode;
  posicao?: "cima" | "baixo";
}) {
  const [visivel, setVisivel] = useState(false);
  const tooltipId = useId();

  function aoPressionarTecla(evento: React.KeyboardEvent) {
    if (evento.key === "Escape") setVisivel(false);
  }

  return (
    <span
      className="tooltip"
      onMouseEnter={() => setVisivel(true)}
      onMouseLeave={() => setVisivel(false)}
      onFocus={() => setVisivel(true)}
      onBlur={() => setVisivel(false)}
      onKeyDown={aoPressionarTecla}
    >
      <span aria-describedby={visivel ? tooltipId : undefined}>{children}</span>
      {visivel && (
        <span
          role="tooltip"
          id={tooltipId}
          className={posicao === "baixo" ? "tooltip-balao tooltip-balao--baixo" : "tooltip-balao"}
        >
          {texto}
        </span>
      )}
    </span>
  );
}
