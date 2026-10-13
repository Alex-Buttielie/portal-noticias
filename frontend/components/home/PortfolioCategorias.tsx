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

      {/* `items-start`: sem isso, o CSS Grid estica cada card (align-items:
          stretch é o padrão) até a altura do vizinho mais alto da mesma
          linha — um bloco com só 1 notícia (ex. "Igor Gadelha") ficava
          esticado pra combinar com um vizinho de 3, sobrando um vão vazio
          feio dentro do card, abaixo do conteúdo real. Com `items-start`
          cada card só cresce até a altura do próprio conteúdo. */}
      <div className="grid min-w-0 grid-cols-1 items-start gap-4 md:grid-cols-2 xl:grid-cols-3">
        {blocos.map((bloco) => {
          const visiveis = expandidos[bloco.categoria] ?? porCategoria;
          const lista = bloco.itens.slice(0, visiveis);
          const restantes = bloco.total - lista.length;
          return (
            <div key={bloco.categoria} className="flex w-full min-w-0 flex-col overflow-hidden rounded-[var(--raio-lg)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] p-4 shadow-[var(--sombra-1)]">
              <Link
                href={`/categoria/${encodeURIComponent(bloco.categoria)}`}
                className="group/h mb-1 flex min-w-0 items-center justify-between gap-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] rounded-sm"
              >
                <h3 className="min-w-0 truncate text-base font-bold capitalize text-[var(--cor-texto)] group-hover/h:text-[var(--cor-primaria)]">
                  {bloco.categoria}
                </h3>
                <span className="shrink-0 text-[var(--cor-texto-suave)] group-hover/h:text-[var(--cor-primaria)]">›</span>
              </Link>
              <p className="mb-1 text-xs text-[var(--cor-texto-suave)]">{bloco.motivo}</p>
              {/* No mobile (sem espaço para o thumbnail fixo de 112px da
                  lista densa), 1 notícia por linha com a variante "grade"
                  compacta (imagem no topo), ocupando a largura inteira do
                  card — a versão em 2 colunas ainda estourava a tela em
                  dispositivos reais (classe `grid` do pai sem coluna base
                  deixava o layout inteiro largo demais, forçando o usuário
                  a dar zoom); a partir de md volta à lista densa de sempre.
                  Duas árvores CSS-condicionais (`md:hidden`/`hidden md:block`)
                  em vez de trocar a variante via JS — evita hydration
                  mismatch entre SSR e cliente por causa de media query. */}
              <div className="grid min-w-0 grid-cols-1 gap-3 md:hidden">
                {lista.map((entrada) => (
                  <NewsCard
                    key={`port-grade-${bloco.categoria}-${entrada.tipo}-${entrada.id}`}
                    entrada={entrada}
                    variante="grade"
                    salvo={salvos.has(`${entrada.tipo}-${entrada.id}`)}
                    onToggleSalvar={onToggleSalvar}
                  />
                ))}
              </div>
              <div className="hidden min-w-0 md:block">
                {lista.map((entrada) => (
                  <NewsCard
                    key={`port-lista-${bloco.categoria}-${entrada.tipo}-${entrada.id}`}
                    entrada={entrada}
                    variante="secundaria"
                    salvo={salvos.has(`${entrada.tipo}-${entrada.id}`)}
                    onToggleSalvar={onToggleSalvar}
                  />
                ))}
              </div>
              <div className="mt-2 flex flex-wrap items-center gap-2 border-t border-[var(--cor-borda)] pt-3 text-sm">
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
                  Ver todas ({bloco.total}) →
                </Link>
              </div>
            </div>
          );
        })}
      </div>

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
