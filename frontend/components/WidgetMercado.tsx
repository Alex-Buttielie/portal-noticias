"use client";
import { useEffect, useState } from "react";
import { TrendingUp, TrendingDown } from "lucide-react";
import { obterIndicesMercado, type IndiceMercado } from "@/lib/api";

function formatarPreco(valor: number): string {
  return valor.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

/**
 * Índices de mercado (Ibovespa etc.) — inspirado no widget de cotações do
 * Google Notícias. Some sem avisar nada quando o backend não tem
 * `BRAPI_API_KEY` configurada (recurso desligado, não erro).
 */
export function WidgetMercado() {
  const [indices, setIndices] = useState<IndiceMercado[]>([]);

  useEffect(() => {
    let ativo = true;
    obterIndicesMercado().then((lista) => {
      if (ativo) setIndices(lista);
    });
    return () => {
      ativo = false;
    };
  }, []);

  if (indices.length === 0) return null;

  return (
    <div className="rounded-[var(--raio-lg)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] p-4" aria-label="Cotações de mercado">
      <h3 className="mb-3 text-sm font-bold text-[var(--cor-texto)]">Mercado</h3>
      <ul className="space-y-2">
        {indices.map((indice) => {
          const subiu = indice.variacao_percentual >= 0;
          return (
            <li key={indice.simbolo} className="flex items-center justify-between gap-2 text-sm">
              <span className="font-medium text-[var(--cor-texto)]">{indice.nome}</span>
              <span className="flex items-center gap-2 tabular-nums">
                <span className="text-[var(--cor-texto-suave)]">{formatarPreco(indice.preco)}</span>
                <span className={subiu ? "flex items-center gap-0.5 text-[var(--cor-sucesso)]" : "flex items-center gap-0.5 text-[var(--cor-erro)]"}>
                  {subiu ? <TrendingUp className="h-3.5 w-3.5" aria-hidden /> : <TrendingDown className="h-3.5 w-3.5" aria-hidden />}
                  {subiu ? "+" : ""}
                  {indice.variacao_percentual.toFixed(2)}%
                </span>
              </span>
            </li>
          );
        })}
      </ul>
      <p className="mt-3 text-[10px] text-[var(--cor-texto-suave)]">Cotações com atraso — não use para decisão de investimento. Fonte: Brapi.</p>
    </div>
  );
}
