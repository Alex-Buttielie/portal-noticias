"use client";
import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { AdsSlot } from "@/components/AdsSlot";
import { ImagemNoticia } from "@/components/ImagemNoticia";
import type { FeedEntrada } from "@/lib/api";
import { carregarRegiao, salvarRegiao, limparRegiao, formatarRegiao, cidadesVizinhasMock, type Regiao } from "@/lib/regiao";
import { CompartilharLocalizacao } from "@/components/CompartilharLocalizacao";
import { trackLocationPermission, trackLocationSelected } from "@/lib/analytics";
import { ConsentimentoLocal, lerRecusaLocal, limparRecusaLocal } from "@/components/ConsentimentoLocal";
import { MapPin, Navigation, Clock3, Filter, ArrowUpDown, Search, X } from "lucide-react";
import { cn } from "@/lib/utils";

type Orden = "recente" | "relevancia" | "urgente";

function timeAgo(iso: string) {
  const d = Math.max(0, Date.now() - new Date(iso).getTime());
  const h = Math.floor(d / 3600000);
  if (h < 1) return "agora";
  if (h < 24) return `${h}h`;
  return `${Math.floor(h / 24)}d`;
}

function matchRegiao(noticia: FeedEntrada, regiao: Regiao, escopo: "tudo" | "cidade" | "estado" | "vizinhas", vizinhas: string[]): boolean {
  const hay = `${noticia.titulo} ${noticia.resumo} ${noticia.categoria}`.toLowerCase();
  const cidade = (regiao.cidade || "").toLowerCase();
  const estado = (regiao.estado || "").toLowerCase();
  const bairro = (regiao.bairro || "").toLowerCase();
  const matchCidade = cidade && hay.includes(cidade);
  const matchBairro = bairro && hay.includes(bairro);
  const matchEstado = estado && (hay.includes(estado) || hay.includes(` ${estado} `) || hay.endsWith(` ${estado}`));
  const matchVizinha = vizinhas.some((v) => hay.includes(v.toLowerCase()));
  if (escopo === "cidade") return !!(matchCidade || matchBairro);
  if (escopo === "estado") return !!matchEstado;
  if (escopo === "vizinhas") return !!matchVizinha;
  return !!(matchCidade || matchBairro || matchEstado || matchVizinha);
}

export function SecaoRegiao({ feed }: { feed: FeedEntrada[] }) {
  const [regiao, setRegiao] = useState<Regiao | null>(null);
  const [open, setOpen] = useState(false);
  const [recusado, setRecusado] = useState(false);
  const [escopo, setEscopo] = useState<"tudo" | "cidade" | "estado" | "vizinhas">("tudo");
  const [orden, setOrden] = useState<Orden>("recente");
  const [buscaLocal, setBuscaLocal] = useState("");
  const [categoriaFiltro, setCategoriaFiltro] = useState<string>("todas");

  useEffect(() => {
    setRegiao(carregarRegiao());
    setRecusado(lerRecusaLocal());
  }, []);

  const vizinhas = useMemo(() => (regiao ? cidadesVizinhasMock(regiao.cidade, regiao.estado) : []), [regiao]);

  const aoAlterarRegiao = useCallback((r: Regiao) => {
    salvarRegiao(r);
    setRegiao(r);
    setOpen(false);
    trackLocationPermission(true);
    trackLocationSelected({ pais: r.pais, estado: r.estado, cidade: r.cidade });
  }, []);

  const categorias = useMemo(() => Array.from(new Set(feed.map((f) => f.categoria).filter(Boolean))).sort(), [feed]);

  const itensRegiao = useMemo(() => {
    if (!regiao) return [];
    let base = feed.filter((n) => matchRegiao(n, regiao, escopo, vizinhas));
    if (categoriaFiltro !== "todas") base = base.filter((n) => (n.categoria || "").toLowerCase() === categoriaFiltro);
    if (buscaLocal.trim()) {
      const q = buscaLocal.toLowerCase();
      base = base.filter((n) => `${n.titulo} ${n.resumo}`.toLowerCase().includes(q));
    }
    if (orden === "recente") base = [...base].sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());
    if (orden === "relevancia") base = [...base].sort((a, b) => b.numero_fontes - a.numero_fontes);
    if (orden === "urgente") base = [...base].sort((a, b) => Number(b.urgente) - Number(a.urgente) || new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());
    return base;
  }, [feed, regiao, escopo, vizinhas, categoriaFiltro, buscaLocal, orden]);

  const heroLocal = itensRegiao[0];
  const resto = itensRegiao.slice(1, 7);

  if (!regiao) {
    if (recusado) {
      return (
        <section className="flex flex-wrap items-center gap-2 rounded-[var(--raio-lg)] border border-dashed border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] px-4 py-3">
          <span className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[var(--cor-fundo-elevado)] text-[var(--cor-texto-suave)]"><MapPin className="h-4 w-4" aria-hidden /></span>
          <p className="min-w-0 flex-1 text-sm text-[var(--cor-texto-suave)]"><span className="font-semibold text-[var(--cor-texto)]">Perto de você</span> — ative para ver notícias da sua cidade.</p>
          <Button size="sm" variant="outline" onClick={() => { limparRecusaLocal(); setRecusado(false); }} className="min-h-[40px] border-[var(--cor-borda)]">Ativar</Button>
        </section>
      );
    }
    return (
      <section aria-label="Perto de você" className="rounded-[var(--raio-lg)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] p-4 shadow-[var(--sombra-1)] md:p-6">
        <ConsentimentoLocal
          beneficio="notícias da sua cidade e vizinhança"
          onRegiao={(r) => { setRegiao(r); setRecusado(false); }}
          onRecusar={() => setRecusado(true)}
        />
      </section>
    );
  }
  return (
    <section className="space-y-4 rounded-[var(--raio-lg)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] p-4 md:p-5 shadow-[var(--sombra-1)]">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="flex flex-wrap items-center gap-2 text-base font-bold text-[var(--cor-texto)]"><MapPin className="h-4 w-4 text-[var(--cor-primaria)]" /> Perto de você — {formatarRegiao(regiao)} {regiao.bairro && <Badge variant="outline" className="border-[var(--cor-borda)] capitalize">{regiao.bairro}</Badge>}</h2>
          <p className="mt-1 text-sm text-[var(--cor-texto-suave)]">{vizinhas.length ? <>Inclui <span className="font-medium text-[var(--cor-texto)]">{vizinhas.slice(0, 3).join(", ")}</span> e arredores</> : "Região detectada — filtre por cidade, estado ou vizinhas."} • {itensRegiao.length} {itensRegiao.length === 1 ? "notícia" : "notícias"} próximas</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={() => setOpen(true)} className="min-h-[36px] gap-1.5 border-[var(--cor-borda)]"><MapPin className="h-4 w-4" /> Alterar região</Button>
          <Button variant="ghost" onClick={() => { limparRegiao(); setRegiao(null); }} className="min-h-[36px] gap-1.5"><X className="h-4 w-4" /> Limpar</Button>
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        {(["tudo", "cidade", "estado", "vizinhas"] as const).map((v) => (
          <button key={v} onClick={() => setEscopo(v)} className={cn("rounded-full border px-3 py-1.5 text-sm font-medium capitalize transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]", escopo === v ? "border-[var(--cor-primaria)] bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]" : "border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] text-[var(--cor-texto)] hover:bg-[var(--cor-primaria-suave)]")}>{v === "tudo" ? "Tudo próximo" : v}</button>
        ))}
        <span className="ml-auto hidden items-center gap-1 text-xs text-[var(--cor-texto-suave)] md:inline-flex"><Navigation className="h-3 w-3" /> {regiao.cidade} • {regiao.estado} {regiao.cep && `• ${regiao.cep}`}</span>
      </div>

      <div className="grid gap-3 md:grid-cols-[1fr_180px_180px]">
        <div className="relative">
          <Search className="pointer-events-none absolute left-2.5 top-2.5 h-4 w-4 text-[var(--cor-texto-suave)]" />
          <Input value={buscaLocal} onChange={(e) => setBuscaLocal(e.target.value)} placeholder="Filtrar por título ou resumo…" className="h-9 bg-[var(--cor-fundo-card)] pl-8" aria-label="Filtrar notícias da região" />
        </div>
        <div className="flex items-center gap-2">
          <Filter className="h-4 w-4 text-[var(--cor-texto-suave)]" />
          <Select value={categoriaFiltro} onValueChange={setCategoriaFiltro}>
            <SelectTrigger className="h-9 bg-[var(--cor-fundo-card)]"><SelectValue placeholder="Categoria" /></SelectTrigger>
            <SelectContent><SelectItem value="todas">Todas categorias</SelectItem>{Array.from(new Set(feed.map((f) => f.categoria).filter(Boolean))).map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}</SelectContent>
          </Select>
        </div>
        <div className="flex items-center gap-2">
          <ArrowUpDown className="h-4 w-4 text-[var(--cor-texto-suave)]" />
          <Select value={orden} onValueChange={(v) => setOrden(v as Orden)}>
            <SelectTrigger className="h-9 bg-[var(--cor-fundo-card)]"><SelectValue /></SelectTrigger>
            <SelectContent><SelectItem value="recente">Mais recentes</SelectItem><SelectItem value="relevancia">Mais fontes</SelectItem><SelectItem value="urgente">Urgentes primeiro</SelectItem></SelectContent>
          </Select>
        </div>
      </div>

      {!itensRegiao.length ? (
        <Card className="border-dashed border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)]"><CardContent className="p-6 text-center"><p className="text-sm font-medium text-[var(--cor-texto)]">Nenhuma notícia próxima com estes filtros</p><p className="mt-1 text-sm text-[var(--cor-texto-suave)]">Tente “Tudo próximo”, outra categoria ou limpe a busca.</p><div className="mt-3 flex flex-wrap justify-center gap-2"><Button variant="outline" size="sm" onClick={() => { setEscopo("tudo"); setCategoriaFiltro("todas"); setBuscaLocal(""); }}>Limpar filtros</Button><Button asChild size="sm" className="bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]"><Link href="/radar">Ver Radar regional</Link></Button></div></CardContent></Card>
      ) : (
        <>
          {heroLocal && (
            <Card className="group overflow-hidden border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] transition hover:shadow-[var(--sombra-2)]">
              <div className="grid md:grid-cols-[1.4fr_0.9fr]">
                <Link href={`/noticia/${heroLocal.id}`} className="block aspect-[16/9] overflow-hidden focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]">
                  <ImagemNoticia src={heroLocal.imagem_url} seed={`${heroLocal.categoria || "geral"}-${heroLocal.id}`} alt={heroLocal.titulo} className="h-full w-full object-cover transition duration-300 group-hover:scale-[1.02]" />
                </Link>
                <CardContent className="flex flex-col justify-center p-4">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge className="bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)] gap-1"><MapPin className="h-3 w-3" /> {regiao.cidade}</Badge>
                    <span className="text-xs capitalize text-[var(--cor-texto-suave)]">{heroLocal.categoria} • {timeAgo(heroLocal.timestamp)} • {heroLocal.numero_fontes} fontes</span>
                  </div>
                  <Link href={`/noticia/${heroLocal.id}`} className="mt-2 line-clamp-2 text-balance text-lg font-bold leading-tight text-[var(--cor-texto)] hover:text-[var(--cor-primaria)]">{heroLocal.titulo}</Link>
                  <Link href={`/noticia/${heroLocal.id}`} className="mt-1 line-clamp-2 text-sm text-[var(--cor-texto-suave)] hover:text-[var(--cor-texto)]">{heroLocal.resumo}</Link>
                  <div className="mt-3 flex gap-2">
                    <Button asChild size="sm" className="h-8 bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]"><Link href={`/noticia/${heroLocal.id}`}>Ler agora</Link></Button>
                    <Button asChild size="sm" variant="outline" className="h-8 border-[var(--cor-borda)]"><Link href={`/categoria/${encodeURIComponent(heroLocal.categoria)}`} className="capitalize">{heroLocal.categoria}</Link></Button>
                  </div>
                </CardContent>
              </div>
            </Card>
          )}
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {resto.map((n) => (
              <Card key={`reg-${n.tipo}-${n.id}`} className="group overflow-hidden border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] hover:shadow-[var(--sombra-2)] hover:-translate-y-0.5 transition-all">
                <Link href={`/noticia/${n.id}`} className="block aspect-[16/9] overflow-hidden bg-[var(--cor-fundo-elevado)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]">
                  <ImagemNoticia src={n.imagem_url} seed={`${n.categoria || "geral"}-${n.id}`} alt={n.titulo} className="h-full w-full object-cover transition duration-300 group-hover:scale-[1.02]" />
                </Link>
                <CardContent className="p-3">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-medium capitalize text-[var(--cor-primaria)]">{n.categoria}</span>
                    <span className="text-xs text-[var(--cor-texto-suave)]">• {timeAgo(n.timestamp)}</span>
                    {n.urgente && <span className="ml-auto h-1.5 w-1.5 rounded-full bg-[var(--cor-sinal)]" aria-hidden />}
                  </div>
                  <Link href={`/noticia/${n.id}`} className="mt-1 line-clamp-2 block text-sm font-bold leading-tight text-[var(--cor-texto)] hover:text-[var(--cor-primaria)]">{n.titulo}</Link>
                  <p className="mt-1 line-clamp-2 text-xs text-[var(--cor-texto-suave)]">{n.resumo}</p>
                  <div className="mt-2 flex items-center justify-between text-xs text-[var(--cor-texto-suave)]"><span className="inline-flex items-center gap-1"><Clock3 className="h-3 w-3" />{n.numero_fontes} fontes</span><Link href={`/noticia/${n.id}`} className="font-medium text-[var(--cor-primaria)] hover:underline">Ler →</Link></div>
                </CardContent>
              </Card>
            ))}
          </div>
          <div className="flex flex-wrap gap-2">
            {vizinhas.slice(0, 6).map((v) => (
              <Link key={v} href={`/buscar?busca=${encodeURIComponent(v)}`} className="rounded-full border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] px-3 py-1.5 text-xs font-medium text-[var(--cor-texto)] hover:bg-[var(--cor-primaria-suave)] hover:text-[var(--cor-primaria)]">{v}</Link>
            ))}
            <Link href="/radar" className="rounded-full border border-[var(--cor-primaria)] bg-[var(--cor-primaria-suave)] px-3 py-1.5 text-xs font-medium text-[var(--cor-primaria)]">Ver Radar completo →</Link>
          </div>
        </>
      )}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] max-w-lg">
          <DialogHeader><DialogTitle className="flex items-center gap-2"><MapPin className="h-5 w-5 text-[var(--cor-primaria)]" /> Alterar região</DialogTitle><DialogDescription>Use sua localização ou busque por CEP/endereço.</DialogDescription></DialogHeader>
          <CompartilharLocalizacao
            onRegiao={(r) => {
              salvarRegiao(r);
              setRegiao(r);
              setOpen(false);
              trackLocationPermission(true);
              trackLocationSelected({ pais: r.pais, estado: r.estado, cidade: r.cidade });
            }}
          />
          <DialogFooter><Button variant="outline" onClick={() => setOpen(false)}>Fechar</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </section>
  );
}
