"use client";

import { useState } from "react";
import { useToast } from "@/components/ToastProvider";

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
    <div className="compartilhar">
      <button type="button" className="botao botao--secundaria botao--pequeno" onClick={compartilharNativo}>
        Compartilhar
      </button>
      <a className="botao botao--fantasma botao--pequeno" href={whatsapp} target="_blank" rel="noopener noreferrer">
        WhatsApp
      </a>
      <button type="button" className="botao botao--fantasma botao--pequeno" onClick={copiarLink}>
        {copiado ? "Copiado!" : "Copiar link"}
      </button>
    </div>
  );
}
