"use client";

import { useEffect, useId, useState } from "react";

interface Propriedades {
  valorInicial?: string;
  rotulo?: string;
  placeholder?: string;
  atrasoMs?: number;
  aoBuscar: (termo: string) => void;
}

// Busca em pílula com debounce — mesma lógica de antes, só visual + a11y:
// id único por instância e botão de envio visível (40px+, foco visível global).
export function SearchBar({ valorInicial = "", rotulo = "Buscar", placeholder = "Buscar notícias, temas…", atrasoMs = 400, aoBuscar }: Propriedades) {
  const [termo, setTermo] = useState(valorInicial);
  const idCampo = useId();

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
      className="busca busca--pill"
      onSubmit={(evento) => {
        evento.preventDefault();
        aoBuscar(termo.trim());
      }}
    >
      <label className="busca__rotulo-visualmente-oculto" htmlFor={idCampo}>
        {rotulo}
      </label>
      <input
        id={idCampo}
        type="search"
        className="busca__campo"
        style={{ borderRadius: "var(--raio-completo)" }}
        placeholder={placeholder}
        value={termo}
        onChange={(evento) => setTermo(evento.target.value)}
        autoComplete="off"
      />
      <button
        type="submit"
        className="botao botao--primaria botao--medio"
        style={{ borderRadius: "var(--raio-completo)", minHeight: 44, flexShrink: 0 }}
        aria-label={rotulo}
      >
        <span aria-hidden="true">⌕</span> Buscar
      </button>
    </form>
  );
}
