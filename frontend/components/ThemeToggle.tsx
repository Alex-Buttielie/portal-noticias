"use client";

import { useEffect, useState } from "react";
import { Moon, Sun } from "lucide-react";
import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

function cn(...inputs: (string | boolean | undefined)[]) {
  return twMerge(clsx(inputs));
}

const CHAVE_TEMA = "portal_noticias_tema";

type Tema = "light" | "dark";

function lerTemaAtual(): Tema {
  if (typeof document === "undefined") return "light";
  const explicito = document.documentElement.getAttribute("data-theme");
  if (explicito === "dark" || explicito === "light") return explicito;
  if (typeof window !== "undefined" && window.matchMedia("(prefers-color-scheme: dark)").matches) {
    return "dark";
  }
  return "light";
}

/**
 * Alternância de tema manual. Preserva `localStorage portal_noticias_tema`
 * e `data-theme` (contrato LGPD/anti-flash com layout.tsx: SCRIPT_TEMA_INICIAL).
 * Visual: shadcn Button ghost icon + lucide-react + focus-visible:ring + motion-reduce.
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
      onClick={alternar}
      aria-label={tema === "dark" ? "Mudar para tema claro" : "Mudar para tema escuro"}
      title={tema === "dark" ? "Tema escuro ativo" : "Tema claro ativo"}
      className={cn(
        // legado `botao-tema` preservado como alias
        "botao-tema",
        "inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-[var(--cor-borda)] bg-transparent text-[var(--cor-texto-suave)]",
        "transition-[transform,background,border-color,color] duration-150 ease-out",
        "hover:border-[var(--cor-primaria)] hover:bg-[var(--cor-primaria-suave)] hover:text-[var(--cor-primaria)] hover:rotate-[12deg]",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--cor-fundo)]",
        "active:scale-[0.96]",
        "motion-reduce:transition-none motion-reduce:hover:rotate-0"
      )}
    >
      <span aria-hidden="true" className="inline-flex">
        {tema === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
      </span>
    </button>
  );
}
