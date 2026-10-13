"use client";
import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@/lib/auth-context";
import { salvarLocalidade, removerLocalidade, type LocalidadeSalva, type RadarNoticiaItem } from "@/lib/api";
import {
  useQueryTendenciasRadar,
  useQueryRadarEvolucao,
  useQueryRadarLocalidadesSalvas,
  useQueryNoticiasRadar,
  invalidarQueriesRadarLocalidades,
} from "@/lib/queries";
import { queryKeys } from "@/lib/query-keys";
import { usePremiumAtivo } from "@/lib/premium";
import { AdsSlot } from "@/components/AdsSlot";
import { EstadoVazio } from "@/components/EstadoVazio";
import RadarLocalSimples from "@/components/RadarLocalSimples";
import { ImagemNoticia } from "@/components/ImagemNoticia";
import { timeAgo } from "@/lib/editorial";
import type { Regiao } from "@/lib/regiao";
import { cn } from "@/lib/utils";
import { formatarDataSemAno } from "@/lib/datas";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import {
  RefreshCw,
  MapPin,
  TrendingUp,
  BarChart3,
  BookmarkPlus,
  Bookmark,
  X,
  AlertCircle,
  Loader2,
  ExternalLink,
  Crown,
  LayoutGrid,
  Search,
  Navigation,
} from "lucide-react";

const CATS = ["", "politica", "economia", "tecnologia", "cidades", "esportes", "cultura", "geral"];

// R-03 — siglas das 27 UFs (26 estados + DF), mesma lista pública usada
// pelo backend (`backend/radar/geografia.py`) e por `EnderecoInteligente.tsx`
// (`UFS_FALLBACK`) — não depende de uma chamada de rede para popular o filtro.
const UFS = ["AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO"];

const PERIODOS = [
  { valor: 7, rotulo: "7 dias" },
  { valor: 14, rotulo: "14 dias" },
  { valor: 30, rotulo: "30 dias" },
  { valor: 90, rotulo: "90 dias" },
];

function locLabel(l: { pais?: string | null; estado?: string | null }) {
  // R-02 — nunca promete filtro por cidade (não existe de verdade): o
  // recorte regional real é por UF.
  const p = [l.pais, l.estado].filter(Boolean).join(" · ");
  return p ? `Notícias de ${p}` : "Recorte nacional";
}

function linkNoticia(item: { tipo: "cluster" | "item"; id: number; cluster_id: number | null }) {
  if (item.cluster_id) return `/noticia/cluster/${item.cluster_id}`;
  return `/noticia/item/${item.id}`;
}

/** Card do grid estilo marketplace (R-03): foto + título + UF + tempo + categoria. */
function CardNoticiaRadar({ item }: { item: RadarNoticiaItem }) {
  return (
    <Link
      href={linkNoticia(item)}
      className="group flex flex-col overflow-hidden rounded-[var(--raio-md)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] transition-shadow hover:shadow-[var(--sombra-1)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]"
    >
      <div className="relative aspect-[16/9] w-full overflow-hidden bg-[var(--cor-fundo-elevado)]">
        <ImagemNoticia
          src={item.imagem_url}
          alt={item.titulo}
          seed={`radar-${item.tipo}-${item.id}`}
          className="h-full w-full object-cover transition-transform group-hover:scale-[1.03]"
        />
        {item.categoria && (
          <Badge className="absolute left-2 top-2 border-transparent bg-[var(--cor-fundo-card)]/90 text-[var(--cor-texto)] capitalize shadow-sm">
            {item.categoria}
          </Badge>
        )}
      </div>
      <div className="flex min-w-0 flex-1 flex-col gap-1.5 p-3">
        <h3 className="line-clamp-2 min-w-0 text-sm font-semibold leading-snug text-[var(--cor-texto)]">{item.titulo}</h3>
        <div className="mt-auto flex min-w-0 flex-wrap items-center gap-2 text-xs text-[var(--cor-texto-suave)]">
          {item.estado && (
            <span className="inline-flex items-center gap-0.5 shrink-0">
              <MapPin className="h-3 w-3" aria-hidden />
              {item.estado}
            </span>
          )}
          <time dateTime={item.timestamp} suppressHydrationWarning className="shrink-0">
            {timeAgo(item.timestamp)}
          </time>
          {typeof item.distancia_km === "number" && (
            <span className="inline-flex items-center gap-0.5 shrink-0 text-[var(--cor-primaria)]">
              <Navigation className="h-3 w-3" aria-hidden />
              {item.distancia_km < 1 ? "<1 km" : `${Math.round(item.distancia_km)} km`}
            </span>
          )}
          {item.nome_fonte && <span className="min-w-0 truncate">{item.nome_fonte}</span>}
        </div>
      </div>
    </Link>
  );
}

export default function RadarClient() {
  const { token, usuario } = useAuth();
  const isPremium = usuario?.papel === "premium" || usuario?.papel === "admin";
  const { liberado } = usePremiumAtivo();
  const premiumGeral = isPremium || liberado;
  const [regiao, setRegiao] = useState<Regiao | null>(null);
  // Fonte única de local (FRENTE 5): tendências e evolução derivam da mesma
  // região. R-02: `estado` (não `cidade`, que a ingestão real nunca popula)
  // + `lat`/`lon` quando disponíveis, para ordenar por proximidade.
  const filtros = useMemo(() => ({
    pais: regiao?.pais || undefined,
    estado: regiao?.estado || undefined,
    lat: regiao?.lat,
    lon: regiao?.lon,
  }), [regiao]);
  const [evoCat, setEvoCat] = useState("");
  const evoFiltros = useMemo(() => ({
    categoria: evoCat || undefined,
    pais: regiao?.pais || undefined,
    estado: regiao?.estado || undefined,
  }), [evoCat, regiao]);
  const [msg, setMsg] = useState<string | null>(null);
  const [tab, setTab] = useState("noticias");
  const [upsellOpen, setUpsellOpen] = useState(false);
  const queryClient = useQueryClient();
  const usuarioId = usuario?.id ?? 0;

  // R-03 — grid estilo marketplace: filtros próprios (categoria/UF/período
  // + busca textual + ordenação), com a UF do local detectado como ponto de
  // partida (o usuário pode trocar sem perder a localização salva).
  const [categoriaGrid, setCategoriaGrid] = useState("");
  const [estadoGrid, setEstadoGrid] = useState("");
  const [periodoGrid, setPeriodoGrid] = useState(30);
  const [buscaInput, setBuscaInput] = useState("");
  const [buscaGrid, setBuscaGrid] = useState("");
  const [ordenarGrid, setOrdenarGrid] = useState<"recencia" | "proximidade">("recencia");

  useEffect(() => {
    const t = setTimeout(() => setBuscaGrid(buscaInput.trim()), 400);
    return () => clearTimeout(t);
  }, [buscaInput]);

  // UF do grid segue a região detectada/salva até o usuário escolher outra.
  useEffect(() => {
    if (regiao?.estado && !estadoGrid) setEstadoGrid(regiao.estado);
  }, [regiao, estadoGrid]);

  const temCoordenada = typeof regiao?.lat === "number" && typeof regiao?.lon === "number";
  const noticiasFiltros = useMemo(() => ({
    estado: estadoGrid || undefined,
    categoria: categoriaGrid || undefined,
    busca: buscaGrid || undefined,
    periodoDias: periodoGrid,
    lat: ordenarGrid === "proximidade" && temCoordenada ? regiao?.lat : undefined,
    lon: ordenarGrid === "proximidade" && temCoordenada ? regiao?.lon : undefined,
  }), [estadoGrid, categoriaGrid, buscaGrid, periodoGrid, ordenarGrid, temCoordenada, regiao]);

  const tendenciasQuery = useQueryTendenciasRadar(filtros, true);
  const evolucaoQuery = useQueryRadarEvolucao({
    token,
    usuarioId,
    filtros: evoFiltros,
  });
  const localidadesQuery = useQueryRadarLocalidadesSalvas({
    token,
    usuarioId,
  });
  const noticiasQuery = useQueryNoticiasRadar(noticiasFiltros);

  // P0-08: sem fallback inventado. Se o radar falhar, a tela mostra um estado
  // de erro explícito em vez de "assuntos em alta" com números fabricados.
  const tend = tendenciasQuery.data;
  const loadingT = tendenciasQuery.isFetching;

  // P0-08: a série histórica usava mockSerie() (números aleatórios) como
  // fallback. Agora só mostramos a série que a API devolveu; 403 continua sendo
  // upsell de Premium, mas sem número inventado.
  const evo = evolucaoQuery.data;
  const loadingE = Boolean(token) && evolucaoQuery.isFetching;
  const salvas = localidadesQuery.data ?? [];
  const noticias = noticiasQuery.data;
  const loadingN = noticiasQuery.isFetching;

  const salvarMutation = useMutation({
    mutationFn: (dados: Parameters<typeof salvarLocalidade>[1]) => {
      if (!token) throw new Error("Faça login para salvar localidades.");
      return salvarLocalidade(token, dados);
    },
    onSuccess: () => {
      setMsg("Localidade salva.");
      void invalidarQueriesRadarLocalidades(queryClient, usuarioId);
    },
    onError: (error: unknown) => {
      setMsg(error instanceof Error ? error.message : "Erro ao salvar.");
    },
  });
  const removerMutation = useMutation({
    mutationFn: (localidade: LocalidadeSalva) => {
      if (!token) throw new Error("Faça login para gerenciar localidades.");
      return removerLocalidade(token, {
        pais: localidade.pais || undefined,
        estado: localidade.estado || undefined,
        cidade: localidade.cidade || undefined,
      });
    },
    onSuccess: (_result, localidade) => {
      queryClient.setQueryData<LocalidadeSalva[]>(
        queryKeys.radar.localidadesSalvas(usuarioId),
        (atuais) => (atuais ?? []).filter(
          (item) => !(
            item.pais === localidade.pais &&
            item.estado === localidade.estado &&
            item.cidade === localidade.cidade
          )
        )
      );
      void invalidarQueriesRadarLocalidades(queryClient, usuarioId);
    },
  });

  function handleSalvar() {
    if (!token) { setMsg("Faça login para salvar localidades."); setTimeout(() => setMsg(null), 3000); return; }
    const p = regiao?.pais || ""; const e = regiao?.estado || ""; const c = regiao?.cidade || "";
    if (!p && !e && !c) { setMsg("Escolha um local acima para salvar."); setTimeout(() => setMsg(null), 3000); return; }
    salvarMutation.mutate({ pais: p || undefined, estado: e || undefined, cidade: c || undefined });
    setTimeout(() => setMsg(null), 3000);
  }
  function handleRemover(localidade: LocalidadeSalva) {
    if (!token) return;
    removerMutation.mutate(localidade);
  }
  function usarSalva(l: LocalidadeSalva) { setRegiao({ cidade: l.cidade || "", estado: l.estado || "", pais: l.pais || "Brasil" }); }

  const assuntos = tend?.assuntos_em_alta ?? [];
  const evoExibido = evo && !premiumGeral ? { ...evo, serie: evo.serie.slice(-7) } : evo;
  const maxEvo = evoExibido ? Math.max(...evoExibido.serie.map((s) => s.numero_noticias), 1) : 1;
  const itensGrid = noticias?.itens ?? [];

  return (
    <div className="mx-auto max-w-6xl space-y-4 py-6 px-4">
      <div className="hud-line" aria-hidden />
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div><h1 className="text-2xl font-bold text-[var(--cor-texto)] flex items-center gap-2"><TrendingUp className="h-6 w-6 text-[var(--cor-neon-ciano)]" />Radar</h1><p className="text-sm text-[var(--cor-texto-suave)] flex items-center gap-1 mt-1"><MapPin className="h-3.5 w-3.5" />{tend ? locLabel(tend.localidade) : locLabel(filtros)}</p></div>
        <Button variant="outline" size="sm" onClick={() => { void tendenciasQuery.refetch(); if (token) void evolucaoQuery.refetch(); void localidadesQuery.refetch(); void noticiasQuery.refetch(); }} className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]"><RefreshCw className="h-4 w-4" />Atualizar</Button>
      </div>

      {tend?.erro_localidade && (
        <Alert className="border-[var(--cor-erro)]/40 bg-[var(--cor-erro-suave)]">
          <AlertCircle className="h-4 w-4 text-[var(--cor-erro)]" />
          <AlertTitle className="text-[var(--cor-texto)] text-sm">Local não identificado</AlertTitle>
          <AlertDescription className="text-[var(--cor-texto-suave)] text-xs">{tend.erro_localidade}</AlertDescription>
        </Alert>
      )}
      {tendenciasQuery.isError && (
        <EstadoVazio
          tom="erro"
          titulo="Não foi possível carregar as tendências"
          descricao="O radar não respondeu. Nenhum número de notícias foi estimado para preencher a lista."
          rotuloTentarDeNovo="Atualizar radar"
          onTentarDeNovo={() => void tendenciasQuery.refetch()}
        />
      )}
      {tend?.aviso_metodologia && <Alert className="border-[var(--cor-neon-ciano)]/30 bg-[var(--cor-destaque-suave)]"><AlertCircle className="h-4 w-4 text-[var(--cor-neon-ciano)]" /><AlertTitle className="text-[var(--cor-texto)] text-sm">Metodologia</AlertTitle><AlertDescription className="text-[var(--cor-texto-suave)] text-xs">{tend.aviso_metodologia}</AlertDescription></Alert>}
      {msg && <Alert className="border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)]"><AlertDescription className="text-sm text-[var(--cor-texto)]">{msg}</AlertDescription></Alert>}

      <Card className="bento border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
        <CardHeader className="pb-3"><CardTitle className="text-base flex items-center gap-2"><MapPin className="h-4 w-4 text-[var(--cor-neon-ciano)]" />Local</CardTitle><CardDescription className="text-[var(--cor-texto-suave)]">Um recorte por estado para notícias, tendências e evolução</CardDescription></CardHeader>
        <CardContent className="space-y-4">
          <RadarLocalSimples value={regiao} onChange={setRegiao} />
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={handleSalvar} className="border-[var(--cor-neon-ciano)]/40 text-[var(--cor-texto)] min-h-[44px]"><BookmarkPlus className="h-4 w-4" />Salvar localidade</Button>
          </div>
          <div className="space-y-2">
            <p className="text-xs font-medium text-[var(--cor-texto-suave)] flex items-center gap-1"><Bookmark className="h-3.5 w-3.5" />Localidades salvas {token ? "" : "— faça login"}</p>
            {!token ? <p className="text-xs text-[var(--cor-texto-suave)]">Faça login para salvar e gerenciar localidades. Tendências continuam disponíveis.</p> : salvas.length === 0 ? <p className="text-xs text-[var(--cor-texto-suave)]">Nenhuma localidade salva.</p> : <div className="flex flex-wrap gap-2">{salvas.map((l, i) => (
              <span key={`${l.pais}-${l.estado}-${l.cidade}-${i}`} className="inline-flex items-center gap-1 rounded-full border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] px-3 py-1 text-xs text-[var(--cor-texto)]">
                <button onClick={() => usarSalva(l)} className="hover:underline">{[l.pais, l.estado, l.cidade].filter(Boolean).join(" · ") || "—"}</button>
                <button aria-label="Remover" onClick={() => handleRemover(l)} className="ml-1 rounded-full p-0.5 hover:bg-[var(--cor-borda)]"><X className="h-3 w-3" /></button>
              </span>
            ))}</div>}
          </div>
        </CardContent>
      </Card>

      <Tabs value={tab} onValueChange={setTab} className="w-full">
        <TabsList className="h-auto flex-wrap bg-[var(--cor-borda)]">
          <TabsTrigger value="noticias" className="data-[state=active]:bg-[var(--cor-fundo-card)]"><LayoutGrid className="h-4 w-4 mr-1" />Notícias</TabsTrigger>
          <TabsTrigger value="tendencias" className="data-[state=active]:bg-[var(--cor-fundo-card)]"><TrendingUp className="h-4 w-4 mr-1" />Tendências</TabsTrigger>
          <TabsTrigger value="evolucao" className="data-[state=active]:bg-[var(--cor-fundo-card)]"><BarChart3 className="h-4 w-4 mr-1" />Evolução</TabsTrigger>
        </TabsList>

        <TabsContent value="noticias" className="space-y-3">
          <Card className="bento border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
            <CardContent className="space-y-3 pt-4">
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
                <div className="col-span-2 space-y-1 sm:col-span-2">
                  <Label className="text-xs">Buscar</Label>
                  <div className="relative">
                    <Search className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--cor-texto-suave)]" />
                    <Input value={buscaInput} onChange={(e) => setBuscaInput(e.target.value)} placeholder="Buscar por título" className="min-h-[44px] bg-[var(--cor-fundo-elevado)] pl-8" />
                  </div>
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">Categoria</Label>
                  <Select value={categoriaGrid} onValueChange={setCategoriaGrid}>
                    <SelectTrigger className="min-h-[44px] border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)]"><SelectValue placeholder="Todas" /></SelectTrigger>
                    <SelectContent>{CATS.map((c) => <SelectItem key={c} value={c}>{c || "Todas"}</SelectItem>)}</SelectContent>
                  </Select>
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">UF</Label>
                  <Select value={estadoGrid} onValueChange={setEstadoGrid}>
                    <SelectTrigger className="min-h-[44px] border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)]"><SelectValue placeholder="Todas" /></SelectTrigger>
                    <SelectContent><SelectItem value="">Todas</SelectItem>{UFS.map((u) => <SelectItem key={u} value={u}>{u}</SelectItem>)}</SelectContent>
                  </Select>
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">Período</Label>
                  <Select value={String(periodoGrid)} onValueChange={(v) => setPeriodoGrid(Number(v))}>
                    <SelectTrigger className="min-h-[44px] border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)]"><SelectValue /></SelectTrigger>
                    <SelectContent>{PERIODOS.map((p) => <SelectItem key={p.valor} value={String(p.valor)}>{p.rotulo}</SelectItem>)}</SelectContent>
                  </Select>
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <Label className="text-xs text-[var(--cor-texto-suave)]">Ordenar por</Label>
                <Select value={ordenarGrid} onValueChange={(v) => setOrdenarGrid(v as "recencia" | "proximidade")}>
                  <SelectTrigger className="min-h-[40px] w-[220px] border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)]"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="recencia">Mais recentes</SelectItem>
                    <SelectItem value="proximidade" disabled={!temCoordenada}>Mais perto de você{!temCoordenada ? " (detecte o local)" : ""}</SelectItem>
                  </SelectContent>
                </Select>
                {noticias?.ordenado_por === "distancia" && (
                  <Badge variant="outline" className="border-[var(--cor-primaria)] text-[var(--cor-primaria)]"><Navigation className="mr-1 h-3 w-3" />Por proximidade</Badge>
                )}
              </div>
            </CardContent>
          </Card>

          {noticias?.erro_localidade && (
            <Alert className="border-[var(--cor-erro)]/40 bg-[var(--cor-erro-suave)]">
              <AlertCircle className="h-4 w-4 text-[var(--cor-erro)]" />
              <AlertTitle className="text-[var(--cor-texto)] text-sm">Local não identificado</AlertTitle>
              <AlertDescription className="text-[var(--cor-texto-suave)] text-xs">{noticias.erro_localidade}</AlertDescription>
            </Alert>
          )}
          {noticiasQuery.isError ? (
            <EstadoVazio
              tom="erro"
              titulo="Não foi possível carregar as notícias"
              descricao="O radar não respondeu. Nenhuma notícia foi inventada para preencher a lista."
              rotuloTentarDeNovo="Atualizar"
              onTentarDeNovo={() => void noticiasQuery.refetch()}
            />
          ) : loadingN ? (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
              {Array.from({ length: 8 }).map((_, i) => <div key={i} className="aspect-[4/5] animate-pulse rounded-[var(--raio-md)] bg-[var(--cor-borda)]" />)}
            </div>
          ) : itensGrid.length === 0 ? (
            <div className="rounded-[var(--raio-md)] border border-dashed border-[var(--cor-borda)] p-8 text-center">
              <p className="text-sm text-[var(--cor-texto-suave)]">Nenhuma notícia para estes filtros.</p>
              <p className="text-xs text-[var(--cor-texto-suave)] mt-1">Tente outra UF, categoria ou período maior.</p>
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
              {itensGrid.map((item) => <CardNoticiaRadar key={`${item.tipo}-${item.id}`} item={item} />)}
            </div>
          )}
        </TabsContent>

        <TabsContent value="tendencias">
          <Card className="bento border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
            <CardHeader className="pb-2"><CardTitle className="text-base">Assuntos em alta</CardTitle><CardDescription className="text-[var(--cor-texto-suave)]">{assuntos.length ? `${assuntos.length} categorias no recorte` : "Sem dados para este recorte"}</CardDescription></CardHeader>
            <CardContent>
              {loadingT ? <div className="grid gap-3">{Array.from({ length: 4 }).map((_, i) => <div key={i} className="h-16 animate-pulse rounded-[var(--raio-md)] bg-[var(--cor-borda)]" />)}</div> : assuntos.length === 0 ? <div className="rounded-[var(--raio-md)] border border-dashed border-[var(--cor-borda)] p-8 text-center"><p className="text-sm text-[var(--cor-texto-suave)]">Nenhum assunto em alta para este recorte.</p><p className="text-xs text-[var(--cor-texto-suave)] mt-1">Tente limpar filtros ou escolher outro recorte.</p></div> : <div className="grid gap-3">{assuntos.map((a, i) => {
                const href = a.cluster_id ? `/noticia/cluster/${a.cluster_id}` : a.item_id ? `/noticia/item/${a.item_id}` : `/noticia/${a.item_id ?? a.cluster_id ?? ""}`;
                const hasLink = !!(a.cluster_id || a.item_id);
                return (
                  <div key={`${a.categoria}-${i}`} className={cn("flex items-center justify-between rounded-[var(--raio-md)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-3 glass")}>
                    <div className="min-w-0"><p className="font-medium capitalize text-[var(--cor-texto)] truncate">{a.categoria}</p><p className="text-xs text-[var(--cor-texto-suave)]">{a.numero_noticias} notícias · {a.numero_fontes} fontes{(a.crescimento_24h ?? 0) > 0 ? ` · +${Math.round((a.crescimento_24h ?? 0) * 100)}% em 24h` : ""}{(a.buscas_relacionadas ?? 0) > 0 ? ` · ${a.buscas_relacionadas} buscas` : ""}{typeof a.distancia_km === "number" ? ` · ${Math.round(a.distancia_km)} km` : ""}</p></div>
                    <div className="flex items-center gap-2 shrink-0 ml-3">
                      {hasLink ? <Link href={href} className="inline-flex items-center gap-1 text-xs font-medium text-[var(--cor-primaria)] hover:underline">Ver<ExternalLink className="h-3 w-3" /></Link> : <span className="text-xs text-[var(--cor-texto-suave)]">—</span>}
                      <Badge className="bg-[var(--cor-neon-ciano)] text-[var(--cor-texto-invertido)] border-transparent shrink-0">#{i + 1}</Badge>
                    </div>
                  </div>
                );
              })}</div>}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="evolucao">
          <Card className="bento border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
            <CardHeader className="pb-3"><CardTitle className="text-base">Evolução por categoria</CardTitle><CardDescription className="text-[var(--cor-texto-suave)]">Série diária de volume de cobertura no recorte</CardDescription></CardHeader>
            <CardContent className="space-y-4">
              {!token ? <div className="rounded-[var(--raio-md)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-6 text-center"><p className="text-sm font-medium text-[var(--cor-texto)]">Faça login para ver a evolução</p><p className="text-xs text-[var(--cor-texto-suave)] mt-1">Este recurso é Premium e requer autenticação.</p><Button asChild size="sm" className="mt-3 bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]"><Link href="/login">Entrar</Link></Button></div> : (
                <>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div className="space-y-1">
                      <Label>Categoria</Label>
                      <Select value={evoCat} onValueChange={setEvoCat}>
                        <SelectTrigger className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]"><SelectValue placeholder="Todas" /></SelectTrigger>
                        <SelectContent>{CATS.map((c) => <SelectItem key={c} value={c}>{c || "Todas"}</SelectItem>)}</SelectContent>
                      </Select>
                    </div>
                    <p className="self-end text-xs text-[var(--cor-texto-suave)]">Usa o mesmo local acima — sem repetir campos.</p>
                  </div>
                  {evo?.erro_localidade && <p className="text-xs text-[var(--cor-erro)]">{evo.erro_localidade}</p>}
                   <div className="flex items-center gap-2">{!premiumGeral && evo && <Badge variant="outline" className="border-[var(--cor-premium)] text-[var(--cor-premium)]"><Crown className="mr-1 h-3 w-3" /> 7 dias no Free</Badge>}</div>
                  {evoExibido?.aviso_metodologia && <p className="text-xs text-[var(--cor-texto-suave)] border-l-2 border-[var(--cor-neon-ciano)] pl-2">{evoExibido.aviso_metodologia}</p>}
                  {loadingE ? <div className="h-40 animate-pulse rounded-[var(--raio-md)] bg-[var(--cor-borda)]" /> : evolucaoQuery.isError ? <EstadoVazio tom="erro" titulo="Não foi possível carregar a evolução" descricao="Nenhuma série foi estimada para este recorte." rotuloTentarDeNovo="Atualizar série" onTentarDeNovo={() => void evolucaoQuery.refetch()} /> : !evoExibido || evoExibido.serie.length === 0 ? <EstadoVazio titulo="Sem dados para esta categoria/recorte" descricao="A API não retornou série de cobertura para estes filtros." /> : (
                    <>
                      <div className="rounded-[var(--raio-md)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-3">
                        <div className="flex items-end gap-1 h-40">
                          {evoExibido.serie.map((p) => (
                            <div key={p.dia} className="flex flex-1 flex-col items-center justify-end gap-1">
                              <span className="text-[10px] font-medium text-[var(--cor-texto)]">{p.numero_noticias}</span>
                              <div className="w-full rounded-t-[var(--raio-sm)] bg-[var(--cor-neon-ciano)] transition-all" style={{ height: `${Math.max(4, (p.numero_noticias / maxEvo) * 100)}%`, minHeight: 4 }} aria-label={`${p.dia}: ${p.numero_noticias}`} />
                              <span className="text-[10px] text-[var(--cor-texto-suave)]">{formatarDataSemAno(p.dia) || p.dia.slice(5)}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                        {evoExibido.serie.map((p) => (
                          <div key={p.dia} className="rounded-[var(--raio-sm)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] px-2 py-1 flex justify-between text-xs"><span className="text-[var(--cor-texto-suave)]">{p.dia.slice(5)}</span><span className="font-medium text-[var(--cor-texto)]">{p.numero_noticias}</span></div>
                        ))}
                      </div>
                      {!premiumGeral && evo && evo.serie.length > 7 && <div className="rounded-[var(--raio-md)] border border-[var(--cor-premium)]/30 bg-[var(--cor-premium-suave)] p-3 flex items-center justify-between gap-3"><p className="text-xs text-[var(--cor-texto)]"><Crown className="inline h-3.5 w-3.5 text-[var(--cor-premium)] mr-1" />Você está vendo apenas os últimos 7 dias. Seja Premium para ver até 30 dias e comparar recortes.</p><Button size="sm" variant="outline" className="shrink-0 border-[var(--cor-premium)] text-[var(--cor-premium)]" onClick={() => setUpsellOpen(true)}>Ver Premium</Button></div>}
                    </>
                  )}
                </>
              )}
              {loadingE && <p className="flex items-center gap-1 text-xs text-[var(--cor-texto-suave)]"><Loader2 className="h-3 w-3 animate-spin" />Carregando evolução…</p>}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
      <AdsSlot id="radar-retangulo" formato="retangulo" />
      <Dialog open={upsellOpen} onOpenChange={setUpsellOpen}>
        <DialogContent className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2"><Crown className="h-5 w-5 text-[var(--cor-premium)]" /> Quer ver mais do Radar?</DialogTitle>
            <DialogDescription>Com Premium você vê até 30 dias de evolução, compara recortes com mais profundidade e usa o feed sem anúncios. Sem pressão — só mais contexto quando precisar.</DialogDescription>
          </DialogHeader>
          <div className="rounded-md border border-[var(--cor-premium)]/20 bg-[var(--cor-premium-suave)] p-3 text-sm text-[var(--cor-texto)]">No plano free, a evolução mostra os últimos 7 dias. É útil para um olhar rápido; o histórico completo fica para quem precisa acompanhar um tema por mais tempo.</div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setUpsellOpen(false)} className="border-[var(--cor-borda)]">Continuar no Free</Button>
            <Button asChild className="bg-[var(--cor-premium)] text-[var(--cor-texto-invertido)]"><Link href="/planos">Conhecer Premium</Link></Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
