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
      <div>
        <div className="controles-salvos">
          <Button variante="secundaria" onClick={() => setVerSalvos(false)}>
            ← Voltar ao feed
          </Button>
        </div>
        {salvos.length === 0 ? (
          <EmptyState titulo="Nenhuma notícia salva ainda" descricao="Toque em “Salvar para depois” em qualquer notícia para lê-la aqui." />
        ) : (
          <div className="grade-noticias">
            {salvos.map((entrada) => (
              <NewsCard key={chaveDaEntrada(entrada)} entrada={entrada} />
            ))}
          </div>
        )}
      </div>
    );
  }

  return (
    <div>
      {exibirPublicidade && (
        <div className="faixa-publicidade">
          Espaço publicitário — assine o <Link href="/planos">Premium</Link> para navegar sem anúncios.
        </div>
      )}
      {novidadeDisponivel && (
        <div className="banner-atualizacao">
          <button type="button" onClick={aplicarNovidade}>
            ↑ Novas notícias disponíveis — atualizar
          </button>
        </div>
      )}
      {mostrarSugestao && categoriaPreferida && (
        <div className="sugestao-adaptativa" role="status">
          <span>
            Notamos que você tem lido bastante sobre <strong>{categoriaPreferida.categoria}</strong>. Quer filtrar o
            feed por esse tema?
          </span>
          <div className="sugestao-adaptativa-acoes">
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
        <div className="controles-feed">
          <SearchBar valorInicial={buscaAtiva} aoBuscar={aoBuscar} />
          <Button variante="secundaria" onClick={() => setVerSalvos(true)}>
            ★ Salvos ({bookmarks.obterSalvos().length})
          </Button>
        </div>
      )}

      <div className="fluxo-contexto" role="group" aria-label="Contexto da listagem">
        {categoria && (
          <p className="texto-suave">
            Filtrando por <strong>{categoria}</strong> —{" "}
            <button type="button" className="link-nulo" onClick={() => setCategoria("")}>
              limpar filtro
            </button>
          </p>
        )}
        {buscaAtiva && (
          <p className="texto-suave">
            Busca por <strong>“{buscaAtiva}”</strong> —{" "}
            <button type="button" className="link-nulo" onClick={() => setBuscaAtiva("")}>
              limpar busca
            </button>
          </p>
        )}
      </div>

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

      {!feed.isLoading && !feed.isError && modoRio && (
        <header className="seu-rio">
          <p className="secao-eyebrow">{rioPessoal ? "Feito para o seu gosto" : "Cobertura ao vivo"}</p>
          <h1 className="seu-rio__titulo">Seu rio</h1>
          <p className="texto-suave">
            {rioPessoal
              ? "A ordem abaixo segue os seus interesses e leituras — nunca uma escolha editorial."
              : "Ordem cronológica, igual para todos. Entre ou diga seus interesses no onboarding para o rio se moldar a você."}
          </p>
        </header>
      )}

      {!feed.isLoading && !feed.isError && (
        <div className={modoRio ? "portal-layout" : ""}>
          <div>
            {modoRio ? (
              <>
                {rioPessoal && paraVoce.length > 0 && (
                  <section className="secao-bloco" aria-label="Para você">
                    <div className="secao-cabecalho">
                      <p className="secao-eyebrow">Para você</p>
                      <h2 className="secao-titulo">No seu gosto</h2>
                    </div>
                    <div className="grade-noticias">
                      {paraVoce.map((entrada) => (
                        <article key={chaveDaEntrada(entrada)}>
                          <NewsCard entrada={entrada} />
                          <PorQueEstouVendoIsso
                            motivos={motivosDaEntrada(entrada, buscaAtiva, intencao.obterLeiturasDaCategoria(entrada.categoria))}
                          />
                        </article>
                      ))}
                    </div>
                  </section>
                )}
                <section className="secao-bloco" id="ultimas" aria-label="Últimas notícias">
                  <div className="secao-cabecalho">
                    <p className="secao-eyebrow">O rio</p>
                    <h2 className="secao-titulo">Últimas notícias</h2>
                  </div>
                  {itens.length === 0 ? (
                    <p className="texto-suave">Mais notícias aparecerão aqui.</p>
                  ) : (
                    <div className="lista-compacta">
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
                  <section className="secao-bloco" aria-label="Da comunidade">
                    <div className="secao-cabecalho">
                      <p className="secao-eyebrow">Vozes</p>
                      <h2 className="secao-titulo">Da comunidade</h2>
                      <Link href="/comunidade" className="secao-ver-tudo">
                        Ver tudo →
                      </Link>
                    </div>
                    <div className="grade-noticias">
                      {comunidadeTeaser.map((pub) => (
                        <article key={pub.id} className="cartao">
                          <div className="cartao-meta">
                            <span className="badge-categoria">{pub.tipo === "opiniao" ? "Opinião" : "Análise"}</span>
                          </div>
                          <Link href={`/comunidade/${pub.id}`} style={{ textDecoration: "none", color: "inherit" }}>
                            <h3 className="cartao-titulo">{pub.titulo}</h3>
                          </Link>
                          <p className="texto-suave">por {pub.autor_nome}</p>
                        </article>
                      ))}
                    </div>
                  </section>
                )}
              </>
            ) : (
              itens.length > 0 && (
                <div className="grade-noticias">
                  {itens.map((entrada) => (
                    <article key={chaveDaEntrada(entrada)}>
                      <NewsCard entrada={entrada} />
                      <PorQueEstouVendoIsso
                        motivos={motivosDaEntrada(entrada, buscaAtiva, intencao.obterLeiturasDaCategoria(entrada.categoria))}
                      />
                    </article>
                  ))}
                </div>
              )
            )}
            {feed.isFetchingNextPage && <SkeletonLista quantidade={2} />}
          </div>
          {modoRio && (
            <aside className="sidebar">
              <MaisLidas limite={5} />
              <div className="newsletter-box">
                <h3>Receba as principais</h3>
                <p>As manchetes do dia no seu e-mail.</p>
                <form onSubmit={onNewsletter} style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                  <input
                    type="email"
                    placeholder="Seu e-mail"
                    aria-label="E-mail para newsletter"
                    value={emailNewsletter}
                    onChange={(e) => setEmailNewsletter(e.target.value)}
                    required
                    style={{ flex: "1 1 160px", minWidth: 0 }}
                  />
                  <Button type="submit" carregando={carregandoNewsletter}>
                    Inscrever
                  </Button>
                </form>
              </div>
              <div className="bloco-sidebar">
                <div className="bloco-sidebar-cabecalho">
                  <h2 className="bloco-sidebar-titulo">Salvos</h2>
                  <Button variante="secundaria" tamanho="pequeno" onClick={() => setVerSalvos(true)}>
                    Ver todos
                  </Button>
                </div>
                <div style={{ padding: "var(--espaco-3) var(--espaco-4)" }}>
                  {bookmarks.obterSalvos().length === 0 ? (
                    <p className="texto-suave" style={{ margin: 0 }}>
                      Salve notícias para ler depois.
                    </p>
                  ) : (
                    <ul style={{ margin: 0, paddingLeft: "1.1rem", fontSize: "0.85rem", display: "flex", flexDirection: "column", gap: 6 }}>
                      {bookmarks.obterSalvos().slice(0, 3).map((s) => (
                        <li key={`${s.tipo}-${s.id}`}>
                          <Link href={`/noticia/${s.tipo}/${s.id}`}>{s.titulo}</Link>
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
        <div className="sentinela-carregamento" ref={sentinelaRef}>
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
