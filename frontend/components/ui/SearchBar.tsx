"use client";

import { useEffect, useState } from "react";
import { Search } from "lucide-react";
import { cn } from "@/lib/utils";

interface Propriedades {
  valorInicial?: string;
  rotulo?: string;
  placeholder?: string;
  atrasoMs?: number;
  aoBuscar: (termo: string) => void;
}

export function SearchBar({
  valorInicial = "",
  rotulo = "Buscar",
  placeholder = "Buscar notícias, temas…",
  atrasoMs = 400,
  aoBuscar,
}: Propriedades) {
  const [termo, setTermo] = useState(valorInicial);

  useEffect(() => {
    setTermo(valorInicial);
  }, [valorInicial]);

  useEffect(() => {
    const id = window.setTimeout(() => aoBuscar(termo.trim()), atrasoMs);
    return () => window.clearTimeout(id);
  }, [termo, atrasoMs, aoBuscar]);

  return (
    <form
      role="search"
      className={cn("flex w-full items-center gap-2")}
      onSubmit={(evento) => {
        evento.preventDefault();
        aoBuscar(termo.trim());
      }}
    >
      <label htmlFor="busca-global" className="sr-only">
        {rotulo}
      </label>
<div className="relative flex-1">
        <Search
          className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--cor-texto-suave)]"
          aria-hidden="true"
        />
        <input
          id="busca-global"
          name="busca"
          type="search"
          inputMode="search"
          enterKeyHint="search"
          placeholder={placeholder}
          value={termo}
          onChange={(evento) => setTermo(evento.target.value)}
          autoComplete="off"
          className={cn(
            "busca__campo flex h-10 min-h-[44px] w-full touch-manipulation rounded-full border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] py-2 pl-10 pr-4 text-[16px] sm:text-sm",
            "placeholder:text-[var(--cor-texto-suave)]",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] focus-visible:ring-offset-0",
            "motion-reduce:transition-none transition-colors"
          )}
        />
      </div>
      <button
        type="submit"
        className={cn(
          "botao botao--secundaria botao--pequeno inline-flex min-h-[44px] touch-manipulation items-center justify-center rounded-full bg-[var(--cor-primaria)] px-5 text-sm font-semibold text-white",
          "hover:bg-[var(--cor-primaria-hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] focus-visible:ring-offset-2",
          "disabled:opacity-50 motion-reduce:transition-none transition-colors"
        )}
      >
        Buscar
      </button>
    </form>
  );
}
