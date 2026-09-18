"use client";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { AdsSlot } from "@/components/AdsSlot";
import { SecaoRegiao } from "@/components/SecaoRegiao";
import { SecaoColunistas } from "@/components/SecaoColunistas";
import { LocalidadeTag } from "@/components/home/NewsCard";
import { ManchetesGrid } from "@/components/home/ManchetesGrid";
import { UltimasNoticias } from "@/components/home/UltimasNoticias";
import { EmAlta } from "@/components/home/EmAlta";
import { ConteudoBombando } from "@/components/home/ConteudoBombando";
import { PortfolioCategorias } from "@/components/home/PortfolioCategorias";
import { ImagemNoticia } from "@/components/ImagemNoticia";
import { categoriasPorAfinidade, ordenarPorGosto } from "@/lib/personalizar";
import { obterTodasLeituras } from "@/lib/intent";
import { alternarSalvo, estaSalvo } from "@/lib/bookmarks";
import { useAuth } from "@/lib/auth-context";
import { usePremiumAtivo } from "@/lib/premium";
import { HOME_CONFIG_PADRAO, obterHomeConfig, type HomeConfig } from "@/lib/editorial";
import { hrefSubcategoria, subcategoriasCompletas } from "@/lib/categorias";
import type { FeedEntrada } from "@/lib/api";
import { Flame, Mail, Info, Crown } from "lucide-react";
import { cn } from "@/lib/utils";

const EDITORIAS = ["política", "economia", "tecnologia", "esportes", "cultura", "saúde", "mundo", "cidades"];

function timeAgo(iso: string) {
  try {
    const d = Math.max(0, Date.now() - new Date(iso).getTime());
    const h = Math.floor(d / 3600000);
    if (h < 1) return "agora";
    if (h < 24) return `${h}h`;
    return `${Math.floor(h / 24)}d`;
  } catch {
    return "";
  }
}

export function HomeClient({
  feed: feedProp,
  urg: urgProp,
  maisLidas: maisLidasProp = [],
}: {
  feed: FeedEntrada[];
  urg: FeedEntrada[];
  maisLidas?: FeedEntrada[];
}) {
  const { usuario } = useAuth();
  const isPremium = usuario?.papel === "premium" || usuario?.papel === "admin";
  const { liberado } = usePremiumAtivo();
  const premiumGeral = isPremium || liberado;
  const [filtro, setFiltro] = useState<string | null>(null);
  const [salvos, setSalvos] = useState<Set<string>>(new Set());
  const [leiturasTick, setLeiturasTick] = useState(0);
  const [config, setConfig] = useState<HomeConfig>(HOME_CONFIG_PADRAO);

  useEffect(() => {
    setConfig(obterHomeConfig());
  }, []);

  useEffect(() => {
    try {
      const s = new Set<string>();
      for (const f of [...feedProp, ...urgProp, ...maisLidasProp]) if (estaSalvo(f)) s.add(`${f.tipo}-${f.id}`);
      setSalvos(s);
    } catch {}
  }, [feedProp, urgProp, maisLidasProp, leiturasTick]);

  const perfil = useMemo(() => ({ interesses: usuario?.interesses ?? [] }), [usuario]);
  const leituras = useMemo(() => {
    try {
      return obterTodasLeituras();
    } catch {
      return {};
    }
  }, [leiturasTick]);

  useEffect(() => {
    setLeiturasTick((n) => n + 1);
  }, []);

  const hasSignal = perfil.interesses.length > 0 || Object.values(leituras).some((v) => v >= 2);
  const ordenado = useMemo(() => {
    if (!hasSignal) return feedProp;
    try {
      return ordenarPorGosto(feedProp, perfil);
    } catch {
      return feedProp;
    }
  }, [feedProp, perfil, hasSignal]);

  const filtrado = useMemo(() => {
    if (!filtro) return ordenado;
    return ordenado.filter((n) => (n.categoria || "").toLowerCase() === filtro);
  }, [ordenado, filtro]);

  const afinidade = useMemo(() => {
    try {
      return categoriasPorAfinidade(perfil);
    } catch {
      return [];
    }
  }, [perfil]);

  const totalEditorias = useMemo(
    () => new Set(feedProp.map((f) => (f.categoria || "").toLowerCase()).filter(Boolean)).size,
    [feedProp]
  );

  // Base do "Em alta": feed geral + urgentes + mais-lidas, deduplicada.
  const baseEmAlta = useMemo(() => {
    const mapa = new Map<string, FeedEntrada>();
    for (const e of [...maisLidasProp, ...urgProp, ...feedProp]) mapa.set(`${e.tipo}-${e.id}`, e);
    return [...mapa.values()];
  }, [feedProp, urgProp, maisLidasProp]);

  function toggleSalvar(e: FeedEntrada) {
    try {
      const novo = alternarSalvo(e);
      setSalvos((prev) => {
        const ns = new Set(prev);
        const k = `${e.tipo}-${e.id}`;
        if (novo) ns.add(k);
        else ns.delete(k);
        return ns;
      });
    } catch {}
  }

  if (feedProp.length === 0) {
    return (
      <div className="space-y-6" role="status" aria-label="Carregando página inicial">
        <div className="h-72 animate-pulse rounded-[var(--raio-lg)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)]" />
        <div className="h-10 w-64 animate-pulse rounded-full bg-[var(--cor-fundo-elevado)]" />
        <div className="grid gap-4 md:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-48 animate-pulse rounded-[var(--raio-lg)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)]" />
          ))}
        </div>
        <Card className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
          <CardContent className="p-6 text-center text-sm text-[var(--cor-texto-suave)]">
            Nenhuma manchete por aqui.{" "}
            <Link href="/arquivo" className="font-medium text-[var(--cor-primaria)] underline">
              Ver arquivo
            </Link>{" "}
            •{" "}
            <Link href="/personalizar" className="font-medium text-[var(--cor-primaria)] underline">
              Personalizar
            </Link>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Faixa editorial + contadores */}
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className="rounded-full border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] px-3 py-1.5 font-medium text-[var(--cor-texto)]">
          {filtrado.length} manchetes • {urgProp.length} urgentes • {totalEditorias} editorias
          {filtro ? ` • filtro: ${filtro}` : ""}
        </span>
        {isPremium && (
          <span className="inline-flex items-center gap-1 rounded-full bg-[var(--cor-premium-suave)] px-2 py-1 font-semibold text-[var(--cor-premium)]">
            <Crown className="h-3 w-3" aria-hidden /> Premium • sem anúncios extras
          </span>
        )}
        <Link href="/arquivo" className="font-medium text-[var(--cor-primaria)] hover:underline">
          Ver arquivo →
        </Link>
      </div>

      {/* Manchetes: 1 destaque + secundárias em grid denso, cards clicáveis */}
      <ManchetesGrid
        itens={filtrado}
        limiteSecundarias={config.manchetesSecundarias}
        salvos={salvos}
        onToggleSalvar={toggleSalvar}
      />

      {hasSignal && (
        <div className="flex items-center gap-2 rounded-full border border-[var(--cor-borda)] bg-[var(--cor-primaria-suave)] px-3 py-2 text-xs text-[var(--cor-texto)]">
          <Info className="h-3.5 w-3.5 shrink-0 text-[var(--cor-primaria)]" aria-hidden />
          <span>
            Feed ordenado por afinidade •{" "}
            <Link href="/personalizar" className="font-medium text-[var(--cor-primaria)] underline">
              ajustar
            </Link>
          </span>
        </div>
      )}

      {/* Ao vivo agora (rail horizontal) */}
      {urgProp.length > 0 && (
        <section
          aria-label="Ao vivo agora"
          className="rounded-[var(--raio-lg)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] p-3 shadow-[var(--sombra-1)]"
        >
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <h2 className="flex items-center gap-2 text-sm font-bold text-[var(--cor-texto)]">
              <span className="h-2 w-2 rounded-full bg-[var(--cor-sinal)] motion-safe:animate-pulse" aria-hidden />
              <Flame className="h-4 w-4 text-[var(--cor-sinal)]" aria-hidden /> Ao vivo agora{" "}
              <span className="rounded-full bg-[var(--cor-erro-suave)] px-2 py-0.5 text-xs font-semibold text-[var(--cor-sinal)]">
                ao vivo
              </span>
            </h2>
            <span className="rounded-full border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] px-2.5 py-1 text-xs font-medium text-[var(--cor-texto-suave)]">
              {urgProp.length} urgentes • deslize para ver mais
            </span>
          </div>
          <div className="flex gap-3 overflow-x-auto pb-2 [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden snap-x snap-mandatory">
            {urgProp.map((u) => (
              <Link
                key={`live-${u.tipo}-${u.id}`}
                href={`/noticia/${u.id}`}
                className="group flex w-64 shrink-0 snap-start gap-3 rounded-[var(--raio-md)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-2 hover:shadow-[var(--sombra-2)] hover:-translate-y-1 transition-all duration-200 motion-safe:transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]"
              >
                <ImagemNoticia
                  src={u.imagem_url}
                  seed={`${u.categoria || "geral"}-${u.id}`}
                  alt=""
                  sizes="96px"
                  className="h-16 w-20 shrink-0 rounded-md object-cover"
                />
                <div className="min-w-0">
                  <span className="inline-flex items-center gap-1 rounded-full bg-[var(--cor-sinal)] px-1.5 py-0.5 text-[10px] font-bold text-[var(--cor-texto-invertido)]">
                    <span className="h-1 w-1 rounded-full bg-[var(--cor-texto-invertido)] motion-safe:animate-pulse" aria-hidden /> AO VIVO
                  </span>
                  <p className="mt-1 line-clamp-2 text-xs font-semibold leading-tight text-[var(--cor-texto)] group-hover:text-[var(--cor-primaria)] motion-safe:transition-colors">
                    {u.titulo}
                  </p>
                  <p className="flex flex-wrap items-center gap-x-1 text-[11px] capitalize text-[var(--cor-texto-suave)]">
                    {u.categoria} • {timeAgo(u.timestamp)} <LocalidadeTag entrada={u} className="text-[11px] normal-case" />
                  </p>
                </div>
              </Link>
            ))}
          </div>
        </section>
      )}

      {/* Últimas + Em alta lado a lado (empilham no mobile) */}
      <div className="grid items-start gap-6 lg:grid-cols-12">
        <div className="lg:col-span-7">
          <UltimasNoticias
            inicial={feedProp}
            limite={config.ultimasLimite}
            passo={config.ultimasPasso}
            intervaloSegundos={config.refreshUltimasSegundos}
          />
        </div>
        <div className="lg:col-span-5">
          <EmAlta feed={baseEmAlta} limite={config.emAltaLimite} categoriaBuscada={filtro} />
        </div>
      </div>

      <ConteudoBombando feed={filtrado} limite={config.bombandoLimite} salvos={salvos} onToggleSalvar={toggleSalvar} />

      <SecaoRegiao feed={filtrado.length ? filtrado : feedProp} />

      <SecaoColunistas />

      <AdsSlot id="home-topo" formato="horizontal" />

      {isPremium && (
        <p className="flex items-center gap-1.5 rounded-full border border-[var(--cor-premium)] bg-[var(--cor-premium-suave)] px-3 py-1.5 text-xs font-medium text-[var(--cor-premium)]">
          <Crown className="h-3.5 w-3.5" aria-hidden /> Você navega com menos anúncios — benefício Premium
        </p>
      )}

      {!premiumGeral ? (
        <AdsSlot id="home-infeed" formato="in-feed" />
      ) : (
        <p className="flex items-center gap-1.5 rounded-full border border-dashed border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] px-3 py-2 text-xs text-[var(--cor-texto-suave)]">
          <Crown className="h-3.5 w-3.5 text-[var(--cor-premium)]" aria-hidden /> Leitura sem interrupção — anúncio removido no Premium
        </p>
      )}

      {/* Portfólio + sidebar */}
      <section className="grid items-start gap-6 lg:grid-cols-12">
        <div className="lg:col-span-8">
          <PortfolioCategorias
            feed={filtrado}
            maxCategorias={config.portfolioCategorias}
            porCategoria={config.portfolioPorCategoria}
            passo={config.portfolioPasso}
            categoriaBuscada={filtro}
            salvos={salvos}
            onToggleSalvar={toggleSalvar}
          />
          <div className="mt-6 rounded-[var(--raio-lg)] border border-dashed border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] px-4 py-6 text-center">
            <p className="text-sm text-[var(--cor-texto-suave)]">
              Fim — veja mais em{" "}
              <Link href="/arquivo" className="font-medium text-[var(--cor-primaria)] underline">
                Arquivo
              </Link>{" "}
              ou{" "}
              <Link href="/personalizar" className="font-medium text-[var(--cor-primaria)] underline">
                Personalizar
              </Link>
              .
            </p>
          </div>
        </div>

        <aside className="space-y-4 lg:col-span-4" aria-label="Exploração e assinatura">
          <Card className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
            <CardContent className="p-4">
              <h3 className="mb-3 text-sm font-bold text-[var(--cor-texto)]">Explorar editorias</h3>
              <div className="flex gap-2 overflow-x-auto pb-2 [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
                <button
                  onClick={() => setFiltro(null)}
                  aria-pressed={!filtro}
                  className={cn(
                    "shrink-0 rounded-full border px-3 py-1.5 text-sm font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]",
                    !filtro
                      ? "border-[var(--cor-primaria)] bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]"
                      : "border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] text-[var(--cor-texto)] hover:bg-[var(--cor-primaria-suave)]"
                  )}
                >
                  Tudo
                </button>
                {EDITORIAS.map((c) => (
                  <button
                    key={c}
                    onClick={() => setFiltro(filtro === c ? null : c)}
                    aria-pressed={filtro === c}
                    className={cn(
                      "shrink-0 rounded-full border px-3 py-1.5 text-sm font-medium capitalize transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]",
                      filtro === c
                        ? "border-[var(--cor-primaria)] bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]"
                        : "border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] text-[var(--cor-texto)] hover:bg-[var(--cor-primaria-suave)]"
                    )}
                  >
                    {c}
                  </button>
                ))}
              </div>
              {filtro && (
                <div className="mt-3 rounded-[var(--raio-md)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-3">
                  <p className="mb-2 text-xs font-semibold tracking-widest text-[var(--cor-texto-suave)]">
                    EM <span className="capitalize">{filtro}</span> • ASSUNTOS
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {subcategoriasCompletas(filtro, feedProp).map((s) => (
                      <Link
                        key={s.termo}
                        href={hrefSubcategoria(s)}
                        className="inline-flex items-center gap-1 rounded-full border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] px-2.5 py-1 text-xs text-[var(--cor-texto)] hover:border-[var(--cor-primaria)] hover:text-[var(--cor-primaria)]"
                      >
                        {s.nome}
                        {"viva" in s && s.viva && (
                          <span className="h-1.5 w-1.5 rounded-full bg-[var(--cor-sinal)] motion-safe:animate-pulse" aria-label="Em alta nas notícias" />
                        )}
                      </Link>
                    ))}
                  </div>
                </div>
              )}
              <Link href="/editorias" className="mt-2 inline-flex text-xs font-medium text-[var(--cor-primaria)] hover:underline">
                Ver todas →
              </Link>
            </CardContent>
          </Card>

          <Card className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
            <CardContent className="p-4">
              <h3 className="text-sm font-bold text-[var(--cor-texto)]">Para você</h3>
              {afinidade.length ? (
                <>
                  <p className="mt-1 text-sm leading-snug text-[var(--cor-texto-suave)]">Baseado no que você acompanha:</p>
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {afinidade.slice(0, 6).map((c) => (
                      <Link
                        key={c}
                        href={`/categoria/${encodeURIComponent(c)}`}
                        className="rounded-full border border-[var(--cor-borda)] bg-[var(--cor-primaria-suave)] px-2.5 py-1 text-xs font-medium capitalize text-[var(--cor-primaria)] hover:bg-[var(--cor-fundo-elevado)]"
                      >
                        {c}
                      </Link>
                    ))}
                  </div>
                  <Link href="/personalizar" className="mt-3 inline-flex text-xs font-medium text-[var(--cor-primaria)] hover:underline">
                    Ajustar preferências →
                  </Link>
                </>
              ) : (
                <>
                  <p className="mt-1 text-sm leading-snug text-[var(--cor-texto-suave)]">
                    Personalize suas editorias favoritas para ver manchetes mais relevantes primeiro.
                  </p>
                  <Button asChild size="sm" className="mt-3 bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)] hover:bg-[var(--cor-primaria-hover)]">
                    <Link href="/personalizar">Personalizar</Link>
                  </Button>
                </>
              )}
            </CardContent>
          </Card>

          <Card className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
            <CardContent className="p-4">
              <h3 className="flex items-center gap-2 text-sm font-bold text-[var(--cor-texto)]">
                <Mail className="h-4 w-4 text-[var(--cor-primaria)]" aria-hidden /> Newsletter
              </h3>
              <p className="mt-1 text-sm text-[var(--cor-texto-suave)]">Resumo diário sem ruído — escolha editorias e período.</p>
              <form action="/newsletter" className="mt-3 flex gap-2">
                <Input
                  placeholder="seu@email.com"
                  type="email"
                  required
                  aria-label="Email para newsletter"
                  className="h-9 bg-[var(--cor-fundo-card)]"
                />
                <Button type="submit" className="h-9 shrink-0 bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)] hover:bg-[var(--cor-primaria-hover)]">
                  Assinar
                </Button>
              </form>
              <p className="mt-2 text-xs text-[var(--cor-texto-suave)]">
                Ao assinar você concorda com <Link href="/privacidade" className="underline">privacidade</Link>.
              </p>
            </CardContent>
          </Card>

          <AdsSlot id="home-sidebar" formato="retangulo" />
        </aside>
      </section>
      <AdsSlot id="home-footer" formato="horizontal" className="my-6" />
    </div>
  );
}
