"use client";

import { Suspense, useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import * as api from "@/lib/api";
import { useFeed } from "@/lib/queries";
import * as intencao from "@/lib/intent";
import * as bookmarks from "@/lib/bookmarks";
import { obterVisualCategoria } from "@/lib/categoryVisuals";
import { useToast } from "@/components/ToastProvider";
import PorQueEstouVendoIsso from "@/components/PorQueEstouVendoIsso";
import Chip from "@/components/Chip";
import BotaoSalvar from "@/components/BotaoSalvar";
import TickerUrgente from "@/components/TickerUrgente";
import MaisLidas from "@/components/MaisLidas";
import BlocoEditoria from "@/components/BlocoEditoria";
import { Button } from "@/components/ui/Button";
import { HorizontalNewsCard, NewsCard } from "@/components/ui/Cards";
import { EmptyState, ErrorState, SkeletonLista } from "@/components/ui/Estados";
import { SearchBar } from "@/components/ui/SearchBar";

const CATEGORIAS_REFERENCIA = ["política", "economia", "esportes", "tecnologia", "saúde", "cultura", "cidades", "mundo", "ciência"];
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
  const modoMosaico = !categoria && !buscaAtiva && !verSalvos;
  const itemHero = modoMosaico && itens.length > 0 ? itens[0] : null;
  const itensMosaicoLateral = modoMosaico ? itens.slice(1, 4) : [];
  const itensAposMosaico = modoMosaico ? itens.slice(4) : itens;
  const grupos = modoMosaico ? agruparPorCategoria(itensAposMosaico) : {};
  const categoriasComConteudo = Object.keys(grupos).slice(0, 3);

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
      {modoMosaico && <TickerUrgente />}
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

      {!modoMosaico && (
        <div className="controles-feed">
          <SearchBar valorInicial={buscaAtiva} aoBuscar={aoBuscar} />
          <Button variante="secundaria" onClick={() => setVerSalvos(true)}>
            ★ Salvos ({bookmarks.obterSalvos().length})
          </Button>
        </div>
      )}

      <div className="filtro-categorias" role="group" aria-label="Filtrar por categoria">
        <Chip selecionado={categoria === ""} aoClicar={() => setCategoria("")}>
          Todas
        </Chip>
        {CATEGORIAS_REFERENCIA.map((c) => {
          const v = obterVisualCategoria(c);
          return (
            <Chip key={c} selecionado={categoria === c} aoClicar={() => setCategoria(categoria === c ? "" : c)}>
              <span className="cartao-emoji" aria-hidden="true">
                {v.emoji}
              </span>
              {c}
            </Chip>
          );
        })}
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

      {!feed.isLoading && !feed.isError && itemHero && (
        <section className="hero" aria-label="Destaque do dia">
          <div
            className="hero__fundo"
            style={{ background: obterVisualCategoria(itemHero.categoria).gradiente }}
            aria-hidden="true"
          />
          <p className="hero__eyebrow">
            Em destaque{itemHero.urgente ? " · urgente" : ""}
          </p>
          <h1 className="hero__titulo">
            <Link href={`/noticia/${itemHero.tipo}/${itemHero.id}`}>{itemHero.titulo}</Link>
          </h1>
          <p className="hero__resumo">{itemHero.resumo}</p>
          <div className="hero__acoes">
            <Link
              href={`/noticia/${itemHero.tipo}/${itemHero.id}`}
              className="botao botao--primaria botao--medio"
            >
              Ler agora
            </Link>
            <BotaoSalvar entrada={itemHero} />
          </div>
          {itensMosaicoLateral.length > 0 && (
            <ol className="hero__lista">
              {itensMosaicoLateral.map((entrada, i) => (
                <li key={chaveDaEntrada(entrada)}>
                  <HorizontalNewsCard entrada={entrada} posicao={i + 2} />
                </li>
              ))}
            </ol>
          )}
        </section>
      )}

      {!feed.isLoading && !feed.isError && (
        <div className={modoMosaico ? "portal-layout" : ""}>
          <div>
            {modoMosaico ? (
              <>
                {categoriasComConteudo.map((cat) => (
                  <BlocoEditoria key={cat} categoria={cat} itens={grupos[cat]} onVerTodas={() => setCategoria(cat)} />
                ))}
                <section className="secao-bloco">
                  <div className="secao-cabecalho">
                    <h2 className="secao-titulo">Últimas notícias</h2>
                  </div>
                  {itensAposMosaico.length === 0 ? (
                    <p className="texto-suave">Mais notícias aparecerão aqui.</p>
                  ) : (
                    <div className="lista-compacta">
                      {itensAposMosaico.slice(0, 12).map((entrada, i) => (
                        <HorizontalNewsCard key={chaveDaEntrada(entrada)} entrada={entrada} posicao={i + 1} />
                      ))}
                    </div>
                  )}
                </section>
              </>
            ) : (
              itensAposMosaico.length > 0 && (
                <div className="grade-noticias">
                  {itensAposMosaico.map((entrada) => (
                    <article key={chaveDaEntrada(entrada)} className="card-legado">
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
          {modoMosaico && (
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
