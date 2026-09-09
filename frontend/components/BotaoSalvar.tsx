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
      style={{ minHeight: 40 }}
      aria-pressed={salvo}
      aria-label={salvo ? `Remover "${entrada.titulo}" dos salvos` : `Salvar "${entrada.titulo}" para ler depois`}
      title={salvo ? "Remover dos salvos" : "Salvar para ler depois"}
      onClick={aoClicar}
    >
      <span aria-hidden="true">{salvo ? "★" : "☆"}</span>
      {salvo ? "Salvo" : "Salvar para depois"}
    </button>
  );
}
