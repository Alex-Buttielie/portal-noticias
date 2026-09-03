"use client";

import { useEffect, useState } from "react";

const CHAVE_TEMA = "portal_noticias_tema";

type Tema = "light" | "dark";

function lerTemaAtual(): Tema {
  if (typeof document === "undefined") return "light";
  const explicito = document.documentElement.getAttribute("data-theme");
  if (explicito === "dark" || explicito === "light") return explicito;
  // Sem preferência explícita salva: reflete o tema que já está sendo
  // exibido via prefers-color-scheme (ver globals.css), em vez de assumir
  // "light" e mostrar o ícone/estado errado no primeiro clique.
  if (typeof window !== "undefined" && window.matchMedia("(prefers-color-scheme: dark)").matches) {
    return "dark";
  }
  return "light";
}

/**
 * Alternância de tema manual. Por padrão o site segue prefers-color-scheme
 * (ver globals.css e o script inline em layout.tsx, que evita o flash de
 * tema incorreto); este botão permite fixar uma preferência explícita,
 * persistida em localStorage — o escuro também reduz consumo de energia em
 * telas OLED, parte do compromisso de design sustentável.
 */
export default function ThemeToggle() {
  const [tema, setTema] = useState<Tema>("light");

  useEffect(() => {
    setTema(lerTemaAtual());
  }, []);

  function alternar() {
    const novoTema: Tema = tema === "dark" ? "light" : "dark";
    setTema(novoTema);
    document.documentElement.setAttribute("data-theme", novoTema);
    try {
      window.localStorage.setItem(CHAVE_TEMA, novoTema);
    } catch {
      // ignora — preferência vale só para esta sessão.
    }
  }

  return (
    <button
      type="button"
      className="botao-tema"
      onClick={alternar}
      aria-label={tema === "dark" ? "Mudar para tema claro" : "Mudar para tema escuro"}
      title={tema === "dark" ? "Tema escuro ativo" : "Tema claro ativo"}
    >
      <span aria-hidden="true">{tema === "dark" ? "☀️" : "🌙"}</span>
    </button>
  );
}
