"use client";
import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Progress } from "@/components/ui/progress";
import { AdsSlot } from "@/components/AdsSlot";
import { AcoesNoticia } from "./[id]/acoes";
import { Voltar } from "./[id]/voltar";
import { temImagemReal } from "@/lib/imagens";
import type { FeedDetalhe } from "@/lib/api";
import { Clock3, MapPin, ListChecks, MessageSquare, Printer, ALargeSmall, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";

type Relacionado = { id: number; titulo: string; categoria: string; imagem_url?: string; timestamp?: string };

function fmt(iso: string) {
  try {
    return new Intl.DateTimeFormat("pt-BR", { dateStyle: "long", timeStyle: "short" }).format(new Date(iso));
  } catch {
    return iso;
  }
}

function frasesResumo(resumo: string, max = 3): string[] {
  const partes = resumo
    .split(/(?<=[.!?])\s+/)
    .map((s) => s.trim())
    .filter(Boolean);
  if (!partes.length && resumo.trim()) return [resumo.trim()];
  return partes.slice(0, max);
}

function tempoLeitura(texto: string): number {
  const palavras = texto.trim().split(/\s+/).filter(Boolean).length;
  return Math.max(1, Math.round(palavras / 200));
}

export function LeituraPremium({
  detalhe: d,
  relacionados,
  heroSrc,
  imagemReal,
}: {
  detalhe: FeedDetalhe;
  relacionados: Relacionado[];
  heroSrc: string;
  imagemReal: string;
}) {
  const [progresso, setProgresso] = useState(0);
  const [fonteGrande, setFonteGrande] = useState(false);

  useEffect(() => {
    const onScroll = () => {
      const el = document.documentElement;
      const total = el.scrollHeight - el.clientHeight;
      setProgresso(total > 0 ? Math.min(100, Math.round((el.scrollTop / total) * 100)) : 0);
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  const bullets = useMemo(() => frasesResumo(d.fontes[0]?.resumo || ""), [d]);
  const minutos = useMemo(
    () => tempoLeitura([d.titulo, ...d.fontes.map((f) => f.resumo || "")].join(" ")),
    [d]
  );
  const temReal = temImagemReal({ imagem_url: imagemReal });
  const prevId = Math.max(1, d.id - 1);
  const nextId = d.id + 1;
  const hostname = (url: string) => {
    try {
      return new URL(url).hostname;
    } catch {
      return url;
    }
  };

  return (
    <div>
      <div className="fixed inset-x-0 top-0 z-[var(--z-cabecalho)]" aria-hidden>
        <Progress value={progresso} className="h-1 rounded-none" />
      </div>

      <article className="mx-auto max-w-3xl space-y-5">
        <Voltar categoria={d.categoria} />
        <nav aria-label="Trilha" className="flex flex-wrap items-center gap-2 text-xs text-[var(--cor-texto-suave)]">
          <Link href="/" className="hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]">Início</Link>
          <span aria-hidden>›</span>
          <Link href={`/categoria/${encodeURIComponent(d.categoria)}`} className="capitalize hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]">{d.categoria}</Link>
          <span aria-hidden>›</span>
          <span className="line-clamp-1 max-w-[40ch] text-[var(--cor-texto)]">{d.titulo}</span>
        </nav>

        <div className="flex flex-wrap items-center gap-2">
          <Link href={`/categoria/${encodeURIComponent(d.categoria)}`} className="focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] rounded-full">
            <Badge variant="outline" className="border-[var(--cor-borda)] capitalize hover:bg-[var(--cor-primaria-suave)] hover:text-[var(--cor-primaria)]">{d.categoria}</Badge>
          </Link>
          {d.urgente && <Badge className="bg-[var(--cor-sinal)] text-[var(--cor-texto-invertido)] motion-safe:animate-pulse">urgente</Badge>}
          <span className="inline-flex items-center gap-1 text-xs text-[var(--cor-texto-suave)]"><Clock3 className="h-3 w-3" />{fmt(d.timestamp)} • {minutos} min de leitura • {d.fontes.length} {d.fontes.length === 1 ? "fonte" : "fontes"}</span>
        </div>

        <h1 className="text-balance font-serif text-3xl font-bold leading-[1.15] tracking-tight text-[var(--cor-texto)] md:text-4xl">{d.titulo}</h1>
        <p className="text-pretty text-base leading-relaxed text-[var(--cor-texto-suave)]">{d.fontes[0]?.resumo?.slice(0, 180)}{(d.fontes[0]?.resumo?.length || 0) > 180 ? "…" : ""}</p>

        <div className="group relative overflow-hidden rounded-[var(--raio-lg)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] shadow-[var(--sombra-2)]">
          <div className="relative aspect-[16/9] overflow-hidden">
            <img src={heroSrc} alt={d.titulo} loading="eager" className="h-full w-full object-cover" />
            <div className="pointer-events-none absolute inset-0" style={{ background: "linear-gradient(180deg, transparent 55%, rgba(11,11,26,0.55) 100%)" }} aria-hidden />
            <div className="absolute bottom-3 left-3 right-3 flex flex-wrap items-center gap-2">
              <Badge className="bg-[var(--cor-fundo-card)]/90 capitalize text-[var(--cor-texto)] backdrop-blur">{d.categoria}</Badge>
              {d.urgente && <Badge className="bg-[var(--cor-sinal)] text-[var(--cor-texto-invertido)]">Ao vivo</Badge>}
              <span className="ml-auto rounded-full bg-[var(--cor-fundo-card)]/85 px-2.5 py-1 text-xs text-[var(--cor-texto-suave)] backdrop-blur">{d.fontes.length} {d.fontes.length === 1 ? "fonte citada" : "fontes citadas"}</span>
            </div>
          </div>
          <p className="px-3 py-2 text-xs text-[var(--cor-texto-suave)]">{temReal ? "Imagem da cobertura original • Crédito: fontes citadas abaixo" : `Imagem ilustrativa • Crédito: fontes citadas abaixo`}</p>
        </div>

        <AdsSlot id="noticia-topo" formato="horizontal" />

        <div className="sticky top-14 z-[var(--z-conteudo-elevado)] rounded-[var(--raio-lg)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]/90 p-2 shadow-[var(--sombra-1)] backdrop-blur">
          <div className="flex flex-wrap items-center gap-2">
            <div className="min-w-0 flex-1">
              <AcoesNoticia entrada={{ tipo: d.tipo, id: d.id, titulo: d.titulo, resumo: d.fontes[0]?.resumo || "", categoria: d.categoria, urgente: d.urgente, numero_fontes: d.fontes.length, timestamp: d.timestamp, imagem_url: imagemReal }} />
            </div>
            <div className="flex items-center gap-1">
              <Button variant="ghost" size="sm" onClick={() => setFonteGrande((v) => !v)} aria-pressed={fonteGrande} title="Ajustar tamanho do texto" className="min-h-[44px] gap-1"><ALargeSmall className="h-4 w-4" /> {fonteGrande ? "A−" : "A+"}</Button>
              <Button variant="ghost" size="sm" onClick={() => window.print()} title="Imprimir" className="min-h-[44px]"><Printer className="h-4 w-4" /><span className="sr-only">Imprimir</span></Button>
            </div>
          </div>
        </div>

        <Card className="overflow-hidden border-[var(--cor-primaria)] bg-[var(--cor-fundo-card)] shadow-[var(--sombra-1)]">
          <CardContent className="p-5">
            <h2 className="flex items-center gap-2 text-sm font-bold tracking-tight text-[var(--cor-texto)]"><ListChecks className="h-4 w-4 text-[var(--cor-primaria)]" /> Em 30 segundos</h2>
            <ul className="mt-3 space-y-2">
              {bullets.map((b, i) => (
                <li key={i} className="flex gap-2.5 text-sm leading-relaxed text-[var(--cor-texto)]">
                  <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[var(--cor-primaria-suave)] text-xs font-bold text-[var(--cor-primaria)]">{i + 1}</span>
                  <span>{b}</span>
                </li>
              ))}
            </ul>
            <div className="mt-4 flex flex-wrap gap-2 text-xs">
              <a href="#resumo-completo" className="rounded-full border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] px-3 py-1.5 font-medium text-[var(--cor-texto)] hover:bg-[var(--cor-primaria-suave)] hover:text-[var(--cor-primaria)]">Resumo</a>
              <a href="#fontes" className="rounded-full border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] px-3 py-1.5 font-medium text-[var(--cor-texto)] hover:bg-[var(--cor-primaria-suave)] hover:text-[var(--cor-primaria)]">Fontes ({d.fontes.length})</a>
              <a href="#veja-tambem" className="rounded-full border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] px-3 py-1.5 font-medium text-[var(--cor-texto)] hover:bg-[var(--cor-primaria-suave)] hover:text-[var(--cor-primaria)]">Veja também</a>
            </div>
          </CardContent>
        </Card>

        <Card className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
          <CardContent id="resumo-completo" className={cn("scroll-mt-24 p-5 md:p-6", fonteGrande ? "text-lg" : "text-base")}>
            <div className={cn("space-y-4 leading-relaxed text-[var(--cor-texto)]", fonteGrande ? "leading-loose" : "leading-relaxed")}>
              <p className="text-pretty first-letter:float-left first-letter:mr-2 first-letter:font-serif first-letter:text-5xl first-letter:font-bold first-letter:leading-[0.9] first-letter:text-[var(--cor-primaria)]">{d.fontes[0]?.resumo}</p>
              {d.fontes.slice(1, 3).map((f, i) => (
                f.resumo && f.resumo !== d.fontes[0]?.resumo ? (
                  <blockquote key={i} className="rounded-[var(--raio-md)] border-l-4 border-[var(--cor-primaria)] bg-[var(--cor-fundo-elevado)] px-4 py-3">
                    <p className="text-pretty text-sm italic leading-relaxed text-[var(--cor-texto)]">“{f.resumo}”</p>
                    <cite className="mt-1 block text-xs not-italic text-[var(--cor-texto-suave)]">— {f.nome_fonte}</cite>
                  </blockquote>
                ) : null
              ))}
            </div>

            <AdsSlot id="noticia-infeed" formato="in-feed" className="my-5" />

            <Separator className="my-5 bg-[var(--cor-borda)]" />

            <h2 id="fontes" className="scroll-mt-24 text-lg font-bold text-[var(--cor-texto)]">Fontes apuradas <span className="ml-1 rounded-full bg-[var(--cor-fundo-elevado)] px-2 py-0.5 align-middle text-xs font-medium text-[var(--cor-texto-suave)]">{d.fontes.length}</span></h2>
            <ul className="mt-3 space-y-2">
              {d.fontes.map((f, i) => (
                <li key={i} className="group rounded-[var(--raio-md)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-3 transition hover:shadow-[var(--sombra-1)]">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="flex h-7 w-7 items-center justify-center rounded-full bg-[var(--cor-primaria-suave)] text-xs font-bold text-[var(--cor-primaria)]">{i + 1}</span>
                    <a href={f.url_fonte_original} target="_blank" rel="noopener noreferrer" className="font-semibold text-[var(--cor-primaria)] hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]">{f.nome_fonte}</a>
                    <span className="text-xs text-[var(--cor-texto-suave)]">↗ {hostname(f.url_fonte_original)}</span>
                    <a href={f.url_fonte_original} target="_blank" rel="noopener noreferrer" className="ml-auto inline-flex min-h-[36px] items-center rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] px-3 text-xs font-medium text-[var(--cor-texto)] hover:bg-[var(--cor-primaria-suave)] hover:text-[var(--cor-primaria)]">Abrir na fonte ↗</a>
                  </div>
                  {f.resumo && <p className="mt-2 text-sm leading-relaxed text-[var(--cor-texto-suave)]">{f.resumo}</p>}
                </li>
              ))}
            </ul>
            <p className="mt-3 text-xs text-[var(--cor-texto-suave)]">Rastreabilidade total: cada trecho acima pertence à fonte indicada • <Link href="/sobre" className="underline hover:text-[var(--cor-texto)]">como apuramos</Link></p>
          </CardContent>
        </Card>

        <nav aria-label="Navegação da matéria" className="grid gap-2 sm:grid-cols-2">
          <Button asChild variant="outline" className="min-h-[52px] justify-start border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] px-4 text-left"><Link href={`/noticia/${prevId}`}><span className="block text-xs font-normal text-[var(--cor-texto-suave)]">← Anterior</span><span className="block truncate text-sm font-semibold">Matéria #{prevId}</span></Link></Button>
          <Button asChild className="min-h-[52px] justify-end bg-[var(--cor-primaria)] px-4 text-right text-[var(--cor-texto-invertido)]"><Link href={`/noticia/${nextId}`}><span className="block text-xs font-normal opacity-80">Próxima →</span><span className="block truncate text-sm font-semibold">Matéria #{nextId}</span></Link></Button>
        </nav>

        <Card id="veja-tambem" className="scroll-mt-24 border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
          <CardContent className="p-4 md:p-5">
            <h2 className="flex items-center justify-between text-base font-bold text-[var(--cor-texto)]">Você pode gostar <Link href={`/categoria/${encodeURIComponent(d.categoria)}`} className="text-xs font-medium normal-case text-[var(--cor-primaria)] hover:underline">mais em {d.categoria} →</Link></h2>
            {relacionados.length ? (
              <div className="mt-3 grid gap-3 sm:grid-cols-2">
                {relacionados.slice(0, 6).map((r) => (
                  <Link key={r.id} href={`/noticia/${r.id}`} className="group flex gap-3 rounded-[var(--raio-md)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-2 transition hover:-translate-y-0.5 hover:shadow-[var(--sombra-1)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]">
                    <span className="block h-16 w-24 shrink-0 overflow-hidden rounded-md bg-[var(--cor-fundo-card)]">
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img src={r.imagem_url || `https://picsum.photos/seed/${encodeURIComponent(`${r.categoria}-${r.id}`)}/400/225`} alt="" loading="lazy" className="h-full w-full object-cover transition duration-300 group-hover:scale-[1.04]" />
                    </span>
                    <span className="min-w-0">
                      <span className="block text-[11px] font-medium capitalize text-[var(--cor-primaria)]">{r.categoria}</span>
                      <span className="line-clamp-2 block text-sm font-semibold leading-tight text-[var(--cor-texto)] group-hover:text-[var(--cor-primaria)]">{r.titulo}</span>
                      <span className="mt-1 inline-flex items-center gap-1 text-xs text-[var(--cor-primaria)]">Ler <ChevronRight className="h-3 w-3" /></span>
                    </span>
                  </Link>
                ))}
              </div>
            ) : (
              <p className="mt-2 text-sm text-[var(--cor-texto-suave)]">Sem relacionados — <Link href={`/categoria/${encodeURIComponent(d.categoria)}`} className="text-[var(--cor-primaria)] underline">ver mais em {d.categoria}</Link> ou <Link href="/arquivo" className="text-[var(--cor-primaria)] underline">arquivo</Link>.</p>
            )}
            <div className="mt-4 flex flex-wrap gap-2">
              <Button asChild variant="outline" size="sm" className="border-[var(--cor-borda)]"><Link href={`/categoria/${encodeURIComponent(d.categoria)}`} className="capitalize">Ver editoria</Link></Button>
              <Button asChild variant="outline" size="sm" className="border-[var(--cor-borda)]"><Link href="/arquivo">Arquivo</Link></Button>
              <Button asChild size="sm" className="bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]"><Link href="/personalizar">Personalizar feed</Link></Button>
            </div>
          </CardContent>
        </Card>

        <Card className="border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)]">
          <CardContent className="flex flex-wrap items-center gap-3 p-4">
            <span className="flex h-9 w-9 items-center justify-center rounded-full bg-[var(--cor-primaria-suave)] text-[var(--cor-primaria)]"><MessageSquare className="h-4 w-4" /></span>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-semibold text-[var(--cor-texto)]">O que você achou desta cobertura?</p>
              <p className="text-xs text-[var(--cor-texto-suave)]">Participe da conversa com outros leitores na comunidade.</p>
            </div>
            <Button asChild size="sm" className="bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]"><Link href="/comunidade">Participar</Link></Button>
          </CardContent>
        </Card>

        <Card className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
          <CardContent className="flex flex-wrap items-center gap-2 p-4 text-xs text-[var(--cor-texto-suave)]">
            <MapPin className="h-3.5 w-3.5 text-[var(--cor-primaria)]" />
            <span>Continue explorando por região:</span>
            <Link href="/radar" className="font-medium text-[var(--cor-primaria)] hover:underline">Radar regional</Link>
            <span aria-hidden>•</span>
            <Link href="/buscar" className="font-medium text-[var(--cor-primaria)] hover:underline">Buscar</Link>
            <span aria-hidden>•</span>
            <Link href="/comunidade" className="font-medium text-[var(--cor-primaria)] hover:underline">Comunidade</Link>
          </CardContent>
        </Card>

        <AdsSlot id="noticia-pos" formato="horizontal" className="my-2" />
      </article>
    </div>
  );
}
