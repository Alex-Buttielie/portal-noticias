"use client";

import { useState } from "react";
import { Bookmark, BookmarkCheck } from "lucide-react";
import type { FeedEntrada } from "@/lib/api";
import * as bookmarks from "@/lib/bookmarks";
import { useToast } from "@/components/ToastProvider";
import { cn } from "@/lib/utils";

export default function BotaoSalvar({ entrada }: { entrada: FeedEntrada }) {
  const { notificar } = useToast();
  const [salvo, setSalvo] = useState(() => bookmarks.estaSalvo(entrada));

  function aoClicar(evento: React.MouseEvent) {
    evento.preventDefault();
    evento.stopPropagation();
    const novoEstado = bookmarks.alternarSalvo(entrada);
    setSalvo(novoEstado);
    notificar(novoEstado ? "Salvo para ler depois." : "Removido dos salvos.", novoEstado ? "sucesso" : "info");
  }

  return (
    <button
      type="button"
      aria-pressed={salvo}
      onClick={aoClicar}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] focus-visible:ring-offset-2",
        "motion-reduce:transition-none transition-colors",
        salvo
          ? "border-[var(--cor-premium)] bg-[var(--cor-premium)]/10 text-[var(--cor-premium)]"
          : "border-dashed border-[var(--cor-borda)] text-[var(--cor-texto-suave)] hover:border-[var(--cor-premium)] hover:text-[var(--cor-premium)]"
      )}
    >
      {salvo ? <BookmarkCheck className="h-3.5 w-3.5" aria-hidden="true" /> : <Bookmark className="h-3.5 w-3.5" aria-hidden="true" />}
      {salvo ? "Salvo" : "Salvar para depois"}
    </button>
  );
}
