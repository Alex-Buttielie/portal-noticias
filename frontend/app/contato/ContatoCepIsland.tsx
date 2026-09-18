"use client";
import { useState } from "react";
import EnderecoInteligente, { type EnderecoForm } from "@/components/EnderecoInteligente";
export default function ContatoCepIsland() {
  const [sel, setSel] = useState<EnderecoForm | null>(null);
  const resumo = sel && (sel.cidade || sel.uf || sel.cep)
    ? `${sel.logradouro ? `${sel.logradouro}${sel.numero ? `, ${sel.numero}` : ""}, ` : ""}${sel.bairro ? `${sel.bairro} — ` : ""}${sel.cidade}/${sel.uf} (${sel.cep})`
    : null;
  return (
    <div className="space-y-2">
      <p className="text-sm font-medium text-[var(--cor-texto)]">Nos informe seu endereço para direcionamento regional</p>
      <EnderecoInteligente compact onEndereco={(e) => setSel(e)} />
      {resumo && <p className="rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] px-3 py-2 text-xs text-[var(--cor-texto-suave)]">Selecionado: {resumo}</p>}
      <p className="text-xs text-[var(--cor-texto-suave)]">Usado apenas para encaminhar ao time regional — não é armazenado sem seu envio.</p>
    </div>
  );
}
