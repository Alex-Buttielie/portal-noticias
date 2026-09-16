"use client";

import { Suspense, useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import * as api from "@/lib/api";
import * as intencao from "@/lib/intent";
import * as bookmarks from "@/lib/bookmarks";
import { useToast } from "@/components/ToastProvider";
import PorQueEstouVendoIsso from "@/components/PorQueEstouVendoIsso";
import MaisLidas from "@/components/MaisLidas";
import BlocoEditoria from "@/components/BlocoEditoria";
import { Button } from "@/components/ui/Button";
import { HorizontalNewsCard, NewsCard } from "@/components/ui/Cards";
import { EmptyState, ErrorState, SkeletonLista } from "@/components/ui/Estados";
import { SearchBar } from "@/components/ui/SearchBar";
import { useFeed, useOnboarding, usePublicacoes } from "@/lib/queries";
import { categoriasPorAfinidade, ordenarPorGosto, temSinalDeGosto } from "@/lib/personalizar";
import { cn } from "@/lib/utils";

const INTERVALO_VERIFICACAO_NOVIDADES_MS = 60000;

function chaveDaEntrada(e: api.FeedEntrada): string {
  return `${e.tipo}-${e.id}`;
}

function motivosDaEntrada(e: api.FeedEntrada, buscaAtiva: string, leiturasPorCategoria: number): string[] {
  const m: string[] = [];
  if (e.urgente) m.push("Marcado como urgente pela redação.");
  if (e.numero_fontes >= 3) m.push(`Confirmado por ${e.numero_fontes} fontes diferentes.`);
  if (buscaAtiva) m.push(`Corresponde à sua busca por "${buscaAtiva}".`);
  if (leiturasPorCategoria >= 2 && e.categoria)
    m.push(`Você já leu ${leiturasPorCategoria} notícias de ${e.categoria} nesta sessão.`);
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

function PaginaFeedInner() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const { notificar } = useToast();
  const [categoria, setCategoria] = useState(() => searchParams.get("categoria") || "");
  const [buscaAtiva, setBuscaAtiva] = useState(() => searchParams.get("busca") || "");
  const [categoriaPreferida, setCategoriaPreferida] = useState<intencao.CategoriaPreferida | null>(null);
  const [sugestaoDispensada, setSugestaoDispensada] = useState(false);
  const [novidadeDisponivel, setNovidadeDisponivel] = useState(false);
  const [verSalvos, setVerSalvos] = useState(false);
  const [salvos, setSalvos] = useState<api.FeedEntrada[]>([]);
  const [emailNewsletter, setEmailNewsletter] = useState("");
  const [carregandoNewsletter, setCarregandoNewsletter] = useState(false);
  const sentinelaRef = useRef<HTMLDivElement | null>(null);
  const primeiraChaveRef = useRef<string | null>(null);

  const feed = useFeed({ categoria: categoria || undefined, busca: buscaAtiva || undefined });
  const itens = (feed.data?.pages ?? []).flatMap((p) => p.results);
  const exibirPublicidade = feed.data?.pages[0]?.exibir_publicidade ?? true;

  useEffect(() => {
    const cat = searchParams.get("categoria") || "";
    const b = searchParams.get("busca") || "";
    if (cat !== categoria) setCategoria(cat);
    if (b !== buscaAtiva) setBuscaAtiva(b);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  useEffect(() => {
    const p = new URLSearchParams(searchParams.toString());
    let mudou = false;
    if (buscaAtiva) {
      if (p.get("busca") !== buscaAtiva) { p.set("busca", buscaAtiva); mudou = true; }
    } else if (p.has("busca")) { p.delete("busca"); mudou = true; }
    if (categoria) {
      if (p.get("categoria") !== categoria) { p.set("categoria", categoria); mudou = true; }
    } else if (p.has("categoria")) { p.delete("categoria"); mudou = true; }
    if (mudou) {
      const qs = p.toString();
      router.replace(qs ? `/?${qs}` : "/", { scroll: false });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [buscaAtiva, categoria]);

  useEffect(() => {
    primeiraChaveRef.current = itens[0] ? chaveDaEntrada(itens[0]) : null;
    setCategoriaPreferida(intencao.obterCategoriaPreferida());
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [feed.dataUpdatedAt]);

  useEffect(() => {
    const verificar = () => {
      if (document.hidden) return;
      api
        .obterFeed({ categoria: categoria || undefined, busca: buscaAtiva || undefined, page: 1 })
        .then((r) => {
          const chaveNova = r.results[0] ? chaveDaEntrada(r.results[0]) : null;
          if (chaveNova && chaveNova !== primeiraChaveRef.current) setNovidadeDisponivel(true);
        })
        .catch(() => {});
    };
    const id = window.setInterval(verificar, INTERVALO_VERIFICACAO_NOVIDADES_MS);
    return () => window.clearInterval(id);
  }, [categoria, buscaAtiva]);

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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [feed.hasNextPage, feed.isFetchingNextPage, feed.isLoading, itens.length]);

  useEffect(() => {
    if (verSalvos) setSalvos(bookmarks.obterSalvos());
  }, [verSalvos]);

  const aoBuscar = useCallback((termo: string) => {
    setBuscaAtiva(termo);
    setNovidadeDisponivel(false);
    setSugestaoDispensada(false);
  }, []);

  function aplicarNovidade() {
    setNovidadeDisponivel(false);
    void feed.refetch();
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  const mostrarSugestao = !sugestaoDispensada && !categoria && !buscaAtiva && categoriaPreferida !== null;
  const modoRio = !categoria && !buscaAtiva && !verSalvos;
  const onboarding = useOnboarding();
  const perfilGosto = { interesses: onboarding.data?.interesses ?? [] };
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

  async function onNewsletter(e: FormEvent) {
    e.preventDefault();
    const email = emailNewsletter.trim();
    if (!email) return;
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      notificar("Digite um e-mail válido.", "erro");
      return;
    }
    setCarregandoNewsletter(true);
    try {
      const r = await api.assinarNewsletterPublica(email, categoria || "geral");
      notificar(r.detail || "Inscrição confirmada — obrigado!", "sucesso");
      setEmailNewsletter("");
    } catch (err: unknown) {
      notificar(err instanceof api.ApiError ? err.message : "Não foi possível inscrever. Tente novamente.", "erro");
    } finally {
      setCarregandoNewsletter(false);
    }
  }

  if (verSalvos) {
    return (
<div className="min-w-0 space-y-4 overflow-hidden cartao-meta secao-ver-tudo cartao-titulo secao-cabecalho">
        <header className={cn("seu-rio", "mb-6 min-w-0 space-y-2")}>
          <p className="text-xs font-bold uppercase tracking-[0.14em] text-[var(--cor-primaria)] secao-eyebrow">Leitura salva</p>
          <h1 className="break-words font-[var(--fonte-titulo)] text-3xl font-extrabold tracking-[-0.03em] text-wrap-balance seu-rio__titulo secao-titulo">Salvos para depois</h1>
          <p className="max-w-[62ch] break-words text-sm text-[var(--cor-texto-suave)] texto-suave">Sua lista de leitura para depois, guardada neste aparelho.</p>
        </header>
        <div className="flex justify-end controles-salvos">
          <Button variante="secundaria" onClick={() => setVerSalvos(false)}>
            ← Voltar ao feed
          </Button>
        </div>
        {salvos.length === 0 ? (
          <EmptyState titulo="Nenhuma notícia salva ainda" descricao="Toque em “Salvar para depois” em qualquer notícia para lê-la aqui." />
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
    <div className="min-w-0 w-full max-w-full space-y-4 overflow-hidden">
      {exibirPublicidade && (
        <div className={cn("faixa-publicidade", "rounded-md border border-[var(--cor-borda)] border-l-[3px] bg-[var(--cor-fundo-card)] px-3 py-2 text-sm text-[var(--cor-texto-suave)] motion-reduce:transition-none")}>
          Espaço publicitário — assine o <Link href="/planos" className="font-semibold text-[var(--cor-primaria)] underline-offset-2 hover:underline">Premium</Link> para navegar sem anúncios.
        </div>
      )}
      {novidadeDisponivel && (
        <div className={cn("banner-atualizacao", "sticky top-16 z-[var(--z-banner)] mb-4 flex justify-center motion-reduce:animate-none")} aria-live="polite">
          <button
            type="button"
            onClick={aplicarNovidade}
            className="inline-flex items-center gap-2 rounded-full bg-[var(--cor-primaria)] px-4 py-2 text-sm font-semibold text-white shadow-md transition-colors hover:bg-[var(--cor-primaria-hover)] motion-reduce:animate-none motion-reduce:transition-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] focus-visible:ring-offset-2"
          >
            ↑ Novas notícias disponíveis — atualizar
          </button>
        </div>
      )}
      {mostrarSugestao && categoriaPreferida && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-[var(--cor-primaria)] bg-[var(--cor-primaria-suave)] p-3 text-sm motion-reduce:transition-none" role="status">
          <span>
            Notamos que você tem lido bastante sobre <strong>{categoriaPreferida.categoria}</strong>. Quer filtrar o
            feed por esse tema?
          </span>
          <div className="flex flex-wrap gap-2">
            <Button
              onClick={() => {
                setCategoria(categoriaPreferida.categoria);
                setSugestaoDispensada(true);
              }}
            >
              Filtrar por {categoriaPreferida.categoria}
            </Button>
            <Button variante="secundaria" onClick={() => setSugestaoDispensada(true)}>
              Agora não
            </Button>
          </div>
        </div>
      )}

      {!modoRio && (
        <div className="flex flex-wrap items-end gap-3">
          <div className="min-w-0 flex-1">
            <SearchBar valorInicial={buscaAtiva} aoBuscar={aoBuscar} />
          </div>
          <Button variante="secundaria" onClick={() => setVerSalvos(true)}>
            ★ Salvos ({bookmarks.obterSalvos().length})
          </Button>
        </div>
      )}

      <div className="space-y-1" role="group" aria-label="Contexto da listagem">
        {categoria && (
          <p className="text-sm text-[var(--cor-texto-suave)]">
            Filtrando por <strong className="text-[var(--cor-texto)]">{categoria}</strong> —{" "}
            <button type="button" className="bg-transparent p-0 font-inherit text-[var(--cor-primaria)] underline hover:text-[var(--cor-primaria-hover)]" onClick={() => setCategoria("")}>
              limpar filtro
            </button>
          </p>
        )}
        {buscaAtiva && (
          <p className="text-sm text-[var(--cor-texto-suave)]">
            Busca por <strong className="text-[var(--cor-texto)]">“{buscaAtiva}”</strong> —{" "}
            <button type="button" className="bg-transparent p-0 font-inherit text-[var(--cor-primaria)] underline hover:text-[var(--cor-primaria-hover)]" onClick={() => setBuscaAtiva("")}>
              limpar busca
            </button>
          </p>
        )}
      </div>

      {!modoRio && (
<header className={cn("seu-rio", "mb-6 space-y-2")}>
          <p className="text-xs font-bold uppercase tracking-[0.14em] text-[var(--cor-primaria)] secao-eyebrow">Filtro do rio</p>
          <h1 className="font-[var(--fonte-titulo)] text-3xl font-extrabold tracking-[-0.03em] text-wrap-balance seu-rio__titulo">
            {categoria && buscaAtiva ? `${categoria} — “${buscaAtiva}”` : categoria || `“${buscaAtiva}”`}
          </h1>
          <p className="max-w-[62ch] text-sm text-[var(--cor-texto-suave)]">Um recorte do rio cronológico — limpe o filtro para voltar ao rio completo.</p>
        </header>
      )}

      {feed.isLoading && <SkeletonLista quantidade={6} />}

      <div aria-live="polite">
        {feed.isError && (
          <ErrorState
            mensagem={feed.error instanceof api.ApiError ? feed.error.message : "Não foi possível carregar o feed."}
            aoTentarNovamente={() => void feed.refetch()}
          />
        )}
        {!feed.isLoading && !feed.isError && itens.length === 0 && (
          <EmptyState titulo="Nenhuma notícia encontrada" descricao="Tente outra categoria ou termo de busca." />
        )}
      </div>

      {modoRio && (
<header className={cn("seu-rio", "mb-6 space-y-2")}>
          <p className="text-xs font-bold uppercase tracking-[0.14em] text-[var(--cor-primaria)] secao-eyebrow">{rioPessoal ? "Feito para o seu gosto" : "Cobertura ao vivo"}</p>
          <h1 className="font-[var(--fonte-titulo)] text-[clamp(2rem,5vw,3.2rem)] font-extrabold leading-[1.05] tracking-[-0.03em] text-wrap-balance seu-rio__titulo">Seu rio</h1>
          <p className="max-w-[62ch] text-sm leading-relaxed text-[var(--cor-texto-suave)]">
            {rioPessoal
              ? "A ordem abaixo segue os seus interesses e leituras — nunca uma escolha editorial."
              : "Ordem cronológica, igual para todos. Entre ou diga seus interesses no onboarding para o rio se moldar a você."}
          </p>
        </header>
      )}

      {!feed.isLoading && !feed.isError && (
        <div className={cn("portal-layout", "grid w-full max-w-full grid-cols-1 items-start gap-4 overflow-hidden sm:gap-6 lg:grid-cols-[minmax(0,1fr)_330px]")}>
          <div className="min-w-0 w-full max-w-full space-y-8 overflow-hidden">
            {modoRio ? (
              <>
                {rioPessoal && paraVoce.length > 0 && (
                  <section className="space-y-4 secao-bloco" aria-label="Para você">
                    <div className="flex items-baseline gap-3 border-b-2 border-[var(--cor-borda)] pb-3">
                      <p className="text-xs font-bold uppercase tracking-[0.14em] text-[var(--cor-primaria)]">Para você</p>
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
                <section className="min-w-0 space-y-4 overflow-hidden" id="ultimas" aria-label="Últimas notícias">
                  <div className="flex items-baseline gap-3 border-b-2 border-[var(--cor-borda)] pb-3">
                    <p className="text-xs font-bold uppercase tracking-[0.14em] text-[var(--cor-primaria)]">O rio</p>
                    <h2 className="font-[var(--fonte-titulo)] text-xl font-extrabold tracking-tight">Últimas notícias</h2>
                  </div>
                  {itens.length === 0 ? (
                    <p className="text-sm text-[var(--cor-texto-suave)]">Mais notícias aparecerão aqui.</p>
                  ) : (
                    <div className={cn("lista-compacta", "flex min-w-0 flex-col gap-3 overflow-hidden")}>
                      {itens.slice(0, 12).map((entrada, i) => (
                        <HorizontalNewsCard key={chaveDaEntrada(entrada)} entrada={entrada} posicao={i + 1} />
                      ))}
                    </div>
                  )}
                </section>
                {categoriasComConteudo.map((cat) => (
                  <BlocoEditoria key={cat} categoria={cat} itens={grupos[cat]} onVerTodas={() => setCategoria(cat)} />
                ))}
                {comunidadeTeaser.length > 0 && (
                  <section className="min-w-0 space-y-4 overflow-hidden break-words" aria-label="Da comunidade">
                    <div className="flex flex-wrap items-baseline gap-3 border-b-2 border-[var(--cor-borda)] pb-3">
                      <p className="text-xs font-bold uppercase tracking-[0.14em] text-[var(--cor-primaria)]">Vozes</p>
                      <h2 className="font-[var(--fonte-titulo)] text-xl font-extrabold tracking-tight">Da comunidade</h2>
                      <Link href="/comunidade" className="ml-auto text-sm font-medium text-[var(--cor-primaria)] hover:underline">
                        Ver tudo →
                      </Link>
                    </div>
                    <div className={cn("grade-noticias", "grid w-full max-w-full grid-cols-1 gap-4 overflow-hidden break-words sm:grid-cols-2 lg:grid-cols-3")}>
                      {comunidadeTeaser.map((pub) => (
                        <article key={pub.id} className="min-w-0 overflow-hidden break-words rounded-xl border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] p-4 shadow-sm transition-colors hover:border-[var(--cor-primaria)] motion-reduce:transition-none">
                          <div className="mb-2 flex flex-wrap gap-1.5">
                            <span className="inline-flex items-center rounded-full border border-transparent bg-[var(--cor-primaria-suave)] px-2 py-0.5 text-xs font-semibold text-[var(--cor-primaria)]">{pub.tipo === "opiniao" ? "Opinião" : "Análise"}</span>
                          </div>
                          <Link href={`/comunidade/${pub.id}`} className="no-underline hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]">
                            <h3 className="break-words font-[var(--fonte-titulo)] text-base font-semibold leading-tight line-clamp-3">{pub.titulo}</h3>
                          </Link>
                          <p className="mt-1 break-words text-sm text-[var(--cor-texto-suave)]">por {pub.autor_nome}</p>
                        </article>
                      ))}
                    </div>
                  </section>
                )}
              </>
            ) : (
              itens.length > 0 && (
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
              )
            )}
            {feed.isFetchingNextPage && <SkeletonLista quantidade={2} />}
          </div>
          {modoRio && (
            <aside className={cn("sidebar", "sticky top-[108px] flex min-w-0 w-full max-w-full flex-col gap-5 self-start overflow-hidden motion-reduce:transition-none")}>
              <MaisLidas limite={5} />
              <div className="rounded-xl bg-[#111] p-5 text-white shadow-sm">
                <h3 className="font-[var(--fonte-titulo)] text-base font-bold">Receba as principais</h3>
                <p className="mt-1 text-sm opacity-80">As manchetes do dia no seu e-mail.</p>
                <form onSubmit={onNewsletter} className="mt-3 flex flex-wrap gap-2 controles-feed">
                  <label htmlFor="newsletter-email" className="sr-only">E-mail para newsletter</label>
                  <input
                    id="newsletter-email"
                    type="email"
                    placeholder="Seu e-mail…"
                    aria-label="E-mail para newsletter"
                    value={emailNewsletter}
                    onChange={(e) => setEmailNewsletter(e.target.value)}
                    required
                    autoComplete="email"
                    className="min-h-[40px] flex-1 min-w-0 rounded-full border border-[#333] bg-[#222] px-3 py-2 text-[16px] text-white placeholder:text-[#888] focus:border-[var(--cor-primaria)] focus:outline-none focus:ring-2 focus:ring-[var(--cor-foco)]/30 motion-reduce:transition-none sm:text-sm"
                  />
                  <Button type="submit" carregando={carregandoNewsletter} className="rounded-full">
                    Inscrever
                  </Button>
                </form>
              </div>
              <div className="overflow-hidden rounded-xl border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
                <div className="flex items-center justify-between gap-2 border-b border-[var(--cor-borda)] px-4 py-3">
                  <h2 className="font-[var(--fonte-titulo)] text-sm font-extrabold">Salvos</h2>
                  <Button variante="secundaria" tamanho="pequeno" onClick={() => setVerSalvos(true)}>
                    Ver todos
                  </Button>
                </div>
                <div className="px-4 py-3">
                  {bookmarks.obterSalvos().length === 0 ? (
                    <p className="m-0 text-sm text-[var(--cor-texto-suave)]">
                      Salve notícias para ler depois.
                    </p>
                  ) : (
                    <ul className="m-0 flex flex-col gap-1.5 pl-4 text-sm">
                      {bookmarks.obterSalvos().slice(0, 3).map((s) => (
                        <li key={`${s.tipo}-${s.id}`} className="marker:text-[var(--cor-texto-suave)]">
                          <Link href={`/noticia/${s.tipo}/${s.id}`} className="text-[var(--cor-primaria)] hover:underline">{s.titulo}</Link>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>
            </aside>
          )}
        </div>
      )}
      {!feed.isLoading && !feed.isError && feed.hasNextPage && (
        <div className="flex justify-center py-4" ref={sentinelaRef} aria-live="polite">
          <Button variante="secundaria" onClick={() => void feed.fetchNextPage()} carregando={feed.isFetchingNextPage}>
            Carregar mais notícias
          </Button>
        </div>
      )}
    </div>
  );
}

export default function PaginaFeed() {
  return (
    <Suspense fallback={null}>
      <PaginaFeedInner />
    </Suspense>
  );
}
