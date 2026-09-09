"use client";

import { useState } from "react";
import type { FeedEntrada } from "@/lib/api";
import * as bookmarks from "@/lib/bookmarks";
import { useToast } from "@/components/ToastProvider";

/** Alterna "salvar para ler depois" — só localStorage, resposta instantânea. */
export default function BotaoSalvar({ entrada }: { entrada: FeedEntrada }) {
  const { notificar } = useToast();
  const [salvo, setSalvo] = useState(() => bookmarks.estaSalvo(entrada));

  function aoClicar(evento: React.MouseEvent) {
    evento.preventDefault();
    evento.stopPropagation();
    const novoEstado = bookmarks.alternarSalvo(entrada);
    setSalvo(novoEstado);
    notificar(
      novoEstado ? "Salvo para ler depois." : "Removido dos salvos.",
      novoEstado ? "sucesso" : "info"
    );
  }

  return (
    <button
      type="button"
      className={`botao-salvar${salvo ? " botao-salvar--ativo" : ""}`}
      aria-pressed={salvo}
      onClick={aoClicar}
    >
      <span aria-hidden="true">{salvo ? "★" : "☆"}</span>
      {salvo ? "Salvo" : "Salvar para depois"}
    </button>
  );
}
