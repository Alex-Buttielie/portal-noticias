"use client";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { AdsSlot } from "@/components/AdsSlot";
import { imagemNoticia } from "@/lib/imagens";
import { categoriasPorAfinidade, ordenarPorGosto } from "@/lib/personalizar";
import { obterTodasLeituras } from "@/lib/intent";
import { alternarSalvo, estaSalvo } from "@/lib/bookmarks";
import { useAuth } from "@/lib/auth-context";
import type { FeedEntrada } from "@/lib/api";
import { ArrowRight, Bookmark, BookmarkCheck, Clock3, Flame, Mail, Info, Crown } from "lucide-react";
import { cn } from "@/lib/utils";

const EDITORIAS = ["política", "economia", "tecnologia", "esportes", "cultura", "saúde", "mundo", "cidades"];

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

  const hero = filtrado[0];
  const grid = filtrado.slice(1, 5);
  const resto = filtrado.slice(5);
  const afinidade = useMemo(() => {
    try { return categoriasPorAfinidade(perfil); } catch { return []; }
  }, [perfil]);

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

  if (!hero) return (<Card className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]"><CardContent className="p-6 text-center text-sm text-[var(--cor-texto-suave)]">Nenhuma manchete por aqui. <Link href="/arquivo" className="font-medium text-[var(--cor-primaria)] underline">Ver arquivo</Link> • <Link href="/personalizar" className="font-medium text-[var(--cor-primaria)] underline">Personalizar</Link></CardContent></Card>);

  return (
    <div className="space-y-6">
      <section className="relative overflow-hidden rounded-[var(--raio-lg)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] shadow-[var(--sombra-1)]">
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
            <Link href={`/noticia/${hero.id}`} className="group relative block overflow-hidden rounded-[var(--raio-lg)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)]">
              <span className="block aspect-[16/9] overflow-hidden">
                <img src={imagemNoticia(hero)} alt={hero.titulo} loading="eager" className="h-full w-full object-cover transition duration-300 group-hover:scale-[1.02]" />
              </span>
              {hero.urgente && <span className="absolute left-3 top-3 rounded-full bg-[var(--cor-sinal)] px-2.5 py-1 text-xs font-bold text-[var(--cor-texto-invertido)] shadow">Ao vivo</span>}
            </Link>
            <div className="flex flex-col gap-3 py-1">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="outline" className="border-[var(--cor-borda)] capitalize text-[var(--cor-texto-suave)]">{hero.categoria}</Badge>
                <span className="inline-flex items-center gap-1 text-xs text-[var(--cor-texto-suave)]"><Clock3 className="h-3 w-3" />{timeAgo(hero.timestamp)} • {hero.numero_fontes} fontes</span>
                {hero.urgente && <span className="inline-flex items-center gap-1 rounded-full bg-[var(--cor-erro-suave)] px-2 py-0.5 text-xs font-medium text-[var(--cor-sinal)]"><span className="h-1.5 w-1.5 rounded-full bg-[var(--cor-sinal)]" aria-hidden /> Urgente</span>}
              </div>
              <Link href={`/noticia/${hero.id}`} className="text-balance text-2xl font-bold leading-tight text-[var(--cor-texto)] hover:text-[var(--cor-primaria)] md:text-3xl">{hero.titulo}</Link>
              <p className="line-clamp-3 text-sm leading-relaxed text-[var(--cor-texto-suave)]">{hero.resumo}</p>
              <div className="mt-1 flex flex-wrap gap-2">
                <Button asChild className="bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)] hover:bg-[var(--cor-primaria-hover)]"><Link href={`/noticia/${hero.id}`}>Ler agora <ArrowRight className="ml-1 h-4 w-4" /></Link></Button>
                <Button variant="outline" className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]" onClick={() => toggleSalvar(hero)}>
                  {salvos.has(`${hero.tipo}-${hero.id}`) ? <><BookmarkCheck className="mr-1 h-4 w-4" /> Salvo</> : <><Bookmark className="mr-1 h-4 w-4" /> Salvar</>}
                </Button>
              </div>
              <Link href="/ao-vivo" className="mt-1 inline-flex items-center gap-1 text-xs font-medium text-[var(--cor-primaria)] hover:underline"><Flame className="h-3 w-3 text-[var(--cor-sinal)]" /> Ver cobertura ao vivo</Link>
            </div>
          </div>
        </div>
      </section>

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
            <div className="grid gap-4 md:grid-cols-2">
              {grid.map((n) => (
                <Card key={`${n.tipo}-${n.id}`} className="bento bento-hover group overflow-hidden border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
                  <Link href={`/noticia/${n.id}`} className="block aspect-[16/9] overflow-hidden bg-[var(--cor-fundo-elevado)]">
                    <img src={imagemNoticia(n)} alt={n.titulo} loading="lazy" className="h-full w-full object-cover transition duration-300 group-hover:scale-[1.02]" />
                  </Link>
                  <CardContent className="p-4">
                    <div className="mb-2 flex items-center gap-2">
                      <span className="text-xs font-medium capitalize text-[var(--cor-primaria)]">{n.categoria}</span>
                      <span className="text-xs text-[var(--cor-texto-suave)]">• {timeAgo(n.timestamp)} • {n.numero_fontes} fontes</span>
                      {n.urgente && <span className="ml-auto h-1.5 w-1.5 rounded-full bg-[var(--cor-sinal)]" aria-hidden />}
                    </div>
                    <Link href={`/noticia/${n.id}`} className="line-clamp-2 text-balance text-[15px] font-bold leading-tight text-[var(--cor-texto)] hover:text-[var(--cor-primaria)]">{n.titulo}</Link>
                    <p className="mt-1 line-clamp-2 text-sm leading-snug text-[var(--cor-texto-suave)]">{n.resumo}</p>
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

          {!isPremium ? <AdsSlot id="home-infeed" formato="in-feed" /> : <p className="flex items-center gap-1.5 rounded-full border border-dashed border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] px-3 py-2 text-xs text-[var(--cor-texto-suave)]"><Crown className="h-3.5 w-3.5 text-[var(--cor-premium)]" /> Leitura sem interrupção — anúncio removido no Premium</p>}

          {resto.length > 0 && resto.slice(0,3).length>0 && hasSignal && (
            <div className="rounded-[var(--raio-lg)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] p-3">
              <p className="mb-2 text-sm font-bold text-[var(--cor-texto)]">Continuar lendo</p>
              <div className="grid gap-2">
                {resto.slice(0,3).map(n=>(
                  <Link key={`cont-${n.tipo}-${n.id}`} href={`/noticia/${n.id}`} className="flex items-center justify-between gap-2 rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] px-3 py-2 text-sm hover:bg-[var(--cor-borda)]">
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
                <div key={`${n.tipo}-${n.id}`} className="flex gap-3 rounded-[var(--raio-lg)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] p-3 transition hover:shadow-[var(--sombra-1)]">
                  <Link href={`/noticia/${n.id}`} className="hidden aspect-[16/9] h-20 w-32 shrink-0 overflow-hidden rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] md:block">
                    <img src={imagemNoticia(n)} alt="" loading="lazy" className="h-full w-full object-cover" />
                  </Link>
                  <div className="min-w-0 flex-1">
                    <p className="text-xs text-[var(--cor-texto-suave)]">{n.categoria} • {timeAgo(n.timestamp)} • {n.numero_fontes} fontes</p>
                    <Link href={`/noticia/${n.id}`} className="line-clamp-2 text-sm font-semibold leading-tight text-[var(--cor-texto)] hover:text-[var(--cor-primaria)]">{n.titulo}</Link>
                    <div className="mt-2 flex gap-2">
                      <Link href={`/noticia/${n.id}`} className="text-xs font-medium text-[var(--cor-primaria)] hover:underline">Ler agora →</Link>
                      <button onClick={() => toggleSalvar(n)} className="text-xs font-medium text-[var(--cor-texto-suave)] hover:text-[var(--cor-texto)]">{salvos.has(`${n.tipo}-${n.id}`) ? "Salvo ✓" : "Salvar"}</button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
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
                      <Link href={`/noticia/${u.id}`} className="line-clamp-2 text-sm font-medium leading-tight text-[var(--cor-texto)] hover:text-[var(--cor-primaria)]">{u.titulo}</Link>
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
