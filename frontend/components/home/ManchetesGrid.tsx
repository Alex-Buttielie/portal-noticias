"use client";
import { memo } from "react";
import Link from "next/link";
import type { FeedEntrada } from "@/lib/api";
import { NewsCard } from "./NewsCard";
import { ManchetePrincipalSlider } from "./ManchetePrincipalSlider";

/** Quantas manchetes entram no slider de destaque (H-01) — sugestão do
 * contrato (3-5), limitada também pelo total disponível. */
const MAX_SLIDES_DESTAQUE = 5;

/** Quantas manchetes extras preenchem a coluna do destaque abaixo do
 * slider no desktop (lg+) — a coluna de secundárias costuma ser mais alta
 * que o card do slider (`lg:items-stretch` só estica o grid, não o
 * conteúdo), deixando espaço ocioso em branco até "Ver todas as
 * manchetes". Some em telas menores, onde as colunas empilham e esse
 * espaço não existe. */
const MAX_EXTRAS_DESTAQUE = 3;

interface ManchetesGridProps {
  itens: FeedEntrada[];
  limiteSecundarias: number;
  salvos: Set<string>;
  onToggleSalvar: (entrada: FeedEntrada) => void;
}

/**
 * Hierarquia editorial: 1 destaque (imagem grande) + N secundárias numa
 * lista densa ao lado — padrão "Principais notícias" do Google Notícias
 * (manchete + outras coberturas da rodada em linha, sem imagem dominante).
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
  // H-01: as primeiras N manchetes giram no slider de destaque; as
  // próximas (desktop) preenchem o espaço ocioso abaixo dele; o restante
  // segue para a lista densa de secundárias — sem repetir nenhuma entrada.
  const totalSlides = Math.max(1, Math.min(MAX_SLIDES_DESTAQUE, itens.length));
  const slidesDestaque = itens.slice(0, totalSlides);
  const restoAposSlides = itens.slice(totalSlides);
  const extras = restoAposSlides.slice(0, MAX_EXTRAS_DESTAQUE);
  const resto = restoAposSlides.slice(extras.length);
  const secundarias = resto.slice(0, limiteSecundarias);
  const excedentes = resto.length - secundarias.length;

  return (
    <section aria-label="Manchetes" className="space-y-4">
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1.4fr_1fr] lg:items-stretch">
        <div className="flex min-w-0 flex-col gap-4">
          <ManchetePrincipalSlider
            itens={slidesDestaque}
            salvos={salvos}
            onToggleSalvar={onToggleSalvar}
          />
          {extras.length > 0 && (
            <div className="hidden min-w-0 rounded-[var(--raio-lg)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] px-4 lg:block">
              {extras.map((entrada) => (
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
        </div>
        {secundarias.length > 0 && (
          <div className="min-w-0 rounded-[var(--raio-lg)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] px-4">
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
      </div>
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
