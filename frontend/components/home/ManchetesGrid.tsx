"use client";
import { memo } from "react";
import Link from "next/link";
import type { FeedEntrada } from "@/lib/api";
import { NewsCard } from "./NewsCard";

interface ManchetesGridProps {
  itens: FeedEntrada[];
  limiteSecundarias: number;
  salvos: Set<string>;
  onToggleSalvar: (entrada: FeedEntrada) => void;
}

/**
 * Hierarquia editorial: 1 destaque + N secundárias em grid denso.
 * Card clicável, sem botões grandes. Quantidade configurável.
 */
export const ManchetesGrid = memo(function ManchetesGrid({ itens, limiteSecundarias, salvos, onToggleSalvar }: ManchetesGridProps) {
  if (itens.length === 0) {
    return (
      <div className="rounded-[var(--raio-lg)] border border-dashed border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] p-8 text-center">
        <p className="text-sm font-medium text-[var(--cor-texto)]">Nenhuma manchete por aqui</p>
        <p className="mt-1 text-sm text-[var(--cor-texto-suave)]">
          Tente outro filtro ou veja o <Link href="/arquivo" className="font-medium text-[var(--cor-primaria)] underline">arquivo</Link>.
        </p>
      </div>
    );
  }
  const [destaque, ...resto] = itens;
  const secundarias = resto.slice(0, limiteSecundarias);
  const excedentes = resto.length - secundarias.length;

  return (
    <section aria-label="Manchetes" className="space-y-4">
      <NewsCard
        entrada={destaque}
        variante="destaque"
        eager
        salvo={salvos.has(`${destaque.tipo}-${destaque.id}`)}
        onToggleSalvar={onToggleSalvar}
      />
      {secundarias.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {secundarias.map((entrada) => (
            <NewsCard
              key={`${entrada.tipo}-${entrada.id}`}
              entrada={entrada}
              variante="secundaria"
              salvo={salvos.has(`${entrada.tipo}-${entrada.id}`)}
              onToggleSalvar={onToggleSalvar}
            />
          ))}
        </div>
      )}
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <Link
          href="/arquivo"
          className="inline-flex items-center gap-1 font-medium text-[var(--cor-primaria)] hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]"
        >
          Ver todas as manchetes ({itens.length}
          {excedentes > 0 ? `+${excedentes} abaixo` : ""}) →
        </Link>
      </div>
    </section>
  );
});
