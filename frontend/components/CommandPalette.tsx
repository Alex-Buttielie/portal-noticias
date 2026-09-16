"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Search, X } from "lucide-react";
import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

function cn(...inputs: (string | boolean | undefined)[]) {
  return twMerge(clsx(inputs));
}

const ATALHOS = [
  { label: "Últimas", href: "/" },
  { label: "Política", href: "/?categoria=política" },
  { label: "Economia", href: "/?categoria=economia" },
  { label: "Esportes", href: "/?categoria=esportes" },
  { label: "Tecnologia", href: "/?categoria=tecnologia" },
  { label: "Comunidade", href: "/comunidade" },
  { label: "Radar", href: "/radar" },
  { label: "Premium", href: "/planos" },
];

export default function CommandPalette({ aberto, aoFechar }: { aberto: boolean; aoFechar: () => void }) {
  const router = useRouter();
  const [q, setQ] = useState("");

  useEffect(() => {
    if (!aberto) setQ("");
  }, [aberto]);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") aoFechar();
    }
    if (aberto) window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [aberto, aoFechar]);

  if (!aberto) return null;

  const filtrados = q.trim()
    ? ATALHOS.filter((a) => a.label.toLowerCase().includes(q.toLowerCase()))
    : ATALHOS;

  function ir(href: string) {
    aoFechar();
    router.push(href);
  }

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    const t = q.trim();
    if (!t) return;
    const hit = filtrados[0];
    if (hit && hit.label.toLowerCase() === t.toLowerCase()) ir(hit.href);
    else ir(`/?busca=${encodeURIComponent(t)}`);
  }

  return (
<div className="fixed inset-0 z-[var(--z-modal-fundo)] flex items-start justify-center bg-black/30 p-4 pt-[18vh] backdrop-blur-sm motion-reduce:transition-none palette-fundo">
      {/* Backdrop via Button com aria-label — fecha ao clicar fora */}
      <button
        type="button"
        aria-label="Fechar busca rápida"
        onClick={aoFechar}
        className="absolute inset-0 h-full w-full cursor-default bg-transparent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/60"
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Busca rápida"
        onClick={(e) => e.stopPropagation()}
        className={cn(
          "palette relative z-10 w-full max-w-[640px] overflow-hidden rounded-2xl border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] shadow-[var(--sombra-3)]",
          "animate-in fade-in zoom-in-95 duration-150 ease-out motion-reduce:animate-none"
        )}
      >
        {/* Header: Input shadcn */}
        <form
          onSubmit={onSubmit}
          className="palette-busca flex items-center gap-3 border-b border-[var(--cor-borda)] px-4 py-3"
        >
          <Search className="h-4 w-4 shrink-0 text-[var(--cor-texto-suave)]" aria-hidden="true" />
          <label className="sr-only" htmlFor="busca-rapida">
            Buscar notícias, editorias e seções
          </label>
          <input
            id="busca-rapida"
            name="busca-rapida"
            type="search"
            autoComplete="off"
            autoFocus
            placeholder="Buscar notícias, editorias…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
className={cn(
              "flex h-9 w-full flex-1 rounded-md border-0 bg-transparent px-0 py-1 text-base placeholder:text-[var(--cor-texto-suave)] placeholder:opacity-70",
              "focus:outline-none focus-visible:outline-none focus-visible:ring-0",
              "motion-reduce:transition-none"
            )}
          />
          <kbd className="hidden shrink-0 rounded border border-[var(--cor-borda)] border-b-2 bg-[var(--cor-fundo)] px-1.5 py-0.5 font-mono text-[0.7rem] text-[var(--cor-texto-suave)] sm:inline-flex">
            ↵
          </kbd>
          {/* Botão fechar explícito — shadcn Button ghost icon */}
          <button
            type="button"
            aria-label="Fechar"
            onClick={aoFechar}
            className={cn(
              "inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-transparent bg-transparent text-[var(--cor-texto-suave)]",
              "hover:bg-[var(--cor-primaria-suave)] hover:text-[var(--cor-primaria)]",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] focus-visible:ring-offset-2",
              "motion-reduce:transition-none"
            )}
          >
            <X className="h-3.5 w-3.5" aria-hidden="true" />
          </button>
        </form>
        <div
          className="palette-lista max-h-[320px] overflow-auto p-2"
          role="listbox"
          aria-label="Atalhos e resultados"
        >
          {filtrados.map((a) => (
            <button
              key={a.href}
              type="button"
              role="option"
              aria-selected="false"
              className={cn(
                "palette-item flex w-full items-center justify-between gap-4 rounded-xl border border-transparent bg-transparent px-3 py-2.5 text-left",
                "hover:border-[var(--cor-borda)] hover:bg-[var(--cor-primaria-suave)]",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] focus-visible:ring-offset-1",
                "motion-reduce:transition-none"
              )}
              onClick={() => ir(a.href)}
            >
              <span className="palette-item-label truncate text-sm font-semibold text-[var(--cor-texto)]">{a.label}</span>
              <span className="palette-item-hint hidden shrink-0 text-xs text-[var(--cor-texto-suave)] sm:inline">{a.href}</span>
            </button>
          ))}
          {filtrados.length === 0 && (
            <p className="texto-suave px-3 py-4 text-sm text-[var(--cor-texto-suave)]">
              Nenhum atalho — pressione Enter para buscar “{q}”.
            </p>
          )}
        </div>
        <p className="palette-rodape border-t border-[var(--cor-borda)] px-4 py-2.5 text-xs text-[var(--cor-texto-suave)]">
          ↵ buscar · Esc fechar · ⌘K reabrir
        </p>
      </div>
    </div>
  );
}
