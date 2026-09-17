"use client";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { AdsSlot } from "@/components/AdsSlot";
import { SecaoRegiao } from "@/components/SecaoRegiao";
import { imagemNoticia } from "@/lib/imagens";
import { categoriasPorAfinidade, ordenarPorGosto } from "@/lib/personalizar";
import { obterTodasLeituras } from "@/lib/intent";
import { alternarSalvo, estaSalvo } from "@/lib/bookmarks";
import { useAuth } from "@/lib/auth-context";
import { usePremiumAtivo } from "@/lib/premium";
import type { FeedEntrada } from "@/lib/api";
import { ArrowRight, Bookmark, BookmarkCheck, Clock3, Flame, Mail, Info, Crown } from "lucide-react";
import { cn } from "@/lib/utils";

const EDITORIAS = ["política", "economia", "tecnologia", "esportes", "cultura", "saúde", "mundo", "cidades"];
const EDITORIAS_DESTAQUE = ["política", "economia", "tecnologia", "esportes"];

function timeAgo(iso: string) {
  const d = Math.max(0, Date.now() - new Date(iso).getTime());
  const h = Math.floor(d / 3600000);
  if (h < 1) return "agora";
  if (h < 24) return `${h}h`;
  return `${Math.floor(h / 24)}d`;
}

export function HomeClient({ feed: feedProp, urg: urgProp }: { feed: FeedEntrada[]; urg: FeedEntrada[] }) {
  const { usuario } = useAuth();
  const isPremium = usuario?.papel === "premium" || usuario?.papel === "admin";
  const { liberado } = usePremiumAtivo();
  const premiumGeral = isPremium || liberado;
  const [filtro, setFiltro] = useState<string | null>(null);
  const [salvos, setSalvos] = useState<Set<string>>(new Set());
  const [leiturasTick, setLeiturasTick] = useState(0);

  useEffect(() => {
    try {
      const s = new Set<string>();
      for (const f of [...feedProp, ...urgProp]) if (estaSalvo(f)) s.add(`${f.tipo}-${f.id}`);
      setSalvos(s);
    } catch {}
  }, [feedProp, urgProp, leiturasTick]);

  const perfil = useMemo(() => ({ interesses: usuario?.interesses ?? [] }), [usuario]);
  const leituras = useMemo(() => {
    try { return obterTodasLeituras(); } catch { return {}; }
  }, [leiturasTick]);

  useEffect(() => { setLeiturasTick((n) => n + 1); }, []);

  const hasSignal = perfil.interesses.length > 0 || Object.values(leituras).some((v) => v >= 2);
  const ordenado = useMemo(() => {
    if (!hasSignal) return feedProp;
    try { return ordenarPorGosto(feedProp, perfil); } catch { return feedProp; }
  }, [feedProp, perfil, hasSignal]);

  const filtrado = useMemo(() => {
    if (!filtro) return ordenado;
    return ordenado.filter((n) => (n.categoria || "").toLowerCase() === filtro);
  }, [ordenado, filtro]);

  const heroSlides = useMemo(() => filtrado.slice(0, 3), [filtrado]);
  const [heroIdx, setHeroIdx] = useState(0);
  const [paused, setPaused] = useState(false);
  useEffect(() => { setHeroIdx(0); }, [filtro]);
  useEffect(() => { if (heroIdx >= heroSlides.length) setHeroIdx(0); }, [heroIdx, heroSlides.length]);
  useEffect(() => {
    if (heroSlides.length <= 1 || paused) return;
    const id = setInterval(() => setHeroIdx((i) => (i + 1) % heroSlides.length), 8000);
    return () => clearInterval(id);
  }, [heroSlides.length, paused]);
  const hero = heroSlides[heroIdx] ?? filtrado[0];
  const grid = filtrado.slice(3, 7);
  const resto = filtrado.slice(7);
  const afinidade = useMemo(() => {
    try { return categoriasPorAfinidade(perfil); } catch { return []; }
  }, [perfil]);

  const totalEditorias = useMemo(() => new Set(filtrado.map((f) => (f.categoria || "").toLowerCase()).filter(Boolean)).size, [filtrado]);
  const porEditoria = useMemo(() => EDITORIAS_DESTAQUE.map((cat) => ({ cat, items: filtrado.filter((n) => (n.categoria || "").toLowerCase() === cat).slice(0, 2) })).filter((g) => g.items.length > 0), [filtrado]);
  const recomendado = useMemo(() => {
    if (!afinidade.length) return filtrado.slice(0, 3);
    const byAffinity = filtrado.filter((n) => afinidade.includes((n.categoria || "").toLowerCase()));
    if (byAffinity.length >= 3) return byAffinity.slice(0, 3);
    const rest = filtrado.filter((n) => !afinidade.includes((n.categoria || "").toLowerCase()));
    return [...byAffinity, ...rest].slice(0, 3);
  }, [filtrado, afinidade]);

  function toggleSalvar(e: FeedEntrada) {
    try {
      const novo = alternarSalvo(e);
      setSalvos((prev) => {
        const ns = new Set(prev);
        const k = `${e.tipo}-${e.id}`;
        if (novo) ns.add(k); else ns.delete(k);
        return ns;
      });
    } catch {}
  }

  if (feedProp.length === 0 && !hero) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="h-72 rounded-[var(--raio-lg)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)]" />
        <div className="h-10 w-64 rounded-full bg-[var(--cor-fundo-elevado)]" />
        <div className="grid gap-4 md:grid-cols-4">{Array.from({ length: 4 }).map((_, i) => (<div key={i} className="h-48 rounded-[var(--raio-lg)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)]" />))}</div>
        <div className="grid gap-3">{Array.from({ length: 3 }).map((_, i) => (<div key={i} className="h-20 rounded-[var(--raio-lg)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)]" />))}</div>
      </div>
    );
  }

  if (!hero) return (<Card className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]"><CardContent className="p-6 text-center text-sm text-[var(--cor-texto-suave)]">Nenhuma manchete por aqui. <Link href="/arquivo" className="font-medium text-[var(--cor-primaria)] underline">Ver arquivo</Link> • <Link href="/personalizar" className="font-medium text-[var(--cor-primaria)] underline">Personalizar</Link></CardContent></Card>);

  return (
    <div className="space-y-6">
      <section onMouseEnter={() => setPaused(true)} onMouseLeave={() => setPaused(false)} className="relative overflow-hidden rounded-[var(--raio-lg)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] shadow-[var(--sombra-1)]">
        <div className="absolute inset-x-0 top-0 h-px opacity-60" style={{ background: "var(--gradiente-marca)" }} aria-hidden />
        <div className="absolute inset-0 opacity-[0.04]" style={{ background: "var(--gradiente-marca)" }} aria-hidden />
        <div className="relative p-4 md:p-6">
          <div className="mb-3 flex items-center gap-2">
            <h2 className="text-sm font-bold tracking-tight text-[var(--cor-texto)]">Destaque do dia</h2>
            {isPremium && <span className="inline-flex items-center gap-1 rounded-full bg-[var(--cor-premium-suave)] px-2 py-0.5 text-xs font-semibold text-[var(--cor-premium)]"><Crown className="h-3 w-3" /> Premium • sem anúncios extras</span>}
            <span className="hidden h-3 w-px bg-[var(--cor-borda)] md:block" aria-hidden />
            <span className="text-xs text-[var(--cor-texto-suave)]">{new Date().toLocaleDateString("pt-BR")} • {urgProp.length} em alta</span>
          </div>
          <div className="grid gap-6 md:grid-cols-[1.55fr_0.95fr]">
            <div className="group relative overflow-hidden rounded-[var(--raio-lg)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)]">
              <div className="relative aspect-[16/9] overflow-hidden">
                {heroSlides.map((h, i) => (
                  <Link key={`${h.tipo}-${h.id}`} href={`/noticia/${h.id}`} aria-hidden={i !== heroIdx} aria-label={h.titulo} className={cn("absolute inset-0 block transition-opacity duration-500 motion-safe:transition-opacity focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] focus-visible:ring-offset-2", i === heroIdx ? "opacity-100" : "pointer-events-none opacity-0")}>
                    <img src={imagemNoticia(h)} alt={h.titulo} loading={i === 0 ? "eager" : "lazy"} className="h-full w-full object-cover motion-safe:transition motion-safe:duration-300 group-hover:motion-safe:scale-[1.02]" />
                    {h.urgente && <span className="absolute left-3 top-3 rounded-full bg-[var(--cor-sinal)] px-2.5 py-1 text-xs font-bold text-[var(--cor-texto-invertido)] shadow motion-safe:animate-pulse">Ao vivo</span>}
                  </Link>
                ))}
              </div>
              {heroSlides.length > 1 && (
                <div className="absolute bottom-3 left-1/2 flex -translate-x-1/2 items-center gap-1.5 rounded-full bg-[var(--cor-fundo-card)]/80 px-2 py-1.5 shadow backdrop-blur">
                  {heroSlides.map((_, i) => (
                    <button key={i} type="button" aria-label={`Ir para destaque ${i + 1}`} aria-current={i === heroIdx} onClick={() => setHeroIdx(i)} className={cn("h-2 rounded-full transition-all motion-safe:transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]", i === heroIdx ? "w-6 bg-[var(--cor-primaria)]" : "w-2 bg-[var(--cor-borda)] hover:bg-[var(--cor-texto-suave)]")} />
                  ))}
                </div>
              )}
            </div>
            <div className="relative flex min-h-[280px] flex-col py-1">
              {heroSlides.map((h, i) => (
                <div key={`txt-${h.tipo}-${h.id}`} className={cn("flex flex-col gap-3 transition-opacity duration-500 motion-safe:transition-opacity", i === heroIdx ? "opacity-100 motion-safe:animate-in" : "pointer-events-none absolute inset-0 opacity-0") } aria-hidden={i !== heroIdx}>
                  <div className="flex flex-wrap items-center gap-2">
                    <Link href={`/categoria/${encodeURIComponent(h.categoria)}`} className="capitalize focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] focus-visible:ring-offset-1 rounded-full"><Badge variant="outline" className="border-[var(--cor-borda)] capitalize text-[var(--cor-texto-suave)] hover:bg-[var(--cor-primaria-suave)] hover:text-[var(--cor-primaria)] motion-safe:transition-colors">{h.categoria}</Badge></Link>
                    <span className="inline-flex items-center gap-1 text-xs text-[var(--cor-texto-suave)]"><Clock3 className="h-3 w-3" />{timeAgo(h.timestamp)} • {h.numero_fontes} fontes</span>
                    {h.urgente && <span className="inline-flex items-center gap-1 rounded-full bg-[var(--cor-erro-suave)] px-2 py-0.5 text-xs font-medium text-[var(--cor-sinal)]"><span className="h-1.5 w-1.5 rounded-full bg-[var(--cor-sinal)] motion-safe:animate-pulse" aria-hidden /> Urgente</span>}
                  </div>
                  <Link href={`/noticia/${h.id}`} className="text-balance text-2xl font-bold leading-tight text-[var(--cor-texto)] hover:text-[var(--cor-primaria)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] focus-visible:ring-offset-2 motion-safe:transition-colors md:text-3xl line-clamp-2">{h.titulo}</Link>
                  <Link href={`/noticia/${h.id}`} className="line-clamp-2 text-sm leading-relaxed text-[var(--cor-texto-suave)] hover:text-[var(--cor-texto)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] motion-safe:transition-colors">{h.resumo}</Link>
                  <div className="mt-1 flex flex-wrap gap-2">
                    <Button asChild className="bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)] hover:bg-[var(--cor-primaria-hover)] motion-safe:transition-colors"><Link href={`/noticia/${h.id}`} className="focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]">Ler agora <ArrowRight className="ml-1 h-4 w-4" /></Link></Button>
                    <Button variant="outline" className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] motion-safe:transition-colors" onClick={() => toggleSalvar(h)}>
                      {salvos.has(`${h.tipo}-${h.id}`) ? <><BookmarkCheck className="mr-1 h-4 w-4" /> Salvo</> : <><Bookmark className="mr-1 h-4 w-4" /> Salvar</>}
                    </Button>
                  </div>
                  <Link href="/ao-vivo" className="mt-1 inline-flex items-center gap-1 text-xs font-medium text-[var(--cor-primaria)] hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]"><Flame className="h-3 w-3 text-[var(--cor-sinal)]" /> Ver cobertura ao vivo</Link>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className="rounded-full border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] px-3 py-1.5 font-medium text-[var(--cor-texto)]">{filtrado.length} manchetes • {urgProp.length} urgentes • {totalEditorias} editorias</span>
        <span className="text-[var(--cor-texto-suave)] hidden md:inline">• atualizando</span>
        <Link href="/arquivo" className="font-medium text-[var(--cor-primaria)] hover:underline">Ver arquivo →</Link>
      </div>

      {urgProp.length > 0 && (
        <section aria-label="Ao vivo agora" className="rounded-[var(--raio-lg)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] p-3 shadow-[var(--sombra-1)]">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <h2 className="flex items-center gap-2 text-sm font-bold text-[var(--cor-texto)]"><span className="h-2 w-2 rounded-full bg-[var(--cor-sinal)] motion-safe:animate-pulse" aria-hidden /><Flame className="h-4 w-4 text-[var(--cor-sinal)]" /> Ao vivo agora <span className="rounded-full bg-[var(--cor-erro-suave)] px-2 py-0.5 text-xs font-semibold text-[var(--cor-sinal)]">ao vivo</span></h2>
            <span className="rounded-full border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] px-2.5 py-1 text-xs font-medium text-[var(--cor-texto-suave)]">{urgProp.length} urgentes • deslize para ver mais</span>
          </div>
          <div className="flex gap-3 overflow-x-auto pb-2 [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden snap-x snap-mandatory">
            {urgProp.map((u) => (
              <Link key={`live-${u.tipo}-${u.id}`} href={`/noticia/${u.id}`} className="group flex w-64 shrink-0 snap-start gap-3 rounded-[var(--raio-md)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-2 hover:shadow-[var(--sombra-2)] hover:-translate-y-1 transition-all duration-200 motion-safe:transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]">
                <img src={imagemNoticia(u)} alt="" loading="lazy" className="h-16 w-20 shrink-0 rounded-md object-cover" />
                <div className="min-w-0">
                  <span className="inline-flex items-center gap-1 rounded-full bg-[var(--cor-sinal)] px-1.5 py-0.5 text-[10px] font-bold text-[var(--cor-texto-invertido)]"><span className="h-1 w-1 rounded-full bg-[var(--cor-texto-invertido)] motion-safe:animate-pulse" aria-hidden /> AO VIVO</span>
                  <p className="mt-1 line-clamp-2 text-xs font-semibold leading-tight text-[var(--cor-texto)] group-hover:text-[var(--cor-primaria)] motion-safe:transition-colors">{u.titulo}</p>
                  <p className="text-[11px] capitalize text-[var(--cor-texto-suave)]">{u.categoria} • {timeAgo(u.timestamp)}</p>
                </div>
              </Link>
            ))}
          </div>
        </section>
      )}

      <SecaoRegiao feed={filtrado.length ? filtrado : feedProp} />

      <AdsSlot id="home-topo" formato="horizontal" />

      {isPremium && <p className="flex items-center gap-1.5 rounded-full border border-[var(--cor-premium)] bg-[var(--cor-premium-suave)] px-3 py-1.5 text-xs font-medium text-[var(--cor-premium)]"><Crown className="h-3.5 w-3.5" /> Você navega com menos anúncios — benefício Premium</p>}

      <section className="grid gap-6 md:grid-cols-12">
        <div className="md:col-span-8 space-y-4">
          <div className="flex items-center justify-between gap-2">
            <h2 className="text-lg font-bold text-[var(--cor-texto)]">Manchetes</h2>
            <Link href="/arquivo" className="text-sm font-medium text-[var(--cor-primaria)] hover:underline">Arquivo →</Link>
          </div>
          {filtrado.length === 0 ? (
            <Card className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]"><CardContent className="p-6 text-sm text-[var(--cor-texto-suave)]">Nenhuma manchete nesta editoria. <Link href="/arquivo" className="font-medium text-[var(--cor-primaria)] underline">Ver arquivo</Link> ou <Link href="/personalizar" className="font-medium text-[var(--cor-primaria)] underline">personalizar</Link>.</CardContent></Card>
          ) : (
            <div className={cn("grid gap-4", filtrado.length >= 8 ? "md:grid-cols-4" : "md:grid-cols-2")}>
              {grid.map((n) => (
                <Card key={`${n.tipo}-${n.id}`} className="group overflow-hidden border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] hover:shadow-[var(--sombra-2)] hover:-translate-y-1 transition-all duration-200 motion-safe:transition-all">
                  <Link href={`/noticia/${n.id}`} className="block aspect-[16/9] overflow-hidden bg-[var(--cor-fundo-elevado)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]">
                    <img src={imagemNoticia(n)} alt={n.titulo} loading="lazy" className="h-full w-full object-cover motion-safe:transition motion-safe:duration-300 group-hover:motion-safe:scale-[1.02]" />
                  </Link>
                  <CardContent className="p-4">
                    <div className="mb-2 flex items-center gap-2">
                      <Link href={`/categoria/${encodeURIComponent(n.categoria)}`} className="text-xs font-medium capitalize text-[var(--cor-primaria)] hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] rounded-full">{n.categoria}</Link>
                      <span className="text-xs text-[var(--cor-texto-suave)]">• {timeAgo(n.timestamp)} • {n.numero_fontes} fontes</span>
                      {n.urgente && <span className="ml-auto h-1.5 w-1.5 rounded-full bg-[var(--cor-sinal)] motion-safe:animate-pulse" aria-hidden />}
                    </div>
                    <Link href={`/noticia/${n.id}`} className="line-clamp-2 text-balance text-[15px] font-bold leading-tight text-[var(--cor-texto)] hover:text-[var(--cor-primaria)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] motion-safe:transition-colors">{n.titulo}</Link>
                    <Link href={`/noticia/${n.id}`} className="mt-1 line-clamp-2 block text-sm leading-snug text-[var(--cor-texto-suave)] hover:text-[var(--cor-texto)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] motion-safe:transition-colors">{n.resumo}</Link>
                    <div className="mt-3 flex gap-2">
                      <Button asChild size="sm" className="h-8 bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)] hover:bg-[var(--cor-primaria-hover)]"><Link href={`/noticia/${n.id}`}>Ler agora</Link></Button>
                      <Button size="sm" variant="outline" className="h-8 border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]" onClick={() => toggleSalvar(n)}>{salvos.has(`${n.tipo}-${n.id}`) ? "Salvo" : "Salvar"}</Button>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}

          {hasSignal && resto.length > 0 && (
            <div className="flex items-center gap-2 rounded-full border border-[var(--cor-borda)] bg-[var(--cor-primaria-suave)] px-3 py-2 text-xs text-[var(--cor-texto)]">
              <Info className="h-3.5 w-3.5 shrink-0 text-[var(--cor-primaria)]" />
              <span title={`Porque você vê isso: ${afinidade.slice(0,2).join(", ") || "seu histórico"} — leituras em ${Object.entries(leituras).filter(([,v])=>v>=2).map(([k])=>k).join(", ") || "categorias que você acompanha"}.`}>Porque você vê isso: feed ordenado por afinidade • <Link href="/personalizar" className="font-medium text-[var(--cor-primaria)] underline">ajustar</Link></span>
            </div>
          )}

          {!premiumGeral ? <AdsSlot id="home-infeed" formato="in-feed" /> : <p className="flex items-center gap-1.5 rounded-full border border-dashed border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] px-3 py-2 text-xs text-[var(--cor-texto-suave)]"><Crown className="h-3.5 w-3.5 text-[var(--cor-premium)]" /> Leitura sem interrupção — anúncio removido no Premium</p>}

          {resto.length > 0 && resto.slice(0,3).length>0 && hasSignal && (
            <div className="rounded-[var(--raio-lg)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] p-3">
              <p className="mb-2 text-sm font-bold text-[var(--cor-texto)]">Continuar lendo</p>
              <div className="grid gap-2">
                {resto.slice(0,3).map(n=>(
                  <Link key={`cont-${n.tipo}-${n.id}`} href={`/noticia/${n.id}`} className="flex items-center justify-between gap-2 rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] px-3 py-2 text-sm hover:bg-[var(--cor-borda)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]">
                    <span className="line-clamp-1 font-medium text-[var(--cor-texto)]">{n.titulo}</span>
                    <span className="shrink-0 text-xs text-[var(--cor-primaria)]">Ler →</span>
                  </Link>
                ))}
              </div>
            </div>
          )}

          {resto.length > 0 && (
            <div className="grid gap-3">
              {resto.map((n) => (
                <div key={`${n.tipo}-${n.id}`} className="group flex gap-3 rounded-[var(--raio-lg)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] p-3 hover:shadow-[var(--sombra-2)] hover:-translate-y-1 transition-all duration-200 motion-safe:transition-all">
                  <Link href={`/noticia/${n.id}`} className="hidden aspect-[16/9] h-20 w-32 shrink-0 overflow-hidden rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] md:block">
                    <img src={imagemNoticia(n)} alt="" loading="lazy" className="h-full w-full object-cover motion-safe:transition motion-safe:duration-300 group-hover:motion-safe:scale-[1.02]" />
                  </Link>
                  <div className="min-w-0 flex-1">
                    <p className="text-xs text-[var(--cor-texto-suave)]"><Link href={`/categoria/${encodeURIComponent(n.categoria)}`} className="capitalize hover:text-[var(--cor-primaria)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] rounded-full">{n.categoria}</Link> • {timeAgo(n.timestamp)} • {n.numero_fontes} fontes</p>
                    <Link href={`/noticia/${n.id}`} className="line-clamp-2 text-sm font-semibold leading-tight text-[var(--cor-texto)] hover:text-[var(--cor-primaria)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] motion-safe:transition-colors">{n.titulo}</Link>
                    <div className="mt-2 flex gap-2">
                      <Link href={`/noticia/${n.id}`} className="text-xs font-medium text-[var(--cor-primaria)] hover:underline">Ler agora →</Link>
                      <button onClick={() => toggleSalvar(n)} className="text-xs font-medium text-[var(--cor-texto-suave)] hover:text-[var(--cor-texto)]">{salvos.has(`${n.tipo}-${n.id}`) ? "Salvo ✓" : "Salvar"}</button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
          {porEditoria.length > 0 && (
            <section aria-label="Por editoria" className="space-y-3">
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-bold text-[var(--cor-texto)]">Por editoria</h2>
                <Link href="/editorias" className="text-sm font-medium text-[var(--cor-primaria)] hover:underline">Ver todas →</Link>
              </div>
              <div className="grid gap-4 md:grid-cols-4">
                {porEditoria.map((col) => (
                  <div key={col.cat} className="space-y-3">
                    <Link href={`/categoria/${encodeURIComponent(col.cat)}`} className="text-sm font-bold capitalize text-[var(--cor-primaria)] hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]">{col.cat}</Link>
                    {col.items.map((n) => (
                      <Card key={`ed-${n.tipo}-${n.id}`} className="group overflow-hidden border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] hover:shadow-[var(--sombra-2)] hover:-translate-y-1 transition-all duration-200 motion-safe:transition-all">
                        <Link href={`/noticia/${n.id}`} className="block aspect-[16/9] overflow-hidden bg-[var(--cor-fundo-elevado)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]"><img src={imagemNoticia(n)} alt={n.titulo} loading="lazy" className="h-full w-full object-cover motion-safe:transition motion-safe:duration-300 group-hover:motion-safe:scale-[1.02]" /></Link>
                        <CardContent className="p-3">
                          <Link href={`/noticia/${n.id}`} className="line-clamp-2 text-sm font-bold leading-tight text-[var(--cor-texto)] hover:text-[var(--cor-primaria)] motion-safe:transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]">{n.titulo}</Link>
                          <p className="mt-1 text-xs text-[var(--cor-texto-suave)]">{timeAgo(n.timestamp)} • {n.numero_fontes} fontes</p>
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                ))}
              </div>
            </section>
          )}

          {recomendado.length > 0 && (
            <section aria-label="Recomendado para você" className="space-y-3 rounded-[var(--raio-lg)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] p-4">
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-bold text-[var(--cor-texto)]">Recomendado para você</h2>
                <Link href="/personalizar" className="text-xs font-medium text-[var(--cor-primaria)] hover:underline">Personalizar →</Link>
              </div>
              <p className="text-xs text-[var(--cor-texto-suave)]">Baseado em {afinidade.slice(0, 2).join(", ") || "suas leituras"} • {recomendado.length} sugestões</p>
              <div className="grid gap-4 md:grid-cols-3">
                {recomendado.map((n) => (
                  <Card key={`rec-${n.tipo}-${n.id}`} className="group overflow-hidden border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] hover:shadow-[var(--sombra-2)] hover:-translate-y-1 transition-all duration-200 motion-safe:transition-all">
                    <Link href={`/noticia/${n.id}`} className="block aspect-video overflow-hidden focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]"><img src={imagemNoticia(n)} alt={n.titulo} loading="lazy" className="h-full w-full object-cover motion-safe:transition motion-safe:duration-300 group-hover:motion-safe:scale-[1.02]" /></Link>
                    <CardContent className="p-3">
                      <Link href={`/categoria/${encodeURIComponent(n.categoria)}`} className="text-xs font-medium capitalize text-[var(--cor-primaria)] hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] rounded-full">{n.categoria}</Link>
                      <Link href={`/noticia/${n.id}`} className="mt-1 line-clamp-2 block text-sm font-bold leading-tight text-[var(--cor-texto)] hover:text-[var(--cor-primaria)] motion-safe:transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]">{n.titulo}</Link>
                      <p className="mt-1 text-xs text-[var(--cor-texto-suave)]">{timeAgo(n.timestamp)} • {n.numero_fontes} fontes</p>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </section>
          )}

          <div className="rounded-[var(--raio-lg)] border border-dashed border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] px-4 py-6 text-center">
            <p className="text-sm text-[var(--cor-texto-suave)]">Fim — veja mais em <Link href="/arquivo" className="font-medium text-[var(--cor-primaria)] underline">Arquivo</Link> ou <Link href="/personalizar" className="font-medium text-[var(--cor-primaria)] underline">Personalizar</Link>.</p>
          </div>
        </div>

        <aside className="md:col-span-4 space-y-4">
          <Card className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
            <CardContent className="p-4">
              <h3 className="mb-3 text-sm font-bold text-[var(--cor-texto)]">Explorar editorias</h3>
              <div className="flex gap-2 overflow-x-auto pb-2 [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
                <button onClick={() => setFiltro(null)} className={cn("shrink-0 rounded-full border px-3 py-1.5 text-sm font-medium transition", !filtro ? "border-[var(--cor-primaria)] bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]" : "border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] text-[var(--cor-texto)] hover:bg-[var(--cor-primaria-suave)]")}>Tudo</button>
                {EDITORIAS.map((c) => (
                  <button key={c} onClick={() => setFiltro(filtro === c ? null : c)} className={cn("shrink-0 rounded-full border px-3 py-1.5 text-sm font-medium capitalize transition", filtro === c ? "border-[var(--cor-primaria)] bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]" : "border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] text-[var(--cor-texto)] hover:bg-[var(--cor-primaria-suave)]")}>{c}</button>
                ))}
              </div>
              <Link href="/editorias" className="mt-2 inline-flex text-xs font-medium text-[var(--cor-primaria)] hover:underline">Ver todas →</Link>
            </CardContent>
          </Card>

          <Card className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
            <CardContent className="p-4">
              <h3 className="mb-3 flex items-center gap-2 text-sm font-bold text-[var(--cor-texto)]"><Flame className="h-4 w-4 text-[var(--cor-sinal)]" /> Em alta</h3>
              <ol className="space-y-1">
                {urgProp.slice(0, 5).map((u, i) => (
                  <li key={`${u.tipo}-${u.id}`} className="flex gap-3 rounded-md p-2 hover:bg-[var(--cor-fundo-elevado)]">
                    <span className="w-6 shrink-0 text-center text-lg font-bold leading-none text-[var(--cor-texto-suave)]">{i + 1}</span>
                    <div className="min-w-0 flex-1">
                      <Link href={`/noticia/${u.id}`} className="line-clamp-2 text-sm font-medium leading-tight text-[var(--cor-texto)] hover:text-[var(--cor-primaria)] motion-safe:transition-colors">{u.titulo}</Link>
                      <p className="mt-0.5 text-xs text-[var(--cor-texto-suave)]">{u.categoria} • {timeAgo(u.timestamp)}</p>
                    </div>
                  </li>
                ))}
                {!urgProp.length && <p className="text-sm text-[var(--cor-texto-suave)]">Nenhum destaque urgente no momento.</p>}
              </ol>
              <Link href="/ao-vivo" className="mt-3 inline-flex text-xs font-medium text-[var(--cor-primaria)] hover:underline">Ver cobertura ao vivo →</Link>
            </CardContent>
          </Card>

          <Card className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
            <CardContent className="p-4">
              <h3 className="text-sm font-bold text-[var(--cor-texto)]">Para você</h3>
              {afinidade.length ? (
                <>
                  <p className="mt-1 text-sm leading-snug text-[var(--cor-texto-suave)]">Baseado no que você acompanha:</p>
                  <div className="mt-2 flex flex-wrap gap-1.5">{afinidade.slice(0, 6).map((c) => (<Link key={c} href={`/categoria/${encodeURIComponent(c)}`} className="rounded-full border border-[var(--cor-borda)] bg-[var(--cor-primaria-suave)] px-2.5 py-1 text-xs font-medium capitalize text-[var(--cor-primaria)] hover:bg-[var(--cor-fundo-elevado)]">{c}</Link>))}</div>
                  <Link href="/personalizar" className="mt-3 inline-flex text-xs font-medium text-[var(--cor-primaria)] hover:underline">Ajustar preferências →</Link>
                </>
              ) : (
                <>
                  <p className="mt-1 text-sm leading-snug text-[var(--cor-texto-suave)]">Personalize suas editorias favoritas para ver manchetes mais relevantes primeiro.</p>
                  <Button asChild size="sm" className="mt-3 bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)] hover:bg-[var(--cor-primaria-hover)]"><Link href="/personalizar">Personalizar</Link></Button>
                </>
              )}
            </CardContent>
          </Card>

          <Card className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
            <CardContent className="p-4">
              <h3 className="flex items-center gap-2 text-sm font-bold text-[var(--cor-texto)]"><Mail className="h-4 w-4 text-[var(--cor-primaria)]" /> Newsletter</h3>
              <p className="mt-1 text-sm text-[var(--cor-texto-suave)]">Resumo diário sem ruído — escolha editorias e período.</p>
              <form action="/newsletter" className="mt-3 flex gap-2">
                <Input placeholder="seu@email.com" type="email" required aria-label="Email para newsletter" className="h-9 bg-[var(--cor-fundo-card)]" />
                <Button type="submit" className="h-9 shrink-0 bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)] hover:bg-[var(--cor-primaria-hover)]">Assinar</Button>
              </form>
              <p className="mt-2 text-xs text-[var(--cor-texto-suave)]">Ao assinar você concorda com <Link href="/privacidade" className="underline">privacidade</Link>.</p>
            </CardContent>
          </Card>

          <AdsSlot id="home-sidebar" formato="retangulo" />
        </aside>
      </section>
      <AdsSlot id="home-footer" formato="horizontal" className="my-6" />
    </div>
  );
}
