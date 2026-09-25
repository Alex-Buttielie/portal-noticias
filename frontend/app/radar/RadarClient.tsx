"use client";
import { useMemo, useState } from "react";
import Link from "next/link";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@/lib/auth-context";
import { salvarLocalidade, removerLocalidade, ApiError, type LocalidadeSalva } from "@/lib/api";
import { useQueryTendenciasRadar, useQueryRadarEvolucao, useQueryRadarLocalidadesSalvas, invalidarQueriesRadarLocalidades } from "@/lib/queries";
import { queryKeys } from "@/lib/query-keys";
import { usePremiumAtivo } from "@/lib/premium";
import { AdsSlot } from "@/components/AdsSlot";
import RadarLocalSimples from "@/components/RadarLocalSimples";
import type { Regiao } from "@/lib/regiao";
import { cn } from "@/lib/utils";
import { formatarDataSemAno } from "@/lib/datas";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { RefreshCw, MapPin, TrendingUp, BarChart3, BookmarkPlus, Bookmark, X, AlertCircle, Loader2, ExternalLink, Crown } from "lucide-react";

// Sem fallback sintético. A tela do Radar mostra o que o backend respondeu
// (run 20260925-1020-observabilidade, critérios 11 e 12):
//   - `tendenciasQuery` em erro  -> estado de erro explícito, sem lista;
//   - `evolucaoQuery` em erro 403 -> o gate Premium é REAL (o backend respondeu
//     403), e mesmo assim a prévia de 7 dias só existe se o backend a mandou.
// Antes havia `MOCK_T` (três "assuntos em alta" fixos) e `mockSerie()` com
// `Math.random()` a CADA render: o gráfico de evolução mudava de valor a cada
// re-render, sem nenhuma leitura do backend, e ainda era rotulado "Dados de
// exemplo" — ou seja, um número de notícias inventado e instável.
const CATS = ["", "politica", "economia", "tecnologia", "cidades", "esportes", "cultura", "geral"];

function locLabel(l: { pais?: string | null; estado?: string | null; cidade?: string | null }) { const p = [l.pais, l.estado, l.cidade].filter(Boolean).join(" · "); return p || "Recorte nacional"; }

export default function RadarClient() {
  const { token, usuario } = useAuth();
  const isPremium = usuario?.papel === "premium" || usuario?.papel === "admin";
  const { liberado } = usePremiumAtivo();
  const premiumGeral = isPremium || liberado;
  const [regiao, setRegiao] = useState<Regiao | null>(null);
  // Fonte única de local (FRENTE 5): tendências e evolução derivam da mesma região.
  const filtros = useMemo(() => ({
    pais: regiao?.pais || undefined,
    estado: regiao?.estado || undefined,
    cidade: regiao?.cidade || undefined,
  }), [regiao]);
  const [evoCat, setEvoCat] = useState("");
  const evoFiltros = useMemo(() => ({
    categoria: evoCat || undefined,
    pais: regiao?.pais || undefined,
    estado: regiao?.estado || undefined,
    cidade: regiao?.cidade || undefined,
  }), [evoCat, regiao]);
  const [msg, setMsg] = useState<string | null>(null);
  const [tab, setTab] = useState("tendencias");
  const [upsellOpen, setUpsellOpen] = useState(false);
  const queryClient = useQueryClient();
  const usuarioId = usuario?.id ?? 0;

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

  // Sem dado sintético: `data` é a única fonte. Erro é erro, e a tela abaixo
  // mostra o motivo real (status + código de correlação) em vez de um gráfico.
  const tend = tendenciasQuery.data ?? null;
  const loadingT = tendenciasQuery.isFetching;
  const evo = evolucaoQuery.data ?? null;
  const loadingE = Boolean(token) && evolucaoQuery.isFetching;
  const salvas = localidadesQuery.data ?? [];
  const erroTendencias = tendenciasQuery.isError ? tendenciasQuery.error : null;
  const erroEvolucao = evolucaoQuery.isError ? evolucaoQuery.error : null;

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

  return (
    <div className="mx-auto max-w-4xl space-y-4 py-6 px-4">
      <div className="hud-line" aria-hidden />
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div><h1 className="text-2xl font-bold text-[var(--cor-texto)] flex items-center gap-2"><TrendingUp className="h-6 w-6 text-[var(--cor-neon-ciano)]" />Radar de tendências</h1><p className="text-sm text-[var(--cor-texto-suave)] flex items-center gap-1 mt-1"><MapPin className="h-3.5 w-3.5" />{tend ? locLabel(tend.localidade) : locLabel(filtros)}</p></div>
        <Button variant="outline" size="sm" onClick={() => { void tendenciasQuery.refetch(); if (token) void evolucaoQuery.refetch(); void localidadesQuery.refetch(); }} className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]"><RefreshCw className="h-4 w-4" />Atualizar</Button>
      </div>

      {erroTendencias && (
        <Alert variant="destructive" className="border-[var(--cor-erro)]/40 bg-[var(--cor-erro-suave)]">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle className="text-sm">Não foi possível carregar as tendências</AlertTitle>
          <AlertDescription className="text-xs">
            {erroTendencias instanceof Error ? erroTendencias.message : "Falha inesperada."}
            {erroTendencias instanceof ApiError && erroTendencias.requestId
              ? ` Código de suporte: ${erroTendencias.requestId}.`
              : ""}
          </AlertDescription>
        </Alert>
      )}
      {tend?.aviso_metodologia && <Alert className="border-[var(--cor-neon-ciano)]/30 bg-[var(--cor-destaque-suave)]"><AlertCircle className="h-4 w-4 text-[var(--cor-neon-ciano)]" /><AlertTitle className="text-[var(--cor-texto)] text-sm">Metodologia</AlertTitle><AlertDescription className="text-[var(--cor-texto-suave)] text-xs">{tend.aviso_metodologia}</AlertDescription></Alert>}
      {msg && <Alert className="border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)]"><AlertDescription className="text-sm text-[var(--cor-texto)]">{msg}</AlertDescription></Alert>}

      <Card className="bento border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
        <CardHeader className="pb-3"><CardTitle className="text-base flex items-center gap-2"><MapPin className="h-4 w-4 text-[var(--cor-neon-ciano)]" />Local</CardTitle><CardDescription className="text-[var(--cor-texto-suave)]">Um recorte para tendências e evolução</CardDescription></CardHeader>
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
        <TabsList className="bg-[var(--cor-borda)]"><TabsTrigger value="tendencias" className="data-[state=active]:bg-[var(--cor-fundo-card)]"><TrendingUp className="h-4 w-4 mr-1" />Tendências</TabsTrigger><TabsTrigger value="evolucao" className="data-[state=active]:bg-[var(--cor-fundo-card)]"><BarChart3 className="h-4 w-4 mr-1" />Evolução</TabsTrigger></TabsList>

        <TabsContent value="tendencias">
          <Card className="bento border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
            <CardHeader className="pb-2"><CardTitle className="text-base">Assuntos em alta</CardTitle><CardDescription className="text-[var(--cor-texto-suave)]">{assuntos.length ? `${assuntos.length} categorias no recorte` : "Sem dados para este recorte"}</CardDescription></CardHeader>
            <CardContent>
              {loadingT ? <div className="grid gap-3">{Array.from({ length: 4 }).map((_, i) => <div key={i} className="h-16 animate-pulse rounded-[var(--raio-md)] bg-[var(--cor-borda)]" />)}</div> : erroTendencias ? <div role="alert" className="rounded-[var(--raio-md)] border border-dashed border-[var(--cor-erro)] p-8 text-center"><p className="text-sm font-medium text-[var(--cor-texto)]">Tendências indisponíveis</p><p className="text-xs text-[var(--cor-texto-suave)] mt-1">Não mostramos assuntos em alta de exemplo. Tente recarregar a página.</p></div> : assuntos.length === 0 ? <div className="rounded-[var(--raio-md)] border border-dashed border-[var(--cor-borda)] p-8 text-center"><p className="text-sm text-[var(--cor-texto-suave)]">Nenhum assunto em alta para este recorte.</p><p className="text-xs text-[var(--cor-texto-suave)] mt-1">Tente limpar filtros ou escolher outro recorte.</p></div> : <div className="grid gap-3">{assuntos.map((a, i) => {
                const href = a.cluster_id ? `/noticia/cluster/${a.cluster_id}` : a.item_id ? `/noticia/item/${a.item_id}` : `/noticia/${a.item_id ?? a.cluster_id ?? ""}`;
                const hasLink = !!(a.cluster_id || a.item_id);
                return (
                  <div key={`${a.categoria}-${i}`} className={cn("flex items-center justify-between rounded-[var(--raio-md)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-3 glass")}>
                    <div className="min-w-0"><p className="font-medium capitalize text-[var(--cor-texto)] truncate">{a.categoria}</p><p className="text-xs text-[var(--cor-texto-suave)]">{a.numero_noticias} notícias · {a.numero_fontes} fontes{(a.crescimento_24h ?? 0) > 0 ? ` · +${Math.round((a.crescimento_24h ?? 0) * 100)}% em 24h` : ""}{(a.buscas_relacionadas ?? 0) > 0 ? ` · ${a.buscas_relacionadas} buscas` : ""}</p></div>
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
                   <div className="flex items-center gap-2">{!premiumGeral && evo && <Badge variant="outline" className="border-[var(--cor-premium)] text-[var(--cor-premium)]"><Crown className="mr-1 h-3 w-3" /> 7 dias no Free</Badge>}</div>
                  {evoExibido?.aviso_metodologia && <p className="text-xs text-[var(--cor-texto-suave)] border-l-2 border-[var(--cor-neon-ciano)] pl-2">{evoExibido.aviso_metodologia}</p>}
                  {loadingE ? <div className="h-40 animate-pulse rounded-[var(--raio-md)] bg-[var(--cor-borda)]" /> : erroEvolucao ? <div role="alert" className="rounded-[var(--raio-md)] border border-dashed border-[var(--cor-erro)] p-8 text-center"><p className="text-sm font-medium text-[var(--cor-texto)]">Evolução indisponível</p><p className="mt-1 text-xs text-[var(--cor-texto-suave)]">{erroEvolucao instanceof Error ? erroEvolucao.message : "Falha inesperada."}</p>{erroEvolucao instanceof ApiError && erroEvolucao.requestId ? <p className="mt-1 text-xs text-[var(--cor-texto-suave)]">Código de suporte: {erroEvolucao.requestId}</p> : null}<p className="mt-1 text-xs text-[var(--cor-texto-suave)]">Não exibimos uma série de exemplo: gráfico inventado seria indistinguível de dado real.</p></div> : !evoExibido || evoExibido.serie.length === 0 ? <div className="rounded-[var(--raio-md)] border border-dashed border-[var(--cor-borda)] p-8 text-center text-sm text-[var(--cor-texto-suave)]">Sem dados para esta categoria/recorte.</div> : (
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
