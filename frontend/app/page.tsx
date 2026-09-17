import type { Metadata } from "next";
import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { SITE_DESCRIPTION, SITE_NAME } from "@/lib/site";
import { obterFeed, obterUrgentes, type FeedEntrada } from "@/lib/api";
import { imagemNoticia } from "@/lib/imagens";
import { Radio, Flame, ArrowRight, Mail, Sparkles } from "lucide-react";
import { AdsSlot } from "@/components/AdsSlot";

export const metadata: Metadata = {
  title: SITE_NAME,
  description: SITE_DESCRIPTION,
};

export const revalidate = 60;

const MOCK: FeedEntrada[] = [
  { tipo: "cluster", id: 1, titulo: "Mercados reagem a novo ciclo de juros com volatilidade contida", resumo: "Analistas projetam estabilidade após sinalização do banco central.", categoria: "economia", urgente: true, numero_fontes: 4, timestamp: new Date().toISOString() },
  { tipo: "item", id: 2, titulo: "Tecnologia quântica ganha protótipo nacional", resumo: "Pesquisadores anunciam avanço em computação de baixa temperatura.", categoria: "tecnologia", urgente: false, numero_fontes: 3, timestamp: new Date().toISOString() },
  { tipo: "cluster", id: 3, titulo: "Clima extremo mobiliza capitais do Sudeste", resumo: "Defesa civil emite alerta para chuvas intensas nas próximas 48h.", categoria: "cidades", urgente: true, numero_fontes: 5, timestamp: new Date().toISOString() },
  { tipo: "item", id: 4, titulo: "Seleção confirma amistosos antes das eliminatórias", resumo: "Comissão técnica testa novas formações no meio-campo.", categoria: "esportes", urgente: false, numero_fontes: 2, timestamp: new Date().toISOString() },
  { tipo: "item", id: 5, titulo: "Festival ocupa centro histórico com arte imersiva", resumo: "Instalações de luz e som transformam praças em galerias a céu aberto.", categoria: "cultura", urgente: false, numero_fontes: 2, timestamp: new Date().toISOString() },
  { tipo: "item", id: 6, titulo: "Saúde amplia cobertura vacinal em 12 capitais", resumo: "Campanha mira público jovem com postos volantes.", categoria: "saúde", urgente: false, numero_fontes: 3, timestamp: new Date().toISOString() },
];

const EDITORIAS = ["política", "economia", "tecnologia", "esportes", "cultura", "saúde", "mundo", "cidades"];

async function getData() {
  try {
    const [feed, urg] = await Promise.all([obterFeed({}), obterUrgentes(4).catch(() => [] as FeedEntrada[])]);
    return { feed: feed.results?.length ? feed.results : MOCK, urg: urg.length ? urg : MOCK.filter((x) => x.urgente) };
  } catch {
    return { feed: MOCK, urg: MOCK.filter((x) => x.urgente) };
  }
}

function timeAgo(iso: string) {
  const d = Math.max(0, Date.now() - new Date(iso).getTime());
  const h = Math.floor(d / 3600000);
  if (h < 1) return "agora";
  if (h < 24) return `${h}h`;
  return `${Math.floor(h / 24)}d`;
}

export default async function Page() {
  const { feed, urg } = await getData();
  const hero = feed[0];
  const grid = feed.slice(1, 5);
  const resto = feed.slice(5);

  return (
    <div className="space-y-6">
      <section className="relative overflow-hidden rounded-[var(--raio-lg)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
        <div className="hud-grid absolute inset-0" aria-hidden />
        <div className="absolute inset-0 opacity-[0.08]" style={{ background: "var(--gradiente-marca)" }} aria-hidden />
        <div className="relative grid gap-6 p-5 md:grid-cols-[1.4fr_0.9fr] md:p-8">
          <div className="space-y-4">
            <div className="flex flex-wrap items-center gap-2">
              <Badge className="bg-[var(--cor-sinal)] text-[var(--cor-texto-invertido)] hover:bg-[var(--cor-sinal)]"><Radio className="mr-1 h-3 w-3" /> AO VIVO</Badge>
              <span className="text-xs tracking-widest text-[var(--cor-texto-suave)]">HUD • {new Date().toLocaleDateString("pt-BR")} • {urg.length} urgentes</span>
              <span className="hidden h-3 w-px bg-[var(--cor-borda)] md:block" aria-hidden />
              <span className="text-xs text-[var(--cor-texto-suave)]">paper <span className="text-[var(--cor-primaria)]">#FDFBF7</span> / ink <span className="text-[var(--cor-texto)]">#0B0B1A</span> / signal <span className="text-[var(--cor-sinal)]">#FF2E2E</span></span>
            </div>
            <div className="aspect-[16/9] overflow-hidden rounded-[var(--raio-lg)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)]">
              <img src={imagemNoticia(hero)} alt={hero.titulo} loading="lazy" className="h-full w-full object-cover" />
            </div>
            <p className="text-xs text-[var(--cor-texto-suave)]">Imagem ilustrativa — picsum.photos/seed/{hero.categoria}-{hero.id}</p>
            <h1 className="text-balance text-3xl font-bold leading-[var(--linha-altura-compacta)] text-[var(--cor-texto)] md:text-4xl">
              <span className="rounded-md px-1" style={{ background: "var(--cor-primaria-suave)" }}>{hero.titulo}</span>
            </h1>
            <p className="max-w-[60ch] text-pretty text-sm leading-relaxed text-[var(--cor-texto-suave)] md:text-base">{hero.resumo}</p>
            <div className="flex flex-wrap gap-2">
              <Button asChild className="bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)] hover:bg-[var(--cor-primaria-hover)]"><Link href={`/noticia/${hero.id}`}>Ler agora <ArrowRight className="ml-1 h-4 w-4" /></Link></Button>
              <Button asChild variant="outline" className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]"><Link href="/ao-vivo"><Flame className="mr-1 h-4 w-4 text-[var(--cor-sinal)]" /> Ao vivo</Link></Button>
            </div>
            <div className="flex items-center gap-2 text-xs text-[var(--cor-texto-suave)]"><Sparkles className="h-3 w-3 text-[var(--cor-neon-ciano)]" /> Bento HUD • vidro • neon contido — 1 elemento ousado</div>
          </div>
          <Card className="bento overflow-hidden border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] backdrop-blur">
            <CardContent className="p-4">
              <p className="mb-3 text-xs font-semibold tracking-widest text-[var(--cor-texto-suave)]">URGENTES — STRIP</p>
              <div className="space-y-2">
                {urg.length ? urg.map((u) => (
                  <Link key={`${u.tipo}-${u.id}`} href={`/noticia/${u.id}`} className="flex items-start gap-2 rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] p-2 hover:bg-[var(--cor-primaria-suave)]">
                    <span className="mt-1 h-2 w-2 shrink-0 rounded-full bg-[var(--cor-sinal)] shadow-[0_0_8px_var(--cor-sinal)]" aria-hidden />
                    <span className="text-sm font-medium leading-tight text-[var(--cor-texto)]">{u.titulo}</span>
                  </Link>
                )) : <Skeleton className="h-20 w-full bg-[var(--cor-skeleton-base)]" />}
              </div>
              <Link href="/ao-vivo" className="mt-3 inline-flex text-xs font-medium text-[var(--cor-primaria)] hover:underline">Ver cobertura ao vivo →</Link>
            </CardContent>
          </Card>
        </div>
        <div className="hud-line" aria-hidden />
      </section>
      <AdsSlot id="home-topo" formato="horizontal" />

      <section className="grid gap-4 md:grid-cols-12">
        <div className="md:col-span-8 space-y-4">
          <div className="flex items-center justify-between"><h2 className="text-lg font-bold text-[var(--cor-texto)]">Manchetes</h2><Link href="/arquivo" className="text-sm text-[var(--cor-primaria)] hover:underline">Arquivo →</Link></div>
          <div className="grid gap-4 md:grid-cols-2">
            {grid.map((n) => (
              <Card key={`${n.tipo}-${n.id}`} className="bento bento-hover overflow-hidden border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
                <div className="aspect-[16/9] overflow-hidden bg-[var(--cor-fundo-elevado)]">
                  <img src={imagemNoticia(n)} alt={n.titulo} loading="lazy" className="h-full w-full object-cover" />
                </div>
                <CardContent className="p-4">
                  <div className="mb-2 flex items-center gap-2">
                    <Badge variant="outline" className="border-[var(--cor-borda)] text-[var(--cor-texto-suave)]">{n.categoria}</Badge>
                    {n.urgente && <Badge className="bg-[var(--cor-sinal)] text-[var(--cor-texto-invertido)]">urgente</Badge>}
                    <span className="ml-auto text-xs text-[var(--cor-texto-suave)]">{timeAgo(n.timestamp)} • {n.numero_fontes} fontes</span>
                  </div>
                  <Link href={`/noticia/${n.id}`} className="line-clamp-2 text-balance text-base font-bold leading-tight text-[var(--cor-texto)] hover:text-[var(--cor-primaria)]">{n.titulo}</Link>
                  <p className="mt-1 line-clamp-2 text-sm text-[var(--cor-texto-suave)]">{n.resumo}</p>
                </CardContent>
              </Card>
            ))}
          </div>
          <AdsSlot id="home-infeed" formato="in-feed" />
           {resto.length > 0 && (
            <div className="grid gap-3">
              {resto.map((n) => (
                <Link key={`${n.tipo}-${n.id}`} href={`/noticia/${n.id}`} className="flex gap-3 rounded-[var(--raio-lg)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] p-3 hover:bg-[var(--cor-primaria-suave)]">
                  <span className="hidden aspect-[16/9] h-16 w-24 shrink-0 overflow-hidden rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] md:block" aria-hidden>
                    <img src={imagemNoticia(n)} alt="" loading="lazy" className="h-full w-full object-cover" />
                  </span>
                  <div className="min-w-0"><p className="text-xs text-[var(--cor-texto-suave)]">{n.categoria} • {timeAgo(n.timestamp)}</p><p className="line-clamp-2 text-sm font-semibold text-[var(--cor-texto)]">{n.titulo}</p></div>
                </Link>
              ))}
            </div>
          )}
        </div>
        <aside className="md:col-span-4 space-y-4">
          <Card className="bento border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]"><CardContent className="p-4"><h3 className="mb-3 text-sm font-bold tracking-widest text-[var(--cor-texto-suave)]">EDITORIAS</h3><div className="grid grid-cols-2 gap-2">{EDITORIAS.map((c) => (<Link key={c} href={`/categoria/${encodeURIComponent(c)}`} className="rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] px-3 py-2 text-sm font-medium capitalize text-[var(--cor-texto)] hover:bg-[var(--cor-primaria-suave)] hover:text-[var(--cor-primaria)]">{c}</Link>))}</div><Link href="/editorias" className="mt-3 inline-flex text-xs font-medium text-[var(--cor-primaria)] hover:underline">Ver todas →</Link></CardContent></Card>
          <Card className="bento border-[var(--cor-neon-ciano)] bg-[var(--cor-fundo-elevado)]"><CardContent className="p-4"><h3 className="flex items-center gap-2 text-sm font-bold text-[var(--cor-texto)]"><Mail className="h-4 w-4 text-[var(--cor-neon-ciano)]" /> Newsletter</h3><p className="mt-1 text-sm text-[var(--cor-texto-suave)]">Resumo diário sem ruído — escolha editorias e período.</p><form action="/newsletter" className="mt-3 flex gap-2"><Input placeholder="seu@email.com" type="email" required aria-label="Email para newsletter" className="h-9 bg-[var(--cor-fundo-card)]" /><Button type="submit" className="h-9 shrink-0 bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)] hover:bg-[var(--cor-primaria-hover)]">Assinar</Button></form><p className="mt-2 text-xs text-[var(--cor-texto-suave)]">Ao assinar você concorda com <Link href="/privacidade" className="underline">privacidade</Link>.</p></CardContent></Card>
          <AdsSlot id="home-sidebar" formato="retangulo" />
          <Card className="bento border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]"><CardContent className="p-4"><p className="text-xs tracking-widest text-[var(--cor-texto-suave)]">HUD METRICS</p><div className="mt-2 grid grid-cols-3 gap-2 text-center"><div className="rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-2"><p className="text-lg font-bold text-[var(--cor-texto)]">{feed.length}</p><p className="text-xs text-[var(--cor-texto-suave)]">manchetes</p></div><div className="rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-2"><p className="text-lg font-bold text-[var(--cor-sinal)]">{urg.length}</p><p className="text-xs text-[var(--cor-texto-suave)]">urgentes</p></div><div className="rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-2"><p className="text-lg font-bold text-[var(--cor-neon-violeta)]">{EDITORIAS.length}</p><p className="text-xs text-[var(--cor-texto-suave)]">editorias</p></div></div></CardContent></Card>
        </aside>
      </section>
    </div>
  );
}
