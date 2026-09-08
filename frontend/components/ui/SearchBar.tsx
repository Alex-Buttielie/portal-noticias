"use client";

import { useEffect, useState } from "react";

interface Propriedades {
  valorInicial?: string;
  rotulo?: string;
  placeholder?: string;
  atrasoMs?: number;
  aoBuscar: (termo: string) => void;
}

export function SearchBar({ valorInicial = "", rotulo = "Buscar", placeholder = "Buscar notícias, temas…", atrasoMs = 400, aoBuscar }: Propriedades) {
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
      className="busca"
      onSubmit={(evento) => {
        evento.preventDefault();
        aoBuscar(termo.trim());
      }}
    >
      <label className="busca__rotulo-visualmente-oculto" htmlFor="busca-global">
        {rotulo}
      </label>
      <input
        id="busca-global"
        type="search"
        className="busca__campo"
        placeholder={placeholder}
        value={termo}
        onChange={(evento) => setTermo(evento.target.value)}
        autoComplete="off"
      />
    </form>
  );
}
