"use client";
import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { AdsSlot } from "@/components/AdsSlot";
import { SeloFormato, barraPorFormato, formatoDaPublicacao } from "@/components/comunidade/TipoSelo";
import { useAuth } from "@/lib/auth-context";
import { useQueryPublicacoesComunidade, invalidarQueriesComunidade } from "@/lib/queries";
import type { FiltrosPublicacoesComunidade } from "@/lib/query-keys";
import { useQueryClient } from "@tanstack/react-query";
import * as api from "@/lib/api";
import { registrarEventoComunidade } from "@/lib/interacoes-comunidade";
import { formatarDataCurta } from "@/lib/datas";
import { cn } from "@/lib/utils";
import {
  Users, MessageSquare, Shield, Newspaper, Star, Search, LogIn, Plus, Eye,
  UserPlus, UserMinus, Send, Flag, Flame, Clock, TrendingUp, Link2, RotateCcw, MessagesSquare,
} from "lucide-react";

type Grupo = { slug: string; nome: string; desc: string };
const GRUPOS: Grupo[] = [
  { slug: "politica", nome: "Política", desc: "Análises e opiniões sobre poder e decisões." },
  { slug: "economia", nome: "Economia", desc: "Mercado, inflação e bolso no dia a dia." },
  { slug: "tecnologia", nome: "Tecnologia", desc: "IA, plataformas e impacto digital." },
  { slug: "esportes", nome: "Esportes", desc: "Bastidores, opinião e análise tática." },
  { slug: "cultura", nome: "Cultura", desc: "Livros, cinema, música e cena local." },
  { slug: "saude", nome: "Saúde", desc: "Ciência, bem-estar e serviço." },
  { slug: "mundo", nome: "Mundo", desc: "Geopolítica e correspondência." },
  { slug: "cidades", nome: "Cidades", desc: "Mobilidade, bairros e vida urbana." },
  { slug: "geral", nome: "Geral", desc: "Pautas transversais e comunidade aberta." },
];
const LS_GRUPOS = "brd_comunidades_membros";
const LS_SEGUINDO = "brd_autores_seguindo";

function readLS(key: string): string[] { try { const v = localStorage.getItem(key); return v ? JSON.parse(v) as string[] : []; } catch { return []; } }
function writeLS(key: string, v: string[]) { try { localStorage.setItem(key, JSON.stringify(v)); } catch { } }

const MOCK_PUBS: api.Publicacao[] = [
  { id: 901, autor: 1, autor_nome: "Ana Política", titulo: "Opinião: reforma e cidades", conteudo: "Análise curta sobre impacto urbano.", tipo: "opiniao", status: "publicado", categoria: "politica", tags: ["exemplo", "cidades"], news_cluster: 1, news_item: null, destaque: true, numero_comentarios: 12, criado_em: new Date().toISOString(), publicado_em: new Date().toISOString() },
  { id: 902, autor: 2, autor_nome: "Bruno Tech", titulo: "Análise: IA no jornalismo", conteudo: "Como IA reorganiza redação e checagem.", tipo: "analise", status: "publicado", categoria: "tecnologia", tags: ["ia", "exemplo"], news_cluster: null, news_item: null, destaque: false, numero_comentarios: 4, criado_em: new Date().toISOString(), publicado_em: new Date().toISOString() },
];

/** Link de notícia relacionada (ecossistema): cluster > item > editoria. */
function linkNoticiaRelacionada(p: api.Publicacao): { href: string; rotulo: string } | null {
  if (p.news_cluster) return { href: `/noticia/cluster/${p.news_cluster}`, rotulo: "Ver notícia relacionada" };
  if (p.news_item) return { href: `/noticia/item/${p.news_item}`, rotulo: "Ver notícia relacionada" };
  if (p.categoria) return { href: `/categoria/${p.categoria}`, rotulo: "Ver editoria" };
  return null;
}

function EsqueletoFeed() {
  return (
    <div className="grid gap-3" aria-hidden>
      {[0, 1, 2].map((i) => (
        <div key={i} className="animate-pulse rounded-[var(--raio-lg)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] p-3">
          <div className="h-4 w-2/3 rounded bg-[var(--cor-fundo-elevado)]" />
          <div className="mt-2 h-3 w-full rounded bg-[var(--cor-fundo-elevado)]" />
          <div className="mt-1 h-3 w-5/6 rounded bg-[var(--cor-fundo-elevado)]" />
        </div>
      ))}
    </div>
  );
}

export default function Page() {
  const { token } = useAuth();
  const queryClient = useQueryClient();
  const [tab, setTab] = useState("feed");
  const [tipoFiltro, setTipoFiltro] = useState<string>("todos");
  const [catFiltro, setCatFiltro] = useState<string>("todas");
  const [busca, setBusca] = useState("");
  const [buscaDeb, setBuscaDeb] = useState("");
  const [grupoFiltro, setGrupoFiltro] = useState<string | null>(null);
  const [membros, setMembros] = useState<string[]>([]);
  const [seguindo, setSeguindo] = useState<string[]>([]);
  const [assuntos, setAssuntos] = useState<api.AssuntoEmAlta[]>([]);
  const [openCriar, setOpenCriar] = useState(false);
  const [openDenuncia, setOpenDenuncia] = useState<{ open: boolean; pubId?: number; comentarioId?: number }>({ open: false });
  const [openComentar, setOpenComentar] = useState<{ open: boolean; pubId?: number }>({ open: false });
  const [motivo, setMotivo] = useState("");
  const [comentarioTxt, setComentarioTxt] = useState("");
  const [criar, setCriar] = useState({ titulo: "", conteudo: "", tipo: "opiniao" as api.TipoPublicacao, categoria: "geral", tags: "" });
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => { setMembros(readLS(LS_GRUPOS)); setSeguindo(readLS(LS_SEGUINDO)); }, []);

  // Debounce da busca → evita enxurrada de requisições.
  useEffect(() => {
    const t = setTimeout(() => setBuscaDeb(busca.trim()), 350);
    return () => clearTimeout(t);
  }, [busca]);

  const ordenar: "recentes" | "discutidos" | "destaques" =
    tab === "discutidos" ? "discutidos" : tab === "destaques" ? "destaques" : "recentes";

  // --- Migração TanStack Query: filtros dinâmicos na query key.
  // Quando tab/categoria/tipo/busca mudam, a chave muda e a query refetch sozinha.
  const filtros: FiltrosPublicacoesComunidade = {
    ordenar,
    categoria: grupoFiltro || (catFiltro !== "todas" ? catFiltro : undefined),
    tipo: tipoFiltro !== "todos" ? tipoFiltro : undefined,
    busca: buscaDeb || undefined,
    destaque: tab === "destaques" ? true : undefined,
  };
  const { data: pubsData, isLoading, isError, error, refetch } = useQueryPublicacoesComunidade(filtros);

  // Fallback local (modo offline): filtro client-side sobre o mock quando a API falha.
  const pubs = useMemo(() => {
    if (isError) {
      return MOCK_PUBS.filter((p) => {
        if (tipoFiltro !== "todos" && p.tipo !== tipoFiltro) return false;
        const cat = grupoFiltro || (catFiltro !== "todas" ? catFiltro : null);
        if (cat && p.categoria !== cat) return false;
        if (tab === "destaques" && !p.destaque) return false;
        if (buscaDeb && !`${p.titulo} ${p.autor_nome}`.toLowerCase().includes(buscaDeb.toLowerCase())) return false;
        return true;
      });
    }
    return pubsData ?? [];
  }, [isError, pubsData, tipoFiltro, grupoFiltro, catFiltro, tab, buscaDeb]);

  const carregar = useCallback(async () => {
    const cat = grupoFiltro || (catFiltro !== "todas" ? catFiltro : undefined);
    await refetch();
    registrarEventoComunidade("ver_feed", { categoria: cat });
  }, [refetch, grupoFiltro, catFiltro]);

  // Assuntos em alta (radar) — ecossistema; fallback silencioso p/ tags locais.
  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const t = await api.obterTendenciasRadar({});
        if (alive && t?.assuntos_em_alta?.length) setAssuntos(t.assuntos_em_alta.slice(0, 6));
      } catch { /* fallback local abaixo */ }
    })();
    return () => { alive = false; };
  }, []);

  const assuntosFallback = useMemo(() => {
    const cont: Record<string, number> = {};
    for (const p of pubs) for (const t of p.tags || []) cont[t] = (cont[t] || 0) + 1;
    return Object.entries(cont).sort((a, b) => b[1] - a[1]).slice(0, 6);
  }, [pubs]);

  const destaques = useMemo(() => pubs.filter((p) => p.destaque).slice(0, 3), [pubs]);
  const maisDiscutidos = useMemo(
    () => [...pubs].sort((a, b) => (b.numero_comentarios ?? 0) - (a.numero_comentarios ?? 0)).slice(0, 5),
    [pubs]
  );
  const totalComentarios = useMemo(() => pubs.reduce((s, p) => s + (p.numero_comentarios ?? 0), 0), [pubs]);

  const toggleGrupo = (slug: string) => {
    const next = membros.includes(slug) ? membros.filter((s) => s !== slug) : [...membros, slug];
    setMembros(next); writeLS(LS_GRUPOS, next);
    setMsg(membros.includes(slug) ? `Saiu de ${slug}` : `Entrou em ${slug} — feed filtrado`);
    if (!membros.includes(slug)) { setGrupoFiltro(slug); setTab("feed"); setCatFiltro(slug); }
    registrarEventoComunidade("filtrar", { categoria: slug });
  };
  const verGrupo = (slug: string) => {
    setGrupoFiltro(slug); setCatFiltro(slug); setTab("feed");
    registrarEventoComunidade("filtrar", { categoria: slug });
  };

  const toggleSeguir = async (autorId: number, autorNome: string) => {
    const key = String(autorId);
    const isSeg = seguindo.includes(key);
    if (!token) { const n = isSeg ? seguindo.filter((k) => k !== key) : [...seguindo, key]; setSeguindo(n); writeLS(LS_SEGUINDO, n); setMsg(isSeg ? `Deixou de seguir ${autorNome}` : `Seguindo ${autorNome} (local)`); return; }
    try {
      if (isSeg) { await api.deixarDeSeguirAutor(token, autorId); registrarEventoComunidade("deixar_seguir", { publicacaoId: autorId }); }
      else { await api.seguirAutor(token, autorId); registrarEventoComunidade("seguir_autor", { publicacaoId: autorId }); }
      const n = isSeg ? seguindo.filter((k) => k !== key) : [...seguindo, key]; setSeguindo(n); writeLS(LS_SEGUINDO, n);
      setMsg(isSeg ? `Deixou de seguir ${autorNome}` : `Seguindo ${autorNome}`);
    } catch (e: unknown) { setErr(e instanceof Error ? e.message : "Falha ao seguir"); }
  };

  const handleCriar = async () => {
    setErr(null);
    if (!token) { setErr("Entre para publicar."); return; }
    if (criar.titulo.trim().length < 3 || criar.conteudo.trim().length < 10) { setErr("Título ≥3 e conteúdo ≥10 caracteres."); return; }
    try {
      const tags = criar.tags.split(",").map((t) => t.trim()).filter(Boolean);
      const rasc = await api.criarRascunhoPublicacao(token, { titulo: criar.titulo.trim(), conteudo: criar.conteudo.trim(), tipo: criar.tipo, categoria: criar.categoria || undefined, tags: tags.length ? tags : undefined });
      await api.enviarPublicacao(token, rasc.id);
      await invalidarQueriesComunidade(queryClient, { publicacaoId: rasc.id, usuarioId: null });
      setOpenCriar(false); setCriar({ titulo: "", conteudo: "", tipo: "opiniao", categoria: "geral", tags: "" }); setMsg("Publicação enviada!");
      registrarEventoComunidade("publicar", { categoria: criar.categoria });
    } catch (e: unknown) { setErr(e instanceof Error ? e.message : "Falha ao publicar"); }
  };
  const handleComentar = async () => {
    if (!token || !openComentar.pubId) { setErr("Entre para comentar."); return; }
    if (comentarioTxt.trim().length < 2) { setErr("Comentário muito curto."); return; }
    try {
      await api.comentar(token, { conteudo: comentarioTxt.trim(), publicacao: openComentar.pubId });
      await invalidarQueriesComunidade(queryClient, { publicacaoId: openComentar.pubId, usuarioId: null });
      setOpenComentar({ open: false }); setComentarioTxt(""); setMsg("Comentário enviado!");
      registrarEventoComunidade("comentar", { publicacaoId: openComentar.pubId });
    } catch (e: unknown) { setErr(e instanceof Error ? e.message : "Falha ao comentar"); }
  };
  const handleDenunciar = async () => {
    if (!token) { setErr("Entre para denunciar."); return; }
    if (motivo.trim().length < 5) { setErr("Informe o motivo (≥5)."); return; }
    try {
      await api.denunciar(token, { motivo: motivo.trim(), publicacao: openDenuncia.pubId, comentario: openDenuncia.comentarioId });
      setOpenDenuncia({ open: false }); setMotivo(""); setMsg("Denúncia enviada. Obrigado.");
      registrarEventoComunidade("denunciar", { publicacaoId: openDenuncia.pubId });
    } catch (e: unknown) { setErr(e instanceof Error ? e.message : "Falha ao denunciar"); }
  };

  const temFiltroAtivo = tipoFiltro !== "todos" || catFiltro !== "todas" || !!grupoFiltro || !!buscaDeb;
  const limparFiltros = () => { setTipoFiltro("todos"); setCatFiltro("todas"); setGrupoFiltro(null); setBusca(""); };

  const CartaoPub = ({ p, idx }: { p: api.Publicacao; idx: number }) => {
    const formato = formatoDaPublicacao(p.tipo, p.numero_comentarios ?? 0);
    const rel = linkNoticiaRelacionada(p);
    return (
      <div>
        <Link
          href={`/comunidade/${p.id}`}
          onClick={() => registrarEventoComunidade("ver_publicacao", { publicacaoId: p.id, categoria: p.categoria })}
          className={cn(
            "flex gap-3 rounded-[var(--raio-lg)] border border-[var(--cor-borda)] border-l-4 bg-[var(--cor-fundo-card)] p-3 transition-colors hover:bg-[var(--cor-primaria-suave)]",
            barraPorFormato(formato)
          )}
          aria-label={`${p.titulo} — ${formato}, por ${p.autor_nome}`}
        >
          <div className="hidden sm:flex h-[84px] w-[112px] shrink-0 flex-col items-center justify-center gap-1 rounded-[var(--raio-md)] bg-[var(--cor-fundo-elevado)] border border-[var(--cor-borda)]">
            <Newspaper className="h-6 w-6 text-[var(--cor-texto-suave)]" aria-hidden />
            <span className="text-[10px] uppercase tracking-wide text-[var(--cor-texto-suave)]">{p.categoria || "geral"}</span>
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-1.5">
              <SeloFormato formato={formato} />
              <Badge className="bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)] text-xs">{p.categoria || "geral"}</Badge>
              {p.destaque && <Badge variant="secondary" className="gap-1 text-xs"><Star className="h-3 w-3" aria-hidden />Destaque</Badge>}
              {(p.numero_comentarios ?? 0) > 0 && (
                <span className="inline-flex items-center gap-1 text-xs text-[var(--cor-texto-suave)]">
                  <MessagesSquare className="h-3.5 w-3.5" aria-hidden />{p.numero_comentarios} {p.numero_comentarios === 1 ? "comentário" : "comentários"}
                </span>
              )}
            </div>
            <p className="mt-1 line-clamp-2 text-[15px] font-semibold leading-tight text-[var(--cor-texto)]">{p.titulo}</p>
            <p className="line-clamp-2 text-sm text-[var(--cor-texto-suave)]">{p.conteudo.slice(0, 160)}</p>
            <p className="mt-1 text-xs text-[var(--cor-texto-suave)]">por {p.autor_nome} · {formatarDataCurta(p.criado_em)}</p>
            {!!p.tags.length && <div className="mt-1 flex flex-wrap gap-1">{p.tags.slice(0, 3).map((t) => <span key={t} className="rounded-full border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] px-2 py-0.5 text-[11px] text-[var(--cor-texto-suave)]">#{t}</span>)}</div>}
          </div>
        </Link>
        <div className="mt-1 flex flex-wrap items-center gap-1.5 px-1">
          <Button size="sm" variant="ghost" className="h-7 text-xs gap-1" onClick={() => toggleSeguir(p.autor, p.autor_nome)} aria-pressed={seguindo.includes(String(p.autor))}>
            {seguindo.includes(String(p.autor)) ? <><UserMinus className="h-3.5 w-3.5" aria-hidden />Seguindo</> : <><UserPlus className="h-3.5 w-3.5" aria-hidden />Seguir autor</>}
          </Button>
          <Button size="sm" variant="ghost" className="h-7 text-xs gap-1" onClick={() => setOpenComentar({ open: true, pubId: p.id })}>
            <MessageSquare className="h-3.5 w-3.5" aria-hidden />Comentar{p.numero_comentarios ? ` (${p.numero_comentarios})` : ""}
          </Button>
          {rel && (
            <Button size="sm" variant="ghost" className="h-7 text-xs gap-1" asChild>
              <Link href={rel.href} onClick={() => registrarEventoComunidade("clicar_noticia_relacionada", { publicacaoId: p.id, destino: rel.href })}>
                <Link2 className="h-3.5 w-3.5" aria-hidden />{rel.rotulo}
              </Link>
            </Button>
          )}
          <Button size="sm" variant="ghost" className="h-7 text-xs gap-1" onClick={() => setOpenDenuncia({ open: true, pubId: p.id })} aria-label={`Denunciar ${p.titulo}`}>
            <Flag className="h-3.5 w-3.5" aria-hidden />Denunciar
          </Button>
        </div>
        {(idx + 1) % 4 === 0 && <AdsSlot id={`comunidade-feed-${idx}`} formato="in-feed" className="my-3" />}
      </div>
    );
  };

  return (
    <div className="mx-auto max-w-6xl space-y-4 py-6 px-3 sm:px-0">
      <div className="hud-line" aria-hidden />
      {/* Cabeçalho jornalístico */}
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-widest text-[var(--cor-primaria)]">Participação · Opinião · Debate</p>
          <h1 className="text-2xl font-bold tracking-tight text-[var(--cor-texto)]">Comunidade viva</h1>
          <p className="text-sm text-[var(--cor-texto-suave)]">O debate da redação com a rua: opiniões, colunas e discussões ligadas às notícias do dia.</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" className="min-h-[44px] border-[var(--cor-borda)]" onClick={() => setOpenCriar(true)}><Plus className="mr-1.5 h-4 w-4" aria-hidden />Publicar</Button>
          <Button asChild className="min-h-[44px] bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]"><Link href="/comunidade/nova">Nova publicação</Link></Button>
        </div>
      </div>

      {/* Indicadores de interação */}
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4" role="status" aria-label="Indicadores da comunidade">
        {[
          { Icone: MessagesSquare, valor: pubs.length, rotulo: "em discussão" },
          { Icone: MessageSquare, valor: totalComentarios, rotulo: "comentários" },
          { Icone: Users, valor: membros.length, rotulo: "meus grupos" },
          { Icone: Star, valor: pubs.filter((p) => p.destaque).length, rotulo: "destaques" },
        ].map(({ Icone, valor, rotulo }) => (
          <div key={rotulo} className="flex items-center gap-2 rounded-[var(--raio-md)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] px-3 py-2">
            <Icone className="h-4 w-4 text-[var(--cor-primaria)]" aria-hidden />
            <p className="text-sm text-[var(--cor-texto)]"><strong>{valor}</strong> <span className="text-[var(--cor-texto-suave)]">{rotulo}</span></p>
          </div>
        ))}
      </div>

      {(msg || err) && (
        <div className={cn("rounded-md border px-3 py-2 text-sm", err ? "border-[var(--cor-erro)] bg-[var(--cor-erro-suave)] text-[var(--cor-erro)]" : "border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] text-[var(--cor-texto)]")} role="alert">
          {err || msg} <button onClick={() => { setMsg(null); setErr(null); }} className="ml-2 underline text-xs">fechar</button>
        </div>
      )}

      {grupoFiltro && (
        <div className="flex items-center gap-2 rounded-full border border-[var(--cor-borda)] bg-[var(--cor-primaria-suave)] px-3 py-1.5 text-sm text-[var(--cor-texto)] w-fit">
          Filtrando: <strong>{grupoFiltro}</strong>
          <button onClick={() => { setGrupoFiltro(null); setCatFiltro("todas"); }} className="ml-1 rounded-full bg-[var(--cor-fundo-card)] px-2 py-0.5 text-xs border border-[var(--cor-borda)]">Limpar</button>
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-[1fr_320px]">
        {/* Coluna principal */}
        <div className="min-w-0">
          <Tabs value={tab} onValueChange={setTab}>
            <TabsList className="w-full justify-start overflow-x-auto" aria-label="Seções da comunidade">
              <TabsTrigger value="feed" className="gap-1.5"><Newspaper className="h-4 w-4" aria-hidden />Feed</TabsTrigger>
              <TabsTrigger value="destaques" className="gap-1.5"><Star className="h-4 w-4" aria-hidden />Destaques</TabsTrigger>
              <TabsTrigger value="discutidos" className="gap-1.5"><Flame className="h-4 w-4" aria-hidden />Mais discutidos</TabsTrigger>
              <TabsTrigger value="grupos" className="gap-1.5"><Users className="h-4 w-4" aria-hidden />Grupos</TabsTrigger>
              <TabsTrigger value="minhas" className="gap-1.5"><Eye className="h-4 w-4" aria-hidden />Minhas</TabsTrigger>
            </TabsList>

            <TabsContent value="feed" className="space-y-3">
              <Card className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
                <CardContent className="flex flex-wrap gap-2 p-3">
                  <div className="flex items-center gap-1.5">
                    <Select value={tipoFiltro} onValueChange={setTipoFiltro}>
                      <SelectTrigger className="h-9 w-[150px] bg-[var(--cor-fundo-card)]" aria-label="Filtrar por formato"><SelectValue placeholder="Formato" /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="todos">Todos formatos</SelectItem>
                        <SelectItem value="opiniao">Opinião</SelectItem>
                        <SelectItem value="analise">Coluna / Análise</SelectItem>
                      </SelectContent>
                    </Select>
                    <Select value={catFiltro} onValueChange={(v) => { setCatFiltro(v); setGrupoFiltro(null); }}>
                      <SelectTrigger className="h-9 w-[150px] bg-[var(--cor-fundo-card)]" aria-label="Filtrar por editoria"><SelectValue placeholder="Editoria" /></SelectTrigger>
                      <SelectContent><SelectItem value="todas">Todas</SelectItem>{GRUPOS.map((g) => <SelectItem key={g.slug} value={g.slug}>{g.nome}</SelectItem>)}</SelectContent>
                    </Select>
                  </div>
                  <div className="relative flex-1 min-w-[180px]">
                    <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-[var(--cor-texto-suave)]" aria-hidden />
                    <Input placeholder="Buscar por autor, título ou tag" value={busca} onChange={(e) => setBusca(e.target.value)} className="pl-8 h-9 bg-[var(--cor-fundo-card)]" aria-label="Buscar na comunidade" />
                  </div>
                </CardContent>
              </Card>

              {isError && (
                <div className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900" role="alert">
                  <span>{error?.message || "Não foi possível carregar o feed ao vivo — mostrando conteúdo local."}</span>
                  <Button size="sm" variant="outline" className="gap-1" onClick={carregar}><RotateCcw className="h-3.5 w-3.5" aria-hidden />Tentar de novo</Button>
                </div>
              )}

              <div aria-live="polite" aria-busy={isLoading}>
                {isLoading ? <EsqueletoFeed />
                  : pubs.length === 0 ? (
                    <Card className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
                      <CardContent className="p-6 text-center">
                        <MessagesSquare className="mx-auto h-8 w-8 text-[var(--cor-texto-suave)]" aria-hidden />
                        <p className="mt-2 text-sm font-medium text-[var(--cor-texto)]">Nenhuma discussão por aqui — ainda.</p>
                        <p className="text-sm text-[var(--cor-texto-suave)]">Ajuste os filtros ou abra o primeiro debate da editoria.</p>
                        <div className="mt-3 flex justify-center gap-2">
                          {temFiltroAtivo && <Button variant="outline" size="sm" className="border-[var(--cor-borda)]" onClick={limparFiltros}>Limpar filtros</Button>}
                          <Button size="sm" className="bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]" onClick={() => setOpenCriar(true)}>Abrir discussão</Button>
                        </div>
                      </CardContent>
                    </Card>
                  ) : (
                    <div className="grid gap-3">
                      {pubs.map((p, idx) => <CartaoPub key={p.id} p={p} idx={idx} />)}
                    </div>
                  )}
              </div>
            </TabsContent>

            <TabsContent value="destaques" className="space-y-3">
              <div aria-live="polite" aria-busy={isLoading}>
                {isLoading ? <EsqueletoFeed /> : destaques.length === 0 ? (
                  <Card className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]"><CardContent className="p-6 text-center text-sm text-[var(--cor-texto-suave)]">Sem destaques da curadoria por enquanto — o Feed segue aberto.</CardContent></Card>
                ) : (
                  <div className="grid gap-3">
                    <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-widest text-[var(--cor-texto-suave)]"><Star className="h-3.5 w-3.5" aria-hidden />Escolhas da curadoria</p>
                    {destaques.map((p, idx) => <CartaoPub key={p.id} p={p} idx={idx} />)}
                  </div>
                )}
              </div>
            </TabsContent>

            <TabsContent value="discutidos" className="space-y-3">
              <div aria-live="polite" aria-busy={isLoading}>
                {isLoading ? <EsqueletoFeed /> : pubs.length === 0 ? (
                  <Card className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]"><CardContent className="p-6 text-center text-sm text-[var(--cor-texto-suave)]">Ainda sem termômetro — seja a primeira voz.</CardContent></Card>
                ) : (
                  <div className="grid gap-3">
                    <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-widest text-[var(--cor-texto-suave)]"><Flame className="h-3.5 w-3.5" aria-hidden />Ordenado por comentários</p>
                    {[...pubs].sort((a, b) => (b.numero_comentarios ?? 0) - (a.numero_comentarios ?? 0)).map((p, idx) => <CartaoPub key={p.id} p={p} idx={idx} />)}
                  </div>
                )}
              </div>
            </TabsContent>

            <TabsContent value="grupos">
              <div className="grid gap-3 sm:grid-cols-2">
                {GRUPOS.map((g) => {
                  const countPubs = pubs.filter((p) => p.categoria === g.slug).length;
                  const membrosMock = 80 + g.slug.length * 37 + countPubs * 7;
                  const isMembro = membros.includes(g.slug);
                  return (
                    <Card key={g.slug} className={cn("border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] flex flex-col", isMembro && "ring-1 ring-[var(--cor-primaria)]")}>
                      <CardHeader className="pb-2">
                        <div className="flex items-start justify-between gap-2">
                          <div className="flex h-9 w-9 items-center justify-center rounded-[var(--raio-md)] bg-[var(--cor-primaria-suave)] border border-[var(--cor-borda)]"><Users className="h-5 w-5 text-[var(--cor-primaria)]" aria-hidden /></div>
                          {isMembro && <Badge className="bg-[var(--cor-sucesso)] text-white text-[11px]">Membro</Badge>}
                        </div>
                        <CardTitle className="text-base text-[var(--cor-texto)]">{g.nome}</CardTitle>
                        <CardDescription className="text-xs text-[var(--cor-texto-suave)] line-clamp-2">{g.desc}</CardDescription>
                      </CardHeader>
                      <CardContent className="mt-auto space-y-3">
                        <div className="flex gap-3 text-xs text-[var(--cor-texto-suave)]">
                          <span className="flex items-center gap-1"><Users className="h-3.5 w-3.5" aria-hidden />{membrosMock} membros</span>
                          <span className="flex items-center gap-1"><Newspaper className="h-3.5 w-3.5" aria-hidden />{countPubs} pubs</span>
                        </div>
                        <div className="flex gap-2">
                          <Button size="sm" className={cn("flex-1 min-h-[36px] gap-1", isMembro ? "bg-[var(--cor-fundo-elevado)] text-[var(--cor-texto)] border border-[var(--cor-borda)] hover:bg-[var(--cor-borda)]" : "bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]")} onClick={() => toggleGrupo(g.slug)}>
                            {isMembro ? <><UserMinus className="h-4 w-4" aria-hidden />Sair</> : <><UserPlus className="h-4 w-4" aria-hidden />Entrar</>}
                          </Button>
                          <Button size="sm" variant="outline" className="min-h-[36px] border-[var(--cor-borda)] gap-1" onClick={() => verGrupo(g.slug)}><Eye className="h-4 w-4" aria-hidden />Ver</Button>
                        </div>
                      </CardContent>
                    </Card>
                  );
                })}
              </div>
            </TabsContent>

            <TabsContent value="minhas" className="space-y-3">
              {membros.length === 0 ? (
                <Card className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]"><CardContent className="p-6 text-center text-sm text-[var(--cor-texto-suave)]">Você ainda não entrou em nenhuma comunidade. Vá em <strong>Grupos</strong> e clique em Entrar.<Button variant="outline" className="mt-3 border-[var(--cor-borda)]" onClick={() => setTab("grupos")}><Users className="mr-1.5 h-4 w-4" aria-hidden />Explorar grupos</Button></CardContent></Card>
              ) : (
                <div className="grid gap-3 sm:grid-cols-2">
                  {GRUPOS.filter((g) => membros.includes(g.slug)).map((g) => {
                    const pubsGrupo = pubs.filter((p) => p.categoria === g.slug).slice(0, 2);
                    return (
                      <Card key={g.slug} className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
                        <CardHeader className="pb-2">
                          <CardTitle className="text-base flex items-center gap-2 text-[var(--cor-texto)]"><Users className="h-4 w-4 text-[var(--cor-primaria)]" aria-hidden />{g.nome}</CardTitle>
                          <CardDescription className="text-xs">{g.desc}</CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-2">
                          {pubsGrupo.length ? pubsGrupo.map((p) => <Link key={p.id} href={`/comunidade/${p.id}`} className="block rounded-md border border-[var(--cor-borda)] p-2 hover:bg-[var(--cor-primaria-suave)]"><p className="text-sm font-medium text-[var(--cor-texto)] line-clamp-1">{p.titulo}</p><p className="text-xs text-[var(--cor-texto-suave)]">{p.tipo} · {p.autor_nome}</p></Link>) : <p className="text-xs text-[var(--cor-texto-suave)]">Sem publicações ainda.</p>}
                          <div className="flex gap-2 pt-1">
                            <Button size="sm" variant="outline" className="flex-1 border-[var(--cor-borda)]" onClick={() => verGrupo(g.slug)}><Eye className="mr-1 h-3.5 w-3.5" aria-hidden />Ver feed</Button>
                            <Button size="sm" variant="ghost" onClick={() => toggleGrupo(g.slug)}>Sair</Button>
                          </div>
                        </CardContent>
                      </Card>
                    );
                  })}
                </div>
              )}
              {!token && <Card className="border-dashed border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)]"><CardContent className="p-4 flex items-center justify-between gap-3"><p className="text-sm text-[var(--cor-texto-suave)]">Entre para seguir autores de verdade (via API).</p><Button size="sm" variant="outline" className="border-[var(--cor-borda)]" onClick={() => window.location.href = "/login"}><LogIn className="mr-1 h-4 w-4" aria-hidden />Entrar</Button></CardContent></Card>}
            </TabsContent>
          </Tabs>
        </div>

        {/* Coluna lateral viva */}
        <aside className="min-w-0 space-y-3" aria-label="Destaques e tendências da comunidade">
          <Card className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center gap-1.5 text-sm text-[var(--cor-texto)]"><Star className="h-4 w-4 text-[var(--cor-primaria)]" aria-hidden />Discussões em destaque</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {destaques.length === 0 && <p className="text-xs text-[var(--cor-texto-suave)]">A curadoria ainda não marcou destaques.</p>}
              {destaques.map((p) => (
                <Link key={p.id} href={`/comunidade/${p.id}`} className="block rounded-md border border-[var(--cor-borda)] p-2 hover:bg-[var(--cor-primaria-suave)]">
                  <SeloFormato formato={formatoDaPublicacao(p.tipo, p.numero_comentarios ?? 0)} />
                  <p className="mt-1 text-sm font-medium text-[var(--cor-texto)] line-clamp-2">{p.titulo}</p>
                  <p className="text-xs text-[var(--cor-texto-suave)]">{p.autor_nome} · {p.numero_comentarios ?? 0} comentários</p>
                </Link>
              ))}
            </CardContent>
          </Card>

          <Card className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center gap-1.5 text-sm text-[var(--cor-texto)]"><Flame className="h-4 w-4 text-[var(--cor-primaria)]" aria-hidden />Mais discutidos</CardTitle>
            </CardHeader>
            <CardContent className="space-y-1.5">
              {maisDiscutidos.map((p, i) => (
                <Link key={p.id} href={`/comunidade/${p.id}`} className="flex items-center gap-2 rounded-md p-1.5 hover:bg-[var(--cor-primaria-suave)]">
                  <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[var(--cor-fundo-elevado)] border border-[var(--cor-borda)] text-xs font-bold text-[var(--cor-texto)]" aria-hidden>{i + 1}</span>
                  <span className="min-w-0"><span className="block truncate text-sm font-medium text-[var(--cor-texto)]">{p.titulo}</span>
                  <span className="text-xs text-[var(--cor-texto-suave)]">{p.numero_comentarios ?? 0} comentários · {p.categoria}</span></span>
                </Link>
              ))}
              {maisDiscutidos.length === 0 && <p className="text-xs text-[var(--cor-texto-suave)]">Sem termômetro ainda.</p>}
            </CardContent>
          </Card>

          <Card className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center gap-1.5 text-sm text-[var(--cor-texto)]"><TrendingUp className="h-4 w-4 text-[var(--cor-primaria)]" aria-hidden />Assuntos em alta</CardTitle>
              <CardDescription className="text-xs">Do radar do portal — toque para filtrar o debate</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-wrap gap-1.5">
              {assuntos.length > 0 ? assuntos.map((a) => (
                <button
                  key={a.categoria}
                  onClick={() => { setCatFiltro(a.categoria); setGrupoFiltro(null); setTab("feed"); registrarEventoComunidade("filtrar", { categoria: a.categoria }); }}
                  className="rounded-full border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] px-2.5 py-1 text-xs text-[var(--cor-texto)] hover:bg-[var(--cor-primaria-suave)]"
                >
                  {a.categoria} <span className="text-[var(--cor-texto-suave)]">· {a.numero_noticias}</span>
                </button>
              )) : assuntosFallback.length > 0 ? assuntosFallback.map(([tag, n]) => (
                <button
                  key={tag}
                  onClick={() => { setBusca(tag); setTab("feed"); }}
                  className="rounded-full border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] px-2.5 py-1 text-xs text-[var(--cor-texto)] hover:bg-[var(--cor-primaria-suave)]"
                >
                  #{tag} <span className="text-[var(--cor-texto-suave)]">· {n}</span>
                </button>
              )) : <p className="text-xs text-[var(--cor-texto-suave)]">Nenhum assunto em alta agora.</p>}
            </CardContent>
          </Card>

          <Card className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center gap-1.5 text-sm text-[var(--cor-texto)]"><Clock className="h-4 w-4 text-[var(--cor-primaria)]" aria-hidden />Recentes</CardTitle>
            </CardHeader>
            <CardContent className="space-y-1.5">
              {[...pubs].slice(0, 4).map((p) => (
                <Link key={p.id} href={`/comunidade/${p.id}`} className="block rounded-md p-1.5 hover:bg-[var(--cor-primaria-suave)]">
                  <p className="truncate text-sm font-medium text-[var(--cor-texto)]">{p.titulo}</p>
                  <p className="text-xs text-[var(--cor-texto-suave)]">{formatarDataCurta(p.criado_em)} · {p.autor_nome}</p>
                </Link>
              ))}
              {pubs.length === 0 && <p className="text-xs text-[var(--cor-texto-suave)]">Nada por aqui ainda.</p>}
            </CardContent>
          </Card>
        </aside>
      </div>

      <Dialog open={openCriar} onOpenChange={setOpenCriar}>
        <DialogContent className="bg-[var(--cor-fundo-card)] border-[var(--cor-borda)] max-h-[90vh] overflow-y-auto">
          <DialogHeader><DialogTitle>Nova publicação rápida</DialogTitle><DialogDescription>Cria rascunho e envia em seguida. Use a página completa para mais campos.</DialogDescription></DialogHeader>
          <div className="space-y-3">
            <div className="space-y-1.5"><Label htmlFor="qc-titulo">Título</Label><Input id="qc-titulo" value={criar.titulo} onChange={(e) => setCriar((s) => ({ ...s, titulo: e.target.value }))} placeholder="Título..." /></div>
            <div className="grid grid-cols-2 gap-2">
              <div className="space-y-1.5"><Label>Formato</Label><Select value={criar.tipo} onValueChange={(v) => setCriar((s) => ({ ...s, tipo: v as api.TipoPublicacao }))}><SelectTrigger className="bg-[var(--cor-fundo-card)]"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="opiniao">Opinião</SelectItem><SelectItem value="analise">Coluna / Análise</SelectItem></SelectContent></Select></div>
              <div className="space-y-1.5"><Label>Categoria (grupo)</Label><Select value={criar.categoria} onValueChange={(v) => setCriar((s) => ({ ...s, categoria: v }))}><SelectTrigger className="bg-[var(--cor-fundo-card)]"><SelectValue /></SelectTrigger><SelectContent>{GRUPOS.map((g) => <SelectItem key={g.slug} value={g.slug}>{g.nome}</SelectItem>)}</SelectContent></Select></div>
            </div>
            <div className="space-y-1.5"><Label htmlFor="qc-tags">Tags (vírgula)</Label><Input id="qc-tags" value={criar.tags} onChange={(e) => setCriar((s) => ({ ...s, tags: e.target.value }))} placeholder="ex: política, cidades" /></div>
            <div className="space-y-1.5"><Label htmlFor="qc-conteudo">Conteúdo</Label><Textarea id="qc-conteudo" rows={5} value={criar.conteudo} onChange={(e) => setCriar((s) => ({ ...s, conteudo: e.target.value }))} placeholder="Escreva..." /></div>
          </div>
          <DialogFooter><Button variant="outline" onClick={() => setOpenCriar(false)} className="border-[var(--cor-borda)]">Cancelar</Button><Button onClick={handleCriar} className="bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)] gap-1"><Send className="h-4 w-4" aria-hidden />Publicar</Button></DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={openComentar.open} onOpenChange={(o) => setOpenComentar((s) => ({ ...s, open: o }))}>
        <DialogContent className="bg-[var(--cor-fundo-card)] border-[var(--cor-borda)]">
          <DialogHeader><DialogTitle>Comentar</DialogTitle><DialogDescription>Seu comentário na publicação #{openComentar.pubId}</DialogDescription></DialogHeader>
          <Textarea rows={4} value={comentarioTxt} onChange={(e) => setComentarioTxt(e.target.value)} placeholder="Escreva seu comentário..." aria-label="Texto do comentário" />
          <DialogFooter><Button variant="outline" onClick={() => setOpenComentar({ open: false })} className="border-[var(--cor-borda)]">Cancelar</Button><Button onClick={handleComentar} className="bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]"><Send className="mr-1 h-4 w-4" aria-hidden />Enviar</Button></DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={openDenuncia.open} onOpenChange={(o) => setOpenDenuncia((s) => ({ ...s, open: o }))}>
        <DialogContent className="bg-[var(--cor-fundo-card)] border-[var(--cor-borda)]">
          <DialogHeader><DialogTitle className="flex items-center gap-2"><Shield className="h-4 w-4" aria-hidden />Denunciar</DialogTitle><DialogDescription>Conteúdo #{openDenuncia.pubId ?? openDenuncia.comentarioId}</DialogDescription></DialogHeader>
          <div className="space-y-1.5"><Label htmlFor="motivo">Motivo</Label><Textarea id="motivo" rows={3} value={motivo} onChange={(e) => setMotivo(e.target.value)} placeholder="Descreva a violação..." /></div>
          <DialogFooter><Button variant="outline" onClick={() => setOpenDenuncia({ open: false })} className="border-[var(--cor-borda)]">Cancelar</Button><Button onClick={handleDenunciar} variant="destructive"><Flag className="mr-1 h-4 w-4" aria-hidden />Enviar denúncia</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
