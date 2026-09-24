"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { carregarCobertura } from "@/lib/recomendacao";
import type { CoberturaCompleta as TCobertura } from "@/lib/api";
import { formatarDataHoraCompleta } from "@/lib/datas";

/**
 * FRENTE 3 — "Ver cobertura completa": fontes, horários, atualizações e
 * relacionadas do MESMO evento, com origem sempre explícita (nome da fonte
 * + link para a original). Evita duplicação: a própria entrada nunca aparece
 * nas relacionadas (garantido no backend).
 */
export function CoberturaCompleta({ tipo, id }: { tipo: "cluster" | "item"; id: number }) {
  const [aberta, setAberta] = useState(false);
  const [dados, setDados] = useState<TCobertura | null>(null);
  const [erro, setErro] = useState(false);

  useEffect(() => {
    if (!aberta || dados || erro) return;
    void carregarCobertura(tipo, id).then((c) => {
      if (c) setDados(c);
      else setErro(true);
    });
  }, [aberta, dados, erro, tipo, id]);

  if (!aberta) {
    return (
      <Button
        variant="outline"
        onClick={() => setAberta(true)}
        className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]"
      >
        Ver cobertura completa
      </Button>
    );
  }

  if (erro) return <p className="text-sm text-[var(--cor-texto-suave)]">Cobertura indisponível no momento.</p>;
  if (!dados) return <p className="animate-pulse text-sm text-[var(--cor-texto-suave)]">Carregando cobertura…</p>;

  return (
    <div className="space-y-4">
      <Card className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
        <CardContent className="p-4">
          <p className="mb-2 text-sm font-bold text-[var(--cor-texto)]">
            Cobertura completa • {dados.numero_fontes} {dados.numero_fontes === 1 ? "fonte" : "fontes"} •{" "}
            {dados.total_atualizacoes} {dados.total_atualizacoes === 1 ? "atualização" : "atualizações"}
          </p>
          <ol className="space-y-2">
            {dados.atualizacoes.map((a) => (
              <li key={a.url_fonte_original} className="flex flex-col gap-0.5 rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-2.5 text-sm">
                <span className="font-medium text-[var(--cor-texto)]">{a.titulo}</span>
                <span className="text-xs text-[var(--cor-texto-suave)]">
                  {formatarDataHoraCompleta(a.timestamp)} • Fonte:{" "}
                  <a href={a.url_fonte_original} target="_blank" rel="noopener noreferrer" className="text-[var(--cor-primaria)] hover:underline">
                    {a.nome_fonte}
                  </a>
                </span>
              </li>
            ))}
          </ol>
        </CardContent>
      </Card>

      {dados.relacionadas.length > 0 && (
        <Card className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
          <CardContent className="p-4">
            <p className="mb-2 text-sm font-bold text-[var(--cor-texto)]">Relacionadas</p>
            <ul className="space-y-2">
              {dados.relacionadas.map((r) => (
                <li key={`${r.tipo}-${r.id}`}>
                  <Link href={`/noticia/${r.id}`} className="block text-sm font-medium text-[var(--cor-texto)] hover:text-[var(--cor-primaria)]">
                    {r.titulo}
                  </Link>
                  <p className="text-xs capitalize text-[var(--cor-texto-suave)]">
                    {r.categoria} {r.motivo ? `• ${r.motivo}` : ""}
                  </p>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
