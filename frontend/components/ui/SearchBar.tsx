"use client";

import { useEffect, useState } from "react";
import { Search } from "lucide-react";
import { cn } from "@/lib/utils";
import { Input } from "./input";
import { Button } from "./button";

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
  placeholder = "Buscar notícias, temas",
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
        <Input
          id="busca-global"
          name="busca"
          type="search"
          inputMode="text"
          enterKeyHint="search"
          placeholder={placeholder}
          value={termo}
          onChange={(evento) => setTermo(evento.target.value)}
          autoComplete="off"
          className="rounded-full py-2 pl-10 pr-4 text-[16px] sm:text-sm"
        />
      </div>
      <Button type="submit" className="shrink-0 rounded-full px-5">
        Buscar
      </Button>
    </form>
  );
}
