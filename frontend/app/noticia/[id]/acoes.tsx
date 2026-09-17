"use client";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { alternarSalvo, estaSalvo, chaveDoSalvo } from "@/lib/bookmarks";
import { registrarLeitura } from "@/lib/intent";
import type { FeedEntrada } from "@/lib/api";
import { Bookmark, Share2 } from "lucide-react";
export function AcoesNoticia({ entrada }: { entrada: FeedEntrada }) {
  const [salvo, setSalvo] = useState(false);
  useEffect(() => { setSalvo(estaSalvo(entrada)); registrarLeitura(entrada.categoria); }, [entrada]);
  function onSave() { const n = alternarSalvo(entrada); setSalvo(n); }
  async function onShare() {
    const url = typeof window !== "undefined" ? window.location.href : "";
    const data = { title: entrada.titulo, text: entrada.resumo, url };
    try { if (navigator.share) await navigator.share(data); else await navigator.clipboard.writeText(url); } catch {}
  }
  return (
    <div className="flex gap-2">
      <Button variant="outline" onClick={onSave} aria-pressed={salvo} className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] min-h-[44px]">
        <Bookmark className="mr-1 h-4 w-4" fill={salvo ? "currentColor" : "none"} /> {salvo ? "Salvo" : "Salvar"}
      </Button>
      <Button variant="outline" onClick={onShare} className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] min-h-[44px]">
        <Share2 className="mr-1 h-4 w-4" /> Compartilhar
      </Button>
      <span className="sr-only" aria-live="polite">{chaveDoSalvo(entrada)}</span>
    </div>
  );
}
