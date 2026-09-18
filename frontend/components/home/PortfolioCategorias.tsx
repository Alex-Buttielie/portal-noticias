"use client";
import { memo, useMemo, useState } from "react";
import Link from "next/link";
import { LayoutGrid } from "lucide-react";
import type { FeedEntrada } from "@/lib/api";
import {
  agruparPorEstado,
  lerSinaisLocais,
  selecionarPortfolio,
  sinaisNeutros,
} from "@/lib/editorial";
import { useHidratado } from "@/lib/hooks/use-hidratado";
import { NewsCard } from "./NewsCard";

interface PortfolioCategoriasProps {
  feed: FeedEntrada[];
  maxCategorias: number;
  porCategoria: number;
  passo: number;
  categoriaBuscada?: string | null;
  salvos: Set<string>;
  onToggleSalvar: (entrada: FeedEntrada) => void;
}

/**
 * Portfólio dinâmico de categorias — seleção por pesquisas, acessos,
 * crescimento e engajamento (ver lib/editorial.selecionarPortfolio).
 * N notícias por bloco sem restrição fixa, "Ver todas" claro por categoria e
 * "Veja mais" contextual com contagem ("Ver todas de Política (12)",
 * "Mais de GO (5)"). Navegação por link/expansão inline — sem modal.
 */
export const PortfolioCategorias = memo(function PortfolioCategorias({
  feed,
  maxCategorias,
  porCategoria,
  passo,
  categoriaBuscada,
  salvos,
  onToggleSalvar,
}: PortfolioCategoriasProps) {
  const [expandidos, setExpandidos] = useState<Record<string, number>>({});
  // Sinais locais (localStorage) só após hidratar — senão a seleção diverge
  // do SSR e quebra a hidratação. Ver `useHidratado`.
  const hidratado = useHidratado();

  const blocos = useMemo(
    () =>
      selecionarPortfolio(
        feed,
        hidratado ? lerSinaisLocais(categoriaBuscada) : sinaisNeutros(categoriaBuscada),
        maxCategorias
      ),
    [feed, categoriaBuscada, maxCategorias, hidratado]
  );
  const estados = useMemo(() => agruparPorEstado(feed), [feed]);

  if (blocos.length === 0) return null;

  const alternar = (categoria: string, total: number) => {
    setExpandidos((prev) => {
      const atual = prev[categoria] ?? porCategoria;
      const proximo = atual >= total ? porCategoria : Math.min(total, atual + passo);
      return { ...prev, [categoria]: proximo };
    });
  };

  return (
    <section aria-label="Portfólio por editorias" className="w-full max-w-full space-y-6 overflow-x-clip">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 text-lg font-bold text-[var(--cor-texto)]">
          <LayoutGrid className="h-5 w-5 text-[var(--cor-primaria)]" aria-hidden />
          Por editoria
        </h2>
        <Link href="/editorias" className="text-sm font-medium text-[var(--cor-primaria)] hover:underline">
          Ver todas →
        </Link>
      </div>

      {blocos.map((bloco) => {
        const visiveis = expandidos[bloco.categoria] ?? porCategoria;
        const lista = bloco.itens.slice(0, visiveis);
        const restantes = bloco.total - lista.length;
        return (
          <div key={bloco.categoria} className="w-full min-w-0 space-y-3 overflow-hidden rounded-[var(--raio-lg)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] p-4 shadow-[var(--sombra-1)] md:p-5">
            <div className="flex min-w-0 flex-wrap items-baseline justify-between gap-2">
              <h3 className="min-w-0 break-words text-base font-bold capitalize text-[var(--cor-texto)]">
                {bloco.categoria}{" "}
                <span className="ml-1 rounded-full bg-[var(--cor-fundo-elevado)] px-2 py-0.5 text-xs font-semibold text-[var(--cor-texto-suave)]">
                  {bloco.total}
                </span>
              </h3>
              <p className="text-xs text-[var(--cor-texto-suave)]">{bloco.motivo}</p>
            </div>
            <div className="grid min-w-0 grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {lista.map((entrada) => (
                <NewsCard
                  key={`port-${bloco.categoria}-${entrada.tipo}-${entrada.id}`}
                  entrada={entrada}
                  variante="secundaria"
                  salvo={salvos.has(`${entrada.tipo}-${entrada.id}`)}
                  onToggleSalvar={onToggleSalvar}
                />
              ))}
            </div>
            <div className="flex flex-wrap items-center gap-2 border-t border-[var(--cor-borda)] pt-3 text-sm">
              {restantes > 0 && (
                <button
                  type="button"
                  onClick={() => alternar(bloco.categoria, bloco.total)}
                  aria-expanded={visiveis >= bloco.total}
                  className="rounded-full border border-[var(--cor-borda)] px-3 py-1.5 text-xs font-medium text-[var(--cor-texto)] hover:bg-[var(--cor-fundo-elevado)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]"
                >
                  Mostrar mais ({Math.min(passo, restantes)} de {restantes})
                </button>
              )}
              {visiveis > porCategoria && (
                <button
                  type="button"
                  onClick={() => setExpandidos((prev) => ({ ...prev, [bloco.categoria]: porCategoria }))}
                  className="rounded-full border border-[var(--cor-borda)] px-3 py-1.5 text-xs font-medium text-[var(--cor-texto-suave)] hover:bg-[var(--cor-fundo-elevado)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]"
                >
                  Mostrar menos
                </button>
              )}
              <Link
                href={`/categoria/${encodeURIComponent(bloco.categoria)}`}
                className="ml-auto inline-flex items-center gap-1 text-xs font-medium capitalize text-[var(--cor-primaria)] hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]"
              >
                Ver todas de {bloco.categoria} ({bloco.total}) →
              </Link>
            </div>
          </div>
        );
      })}

      {estados.length > 0 && (
        <nav aria-label="Veja mais por localidade" className="flex flex-wrap items-center gap-2 rounded-[var(--raio-lg)] border border-dashed border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] px-4 py-3">
          <span className="text-xs font-semibold uppercase tracking-wide text-[var(--cor-texto-suave)]">Veja mais:</span>
          {estados.map(({ estado, total }) => (
            <Link
              key={estado}
              href={`/buscar?busca=${encodeURIComponent(estado)}`}
              className="rounded-full border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] px-3 py-1.5 text-xs font-medium text-[var(--cor-texto)] hover:bg-[var(--cor-primaria-suave)] hover:text-[var(--cor-primaria)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]"
            >
              Mais de {estado} ({total})
            </Link>
          ))}
        </nav>
      )}
    </section>
  );
});
