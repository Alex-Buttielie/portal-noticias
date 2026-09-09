"use client";

import { useState } from "react";
import { useToast } from "@/components/ToastProvider";

interface Propriedades {
  titulo: string;
  texto?: string;
  url: string;
}

// Ações de compartilhamento — mesma lógica (Web Share API + fallback
// copiar + WhatsApp), só rótulos acessíveis e alvos de 40px+.
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
    <div className="compartilhar" aria-label={`Compartilhar: ${titulo}`}>
      <button
        type="button"
        className="botao botao--secundaria botao--pequeno"
        style={{ minHeight: 40 }}
        onClick={compartilharNativo}
        aria-label={`Compartilhar "${titulo}"`}
      >
        <span aria-hidden="true">↗</span> Compartilhar
      </button>
      <a
        className="botao botao--fantasma botao--pequeno"
        style={{ minHeight: 40 }}
        href={whatsapp}
        target="_blank"
        rel="noopener noreferrer"
        aria-label={`Compartilhar "${titulo}" no WhatsApp`}
      >
        WhatsApp
      </a>
      <button
        type="button"
        className="botao botao--fantasma botao--pequeno"
        style={{ minHeight: 40 }}
        onClick={copiarLink}
        aria-live="polite"
        aria-label="Copiar link da notícia"
      >
        <span aria-hidden="true">{copiado ? "✓" : "⧉"}</span> {copiado ? "Copiado!" : "Copiar link"}
      </button>
    </div>
  );
}
