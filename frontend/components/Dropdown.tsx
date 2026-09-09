"use client";

import { useEffect, useId, useRef, useState, type ReactNode } from "react";

export interface ItemDropdown {
  chave: string;
  rotulo: ReactNode;
  aoSelecionar?: () => void;
  disabled?: boolean;
}

/**
 * Menu de ações/opções ancorado a um botão (implementation-contract.md run
 * 20260903-1134-seo-lgpd-design-system, escopo D). `Escape` fecha e devolve
 * o foco ao gatilho (mesma regra do `Modal`); clique fora também fecha;
 * setas cima/baixo navegam entre itens; `Enter`/`Espaço` seleciona.
 */
export default function Dropdown({
  rotuloGatilho,
  itens,
  carregando = false,
  disabled = false,
  alinhamento = "esquerda",
}: {
  rotuloGatilho: ReactNode;
  itens: ItemDropdown[];
  carregando?: boolean;
  disabled?: boolean;
  alinhamento?: "esquerda" | "direita";
}) {
  const [aberto, setAberto] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const gatilhoRef = useRef<HTMLButtonElement>(null);
  const itensRefs = useRef<(HTMLButtonElement | null)[]>([]);
  const menuId = useId();

  useEffect(() => {
    if (!aberto) return;

    function aoClicarFora(evento: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(evento.target as Node)) {
        setAberto(false);
      }
    }
    document.addEventListener("mousedown", aoClicarFora);
    return () => document.removeEventListener("mousedown", aoClicarFora);
  }, [aberto]);

  function fechar(devolverFoco: boolean) {
    setAberto(false);
    if (devolverFoco) gatilhoRef.current?.focus();
  }

  function aoPressionarTeclaNoMenu(evento: React.KeyboardEvent) {
    const habilitados = itens.map((item, indice) => ({ item, indice })).filter((x) => !x.item.disabled);
    if (habilitados.length === 0) return;

    if (evento.key === "Escape") {
      evento.preventDefault();
      fechar(true);
      return;
    }
    if (evento.key === "ArrowDown" || evento.key === "ArrowUp") {
      evento.preventDefault();
      const focoAtual = itensRefs.current.findIndex((el) => el === document.activeElement);
      const posAtual = habilitados.findIndex((x) => x.indice === focoAtual);
      const proximo =
        evento.key === "ArrowDown"
          ? habilitados[(posAtual + 1 + habilitados.length) % habilitados.length]
          : habilitados[(posAtual - 1 + habilitados.length) % habilitados.length];
      itensRefs.current[proximo.indice]?.focus();
    }
  }

  return (
    <div className="dropdown" ref={containerRef}>
      <button
        type="button"
        ref={gatilhoRef}
        className="botao botao-secundario"
        aria-haspopup="menu"
        aria-expanded={aberto}
        aria-controls={menuId}
        disabled={disabled}
        onClick={() => setAberto((valor) => !valor)}
      >
        {rotuloGatilho}
      </button>

      {aberto && (
        <div
          id={menuId}
          role="menu"
          className={alinhamento === "direita" ? "dropdown-menu dropdown-menu--direita" : "dropdown-menu"}
          onKeyDown={aoPressionarTeclaNoMenu}
        >
          {carregando && (
            <span className="dropdown-item" aria-disabled="true">
              Carregando…
            </span>
          )}
          {!carregando &&
            itens.map((item, indice) => (
              <button
                key={item.chave}
                type="button"
                role="menuitem"
                ref={(el) => {
                  itensRefs.current[indice] = el;
                }}
                className="dropdown-item"
                disabled={item.disabled}
                onClick={() => {
                  item.aoSelecionar?.();
                  fechar(true);
                }}
              >
                {item.rotulo}
              </button>
            ))}
        </div>
      )}
    </div>
  );
}
