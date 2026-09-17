"use client";
import { useState } from "react";
import BuscaCep from "@/components/BuscaCep";
import type { EnderecoViaCep } from "@/lib/cep";
export default function ContatoCepIsland() {
  const [sel, setSel] = useState<EnderecoViaCep | null>(null);
  return (
    <div className="space-y-2">
      <p className="text-sm font-medium text-[var(--cor-texto)]">Nos informe seu CEP para direcionamento regional</p>
      <BuscaCep compact onEndereco={setSel} />
      {sel && <p className="rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] px-3 py-2 text-xs text-[var(--cor-texto-suave)]">Selecionado: {sel.logradouro ? `${sel.logradouro}, ` : ""}{sel.bairro} — {sel.localidade}/{sel.uf} ({sel.cep})</p>}
      <p className="text-xs text-[var(--cor-texto-suave)]">Usado apenas para encaminhar ao time regional — não é armazenado sem seu envio.</p>
    </div>
  );
}
