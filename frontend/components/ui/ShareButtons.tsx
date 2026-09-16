"use client";

import { useState } from "react";
import { Share2, MessageCircle, Copy, Check } from "lucide-react";
import { useToast } from "@/components/ToastProvider";
import { cn } from "@/lib/utils";

interface Propriedades {
  titulo: string;
  texto?: string;
  url: string;
}

export function ShareButtons({ titulo, texto, url }: Propriedades) {
  const { notificar } = useToast();
  const [copiado, setCopiado] = useState(false);

  async function compartilharNativo() {
    try {
      if (navigator.share) {
        await navigator.share({ title: titulo, text: texto, url });
        return;
      }
      await copiarLink();
    } catch {
      // Usuário fechou o diálogo — nada a fazer.
    }
  }

  async function copiarLink() {
    try {
      await navigator.clipboard.writeText(url);
      setCopiado(true);
      notificar("Link copiado.", "sucesso");
      window.setTimeout(() => setCopiado(false), 2000);
    } catch {
      notificar("Não foi possível copiar o link.", "erro");
    }
  }

  const whatsapp = `https://wa.me/?text=${encodeURIComponent(`${titulo} ${url}`)}`;

  return (
    <div className={cn("flex flex-wrap items-center gap-2")}>
      <button
        type="button"
        className={cn(
          "inline-flex min-h-[44px] touch-manipulation items-center justify-center gap-2 rounded-full bg-[var(--cor-primaria)] px-4 text-sm font-medium text-[var(--cor-texto-invertido)]",
          "hover:bg-[var(--cor-primaria-hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] focus-visible:ring-offset-2",
          "motion-reduce:transition-none transition-colors"
        )}
        onClick={compartilharNativo}
        aria-label="Compartilhar esta notícia"
      >
        <Share2 className="h-4 w-4" aria-hidden="true" /> Compartilhar
      </button>
      <a
        className={cn(
          "inline-flex min-h-[44px] touch-manipulation items-center justify-center gap-2 rounded-full border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] px-4 text-sm font-medium text-[var(--cor-texto)]",
          "hover:bg-[var(--cor-primaria-suave)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] focus-visible:ring-offset-2",
          "motion-reduce:transition-none transition-colors"
        )}
        href={whatsapp}
        target="_blank"
        rel="noopener noreferrer"
        aria-label="Compartilhar no WhatsApp"
      >
        <MessageCircle className="h-4 w-4" aria-hidden="true" /> WhatsApp
      </a>
      <button
        type="button"
        className={cn(
          "inline-flex min-h-[44px] touch-manipulation items-center justify-center gap-2 rounded-full border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] px-4 text-sm font-medium text-[var(--cor-texto)]",
          "hover:bg-[var(--cor-primaria-suave)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] focus-visible:ring-offset-2",
          "motion-reduce:transition-none transition-colors"
        )}
        onClick={copiarLink}
        aria-label={copiado ? "Link copiado para a área de transferência" : "Copiar link desta notícia"}
        aria-live="polite"
      >
        {copiado ? <Check className="h-4 w-4 text-[var(--cor-sucesso)]" aria-hidden="true" /> : <Copy className="h-4 w-4" aria-hidden="true" />}
        {copiado ? "Copiado!" : "Copiar link"}
      </button>
    </div>
  );
}
