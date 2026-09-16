const fs = require('fs');
const content = `"use client";

import Link from "next/link";
import { useState, useEffect, useRef, useCallback } from "react";
import * as api from "@/lib/api";
import * as intencao from "@/lib/intent";
import * as bookmarks from "@/lib/bookmarks";
import { useToast } from "@/components/ToastProvider";
import PorQueEstouVendoIsso from "@/components/PorQueEstouVendoIsso";
import BlocoEditoria from "@/components/BlocoEditoria";
import { Button } from "@/components/ui/button";
import { HorizontalNewsCard, NewsCard } from "@/components/ui/Cards";
import { EmptyState, ErrorState } from "@/components/ui/Estados";
import { SearchBar } from "@/components/ui/SearchBar";
import { useFeed, useOnboarding, usePublicacoes } from "@/lib/queries";
import { categoriasPorAfinidade, ordenarPorGosto, temSinalDeGosto } from "@/lib/personalizar";
import { CartaoEsqueleto, SkeletonLista } from "@/components/CartaoEsqueleto";
import { cn } from "@/lib/utils";

function agruparPorCategoriaCliente(itens: api.FeedEntrada[]): Record<string, api.FeedEntrada[]> {
  const g: Record<string, api.FeedEntrada[]> = {};
  for (const it of itens) {
    const cat = (it.categoria || "geral").toLowerCase();
    if (!g[cat]) g[cat] = [];
    g[cat].push(it);
  }
  return g;
}

function chaveDaEntrada(e: api.FeedEntrada): string {
  return \`${e.tipo}-${e.id}\`;
}

function motivosDaEntrada(e: api.FeedEntrada, buscaAtiva: string, leiturasPorCategoria: number): string[] {
  const m: string[] = [];
  if (e.urgente) m.push("Marcado como urgente pela redacao.");
  if (e.numero_fontes >= 3) m.push(\`Confirmado por ${e.numero_fontes} fontes diferentes.\`);
  if (buscaAtiva) m.push(\`Corresponde a sua busca por "${buscaAtiva}".\`);
  if (leiturasPorCategoria >= 2 && e.categoria)
    m.push(\`Voce ja leu ${leiturasPorCategoria} noticias de ${e.categoria} nesta sessao.\`);
  if (m.length === 0) m.push("Publicado recentemente no feed geral.");
  return m;
}

function agruparPorCategoria(itens: api.FeedEntrada[]): Record<string, api.FeedEntrada[]> {
  const g: Record<string, api.FeedEntrada[]> = {};
  for (const it of itens) {
    const cat = (it.categoria || "geral").toLowerCase();
    if (!g[cat]) g[cat] = [];
    g[cat].push(it);
  }
  return g;
}

interface HomeMainProps {
  inicial: {
    feed: api.FeedResposta;
    urgentes: api.FeedEntrada[];
    maisLidas: api.FeedEntrada[];
    onboarding: { interesses: string[] };
  };
}

export default function HomeMain({ inicial }: HomeMainProps) {
  const { notificar } = useToast();
  const [categoria, setCategoria] = useState("");
  const [buscaAtiva, setBuscaAtiva] = useState("");
  const [categoriaPreferida, setCategoriaPreferida] = useState<intencao.CategoriaPreferida | null>(null);
  const [sugestaoDispensada, setSugestaoDispensada] = useState(false);
  const [verSalvos, setVerSalvos] = useState(false);
  const [salvos, setSalvos] = useState<api.FeedEntrada[]>([]);
  const sentinelaRef = useRef<HTMLDivElement | null>(null);

  const feed = useFeed({ categoria: categoria || undefined, busca: buscaAtiva || undefined });
  const itens = (feed.data?.pages ?? []).flatMap((p) => p.results);

  useEffect(() => {
    if (verSalvos) setSalvos(bookmarks.obterSalvos());
  }, [verSalvos]);

  useEffect(() => {
    if (!feed.hasNextPage || feed.isFetchingNextPage || feed.isLoading) return;
    const el = sentinelaRef.current;
    if (!el) return;
    const obs = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting) void feed.fetchNextPage();
      },
      { rootMargin: "400px" }
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, [feed.hasNextPage, feed.isFetchingNextPage, feed.isLoading, itens.length]);

  const aoBuscar = useCallback((termo: string) => {
    setBuscaAtiva(termo);
    setSugestaoDispensada(false);
  }, []);

  const modoRio = !categoria && !buscaAtiva && !verSalvos;
  const perfilGosto = { interesses: inicial.onboarding.interesses };
  const rioPessoal = modoRio && temSinalDeGosto(perfilGosto);
  const paraVoce = rioPessoal ? ordenarPorGosto(itens, perfilGosto).slice(0, 6) : [];
  const afinidade = categoriasPorAfinidade(perfilGosto);
  const grupos = modoRio ? agruparPorCategoria(itens) : {};
  const categoriasComConteudo = Object.keys(grupos).sort((a, b) => {
    const ia = afinidade.indexOf(a.toLowerCase());
    const ib = afinidade.indexOf(b.toLowerCase());
    return (ia === -1 ? 999 : ia) - (ib === -1 ? 999 : ib);
  }).slice(0, 3);
  const comunidadeQuery = usePublicacoes({ destaque: true, enabled: modoRio });
  const comunidadeTeaser = (comunidadeQuery.data ?? []).slice(0, 3);

  if (verSalvos) {
    return (
      <div className="min-w-0 space-y-4 overflow-hidden">
        <header className={cn("seu-rio", "mb-6 min-w-0 space-y-2")}>
          <p className="text-xs font-bold uppercase tracking-[0.14em] text-[var(--cor-primaria)] secao-eyebrow">Leitura salva</p>
          <h1 className="break-words font-[var(--fonte-titulo)] text-3xl font-extrabold tracking-[-0.03em] text-wrap-balance seu-rio__titulo secao-titulo">Salvos para depois</h1>
          <p className="max-w-[62ch] break-words text-sm text-[var(--cor-texto-suave)] texto-suave">Sua lista de leitura para depois, guardada neste aparelho.</p>
        </header>
        <div className="flex justify-end controles-salvos">
          <Button variante="secundaria" onClick={() => setVerSalvos(false)}>[Voltar] Voltar ao feed</Button>
        </div>
        {salvos.length === 0 ? (
          <EmptyState titulo="Nenhuma noticia salva ainda" descricao="Toque em \"Salvar para depois\" em qualquer noticia para le-la aqui." />
        ) : (
          <div className={cn("grade-noticias", "grid w-full max-w-full grid-cols-1 gap-4 overflow-hidden break-words sm:grid-cols-2 lg:grid-cols-3")}>
            {salvos.map((entrada) => (
              <div key={chaveDaEntrada(entrada)} className="min-w-0 overflow-hidden break-words">
                <NewsCard entrada={entrada} />
              </div>
            ))}
          </div>
        )}
      </div>
    );
  }

  return (
    <>
      {!modoRio && (
        <div className="flex flex-wrap items-end gap-3">
          <div className="min-w-0 flex-1">
            <SearchBar valorInicial={buscaAtiva} aoBuscar={aoBuscar} />
          </div>
          <Button variante="secundaria" onClick={() => setVerSalvos(true)}>
            [*] Salvos ({bookmarks.obterSalvos().length})
          </Button>
        </div>
      )}

      <div className="space-y-1" role="group" aria-label="Contexto da listagem">
        {categoria && (
          <p className="text-sm text-[var(--cor-texto-suave)]">
            Filtrando por <strong className="text-[var(--cor-texto)]">{categoria}</strong>{" "}
            <button type="button" className="bg-transparent p-0 font-inherit text-[var(--cor-primaria)] underline hover:text-[var(--cor-primaria-hover)]" onClick={() => setCategoria("")}>limpar filtro</button>
          </p>
        )}
        {buscaAtiva && (
          <p className="text-sm text-[var(--cor-texto-suave)]">
            Busca por <strong className="text-[var(--cor-texto)]">"{buscaAtiva}"</strong>{" "}
            <button type="button" className="bg-transparent p-0 font-inherit text-[var(--cor-primaria)] underline hover:text-[var(--cor-primaria-hover)]" onClick={() => setBuscaAtiva("")}>limpar busca</button>
          </p>
        )}
      </div>

      {!modoRio && (
        <header className={cn("seu-rio", "mb-6 space-y-2")}>
          <p className="text-xs font-bold uppercase tracking-[0.14em] text-[var(--cor-primaria)] secao-eyebrow">Filtro do rio</p>
          <h1 className="font-[var(--fonte-titulo)] text-3xl font-extrabold tracking-[-0.03em] text-wrap-balance seu-rio__titulo">
            {categoria && buscaAtiva ? \`${categoria} - "${buscaAtiva}"\` : categoria || \`"${buscaAtiva}"\`}
          </h1>
          <p className="max-w-[62ch] text-sm text-[var(--cor-texto-suave)]">Um recorte do rio cronologico - limpe o filtro para voltar ao rio completo.</p>
        </header>
      )}

      {feed.isLoading && <SkeletonLista quantidade={6} />}

      <div aria-live="polite">
        {feed.isError && (
          <ErrorState
            mensagem={feed.error instanceof api.ApiError ? feed.error.message : "Nao foi possivel carregar o feed."}
            aoTentarNovamente={() => void feed.refetch()}
          />
        )}
        {!feed.isLoading && !feed.isError && itens.length === 0 && !modoRio && (
          <EmptyState titulo="Nenhuma noticia encontrada" descricao="Tente outra categoria ou termo de busca." />
        )}
      </div>

      {modoRio && (
        <>
          {rioPessoal && paraVoce.length > 0 && (
            <section className="space-y-4 secao-bloco" aria-label="Para voce">
              <div className="flex items-baseline gap-3 border-b-2 border-[var(--cor-borda)] pb-3">
                <p className="text-xs font-bold uppercase tracking-[0.14em] text-[var(--cor-primaria)]">Para voce</p>
                <h2 className="font-[var(--fonte-titulo)] text-xl font-extrabold tracking-tight">No seu gosto</h2>
              </div>
              <div className={cn("grade-noticias", "grid w-full max-w-full grid-cols-1 gap-4 overflow-hidden sm:grid-cols-2 lg:grid-cols-3")}>
                {paraVoce.map((entrada) => (
                  <div key={chaveDaEntrada(entrada)} className="min-w-0 space-y-2 overflow-hidden break-words">
                    <NewsCard entrada={entrada} />
                    <PorQueEstouVendoIsso
                      motivos={motivosDaEntrada(entrada, buscaAtiva, intencao.obterLeiturasDaCategoria(entrada.categoria))}
                    />
                  </div>
                ))}
              </div>
            </section>
          )}

          <section className="min-w-0 space-y-4 overflow-hidden" id="ultimas" aria-label="Ultimas noticias">
            <div className="flex items-baseline gap-3 border-b-2 border-[var(--cor-borda)] pb-3">
              <p className="text-xs font-bold uppercase tracking-[0.14em] text-[var(--cor-primaria)]">O rio</p>
              <h2 className="font-[var(--fonte-titulo)] text-xl font-extrabold tracking-tight">Ultimas noticias</h2>
            </div>
            {itens.length === 0 ? (
              <p className="text-sm text-[var(--cor-texto-suave)]">Mais noticias aparecerao aqui.</p>
            ) : (
              <div className={cn("lista-compacta", "flex min-w-0 flex-col gap-3 overflow-hidden")}>
                {itens.slice(0, 12).map((entrada, i) => (
                  <HorizontalNewsCard key={chaveDaEntrada(entrada)} entrada={entrada} posicao={i + 1} />
                ))}
              </div>
            )}
          </section>

          {categoriasComConteudo.map((cat) => (
            <BlocoEditoria key={cat} categoria={cat} itens={grupos[cat]} onVerTodas={() => setCategoria(cat)} carrosselMobile />
          ))}

          {comunidadeTeaser.length > 0 && (
            <section className="min-w-0 space-y-4 overflow-hidden break-words" aria-label="Da comunidade">
              <div className="flex flex-wrap items-baseline gap-3 border-b-2 border-[var(--cor-borda)] pb-3">
                <p className="text-xs font-bold uppercase tracking-[0.14em] text-[var(--cor-primaria)]">Vozes</p>
                <h2 className="font-[var(--fonte-titulo)] text-xl font-extrabold tracking-tight">Da comunidade</h2>
                <Link href="/comunidade" className="ml-auto text-sm font-medium text-[var(--cor-primaria)] hover:underline">Ver tudo -></Link>
              </div>
              <div className={cn("grade-noticias", "grid w-full max-w-full grid-cols-1 gap-4 overflow-hidden break-words sm:grid-cols-2 lg:grid-cols-3")}>
                {comunidadeTeaser.map((pub) => (
                  <article key={pub.id} className="min-w-0 overflow-hidden break-words rounded-xl border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] p-4 shadow-sm transition-colors hover:border-[var(--cor-primaria)] motion-reduce:transition-none">
                    <div className="mb-2 flex flex-wrap gap-1.5">
                      <span className="inline-flex items-center rounded-full border border-transparent bg-[var(--cor-primaria-suave)] px-2 py-0.5 text-xs font-semibold text-[var(--cor-primaria)]">
                        {pub.tipo === "opiniao" ? "Opiniao" : "Analise"}
                      </span>
                    </div>
                    <Link href={\`/comunidade/${pub.id}\`} className="no-underline hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]">
                      <h3 className="break-words font-[var(--fonte-titulo)] text-base font-semibold leading-tight line-clamp-3">{pub.titulo}</h3>
                    </Link>
                    <p className="mt-1 break-words text-sm text-[var(--cor-texto-suave)]">por {pub.autor_nome}</p>
                  </article>
                ))}
              </div>
            </section>
          )}
        </>
      )}

      {!modoRio && !feed.isLoading && !feed.isError && itens.length > 0 && (
        <div className={cn("grade-noticias", "grid w-full max-w-full grid-cols-1 gap-4 overflow-hidden break-words sm:grid-cols-2 lg:grid-cols-3")}>
          {itens.map((entrada) => (
            <div key={chaveDaEntrada(entrada)} className="min-w-0 space-y-2 overflow-hidden break-words">
              <NewsCard entrada={entrada} />
              <PorQueEstouVendoIsso
                motivos={motivosDaEntrada(entrada, buscaAtiva, intencao.obterLeiturasDaCategoria(entrada.categoria))}
              />
            </div>
          ))}
        </div>
      )}

      {feed.isFetchingNextPage && <SkeletonLista quantidade={2} />}

      {!feed.isLoading && !feed.isError && feed.hasNextPage && (
        <div className="flex justify-center py-4" ref={sentinelaRef} aria-live="polite">
          <Button variante="secundaria" onClick={() => void feed.fetchNextPage()} carregando={feed.isFetchingNextPage}>
            Carregar mais noticias
          </Button>
        </div>
      )}
    </>
  );
}
`;
fs.writeFileSync('components/HomeMain.tsx', content, 'utf8');
console.log('File written successfully');