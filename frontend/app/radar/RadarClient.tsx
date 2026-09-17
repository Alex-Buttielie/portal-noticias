"use client";
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { obterTendenciasRadar, obterEvolucaoRadar, obterLocalidadesSalvas, salvarLocalidade, removerLocalidade, type RadarTendencias, type RadarEvolucao, type LocalidadeSalva } from "@/lib/api";
import { usePremiumAtivo } from "@/lib/premium";
import { AdsSlot } from "@/components/AdsSlot";
import { cn } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { RefreshCw, MapPin, TrendingUp, BarChart3, BookmarkPlus, Bookmark, X, AlertCircle, Loader2, ExternalLink, Crown } from "lucide-react";

const MOCK_T: RadarTendencias = { aviso_metodologia: "Dados de exemplo", localidade: { pais: null, estado: null, cidade: null }, assuntos_em_alta: [{ categoria: "politica", numero_noticias: 12, numero_fontes: 4, cluster_id: 1, item_id: null }, { categoria: "tecnologia", numero_noticias: 8, numero_fontes: 3, cluster_id: null, item_id: 2 }, { categoria: "economia", numero_noticias: 5, numero_fontes: 2, cluster_id: 3, item_id: null }] };
function mockSerie(): RadarEvolucao { const hoje = new Date(); const serie = Array.from({ length: 7 }, (_, i) => { const d = new Date(hoje); d.setDate(hoje.getDate() - (6 - i)); return { dia: d.toISOString().slice(0, 10), numero_noticias: Math.floor(2 + Math.random() * 8) }; }); return { aviso_metodologia: "Dados de exemplo", categoria: null, serie }; }
const CATS = ["", "politica", "economia", "tecnologia", "cidades", "esportes", "cultura", "geral"];

function fmtDia(s: string) { try { const d = new Date(s); return `${String(d.getDate()).padStart(2, "0")}/${String(d.getMonth() + 1).padStart(2, "0")}`; } catch { return s.slice(5); } }

function locLabel(l: { pais?: string | null; estado?: string | null; cidade?: string | null }) { const p = [l.pais, l.estado, l.cidade].filter(Boolean).join(" · "); return p || "Recorte nacional"; }

export default function RadarClient() {
  const { token, usuario } = useAuth();
  const isPremium = usuario?.papel === "premium" || usuario?.papel === "admin";
  const { liberado } = usePremiumAtivo();
  const premiumGeral = isPremium || liberado;
  const [draftPais, setDraftPais] = useState("");
  const [draftEstado, setDraftEstado] = useState("");
  const [draftCidade, setDraftCidade] = useState("");
  const [filtros, setFiltros] = useState<{ pais?: string; estado?: string; cidade?: string }>({});
  const [tend, setTend] = useState<RadarTendencias | null>(null);
  const [loadingT, setLoadingT] = useState(true);
  const [evoCat, setEvoCat] = useState("");
  const [evoPais, setEvoPais] = useState("");
  const [evoEstado, setEvoEstado] = useState("");
  const [evoCidade, setEvoCidade] = useState("");
  const [evoFiltros, setEvoFiltros] = useState<{ categoria?: string; pais?: string; estado?: string; cidade?: string }>({});
  const [evo, setEvo] = useState<RadarEvolucao | null>(null);
  const [loadingE, setLoadingE] = useState(false);
  const [salvas, setSalvas] = useState<LocalidadeSalva[]>([]);
  const [msg, setMsg] = useState<string | null>(null);
  const [tab, setTab] = useState("tendencias");
  const [upsellOpen, setUpsellOpen] = useState(false);

  const fetchTend = useCallback(async (f = filtros) => {
    setLoadingT(true);
    try {
      const d = await obterTendenciasRadar({ pais: f.pais || undefined, estado: f.estado || undefined, cidade: f.cidade || undefined });
      setTend(d);
    } catch { setTend({ ...MOCK_T, localidade: { pais: f.pais || null, estado: f.estado || null, cidade: f.cidade || null } }); }
    setLoadingT(false);
  }, [filtros]);

  const fetchEvo = useCallback(async (ef = evoFiltros) => {
    if (!token) { setEvo(null); return; }
    setLoadingE(true);
    try {
      const d = await obterEvolucaoRadar(token, { categoria: ef.categoria || undefined, pais: ef.pais || undefined, estado: ef.estado || undefined, cidade: ef.cidade || undefined });
      setEvo(d);
    } catch (e: unknown) {
      const err = e as { status?: number };
      if (err?.status === 403) setEvo({ aviso_metodologia: "Prévia de 7 dias — seja Premium para ver a série completa, sem limites.", categoria: ef.categoria || null, serie: mockSerie().serie });
      else setEvo({ ...mockSerie(), categoria: ef.categoria || null });
    }
    setLoadingE(false);
  }, [evoFiltros, token]);

  const fetchSalvas = useCallback(async () => {
    if (!token) { setSalvas([]); return; }
    try { setSalvas(await obterLocalidadesSalvas(token)); } catch { setSalvas([]); }
  }, [token]);

  useEffect(() => { fetchTend(filtros); }, [filtros, fetchTend]);
  useEffect(() => { fetchEvo(evoFiltros); }, [evoFiltros, fetchEvo]);
  useEffect(() => { fetchSalvas(); }, [fetchSalvas]);
  useEffect(() => {
    const id = setInterval(() => fetchTend(filtros), 60000);
    return () => clearInterval(id);
  }, [fetchTend, filtros]);

  function aplicar() {
    const f = { pais: draftPais.trim() || undefined, estado: draftEstado.trim() || undefined, cidade: draftCidade.trim() || undefined };
    const clean: Record<string, string> = {};
    if (f.pais) clean.pais = f.pais;
    if (f.estado) clean.estado = f.estado;
    if (f.cidade) clean.cidade = f.cidade;
    setFiltros(clean);
  }
  function limpar() { setDraftPais(""); setDraftEstado(""); setDraftCidade(""); setFiltros({}); }
  function aplicarEvo() {
    setEvoFiltros({ categoria: evoCat || undefined, pais: evoPais.trim() || undefined, estado: evoEstado.trim() || undefined, cidade: evoCidade.trim() || undefined });
  }
  async function handleSalvar() {
    if (!token) { setMsg("Faça login para salvar localidades."); setTimeout(() => setMsg(null), 3000); return; }
    const p = draftPais.trim() || filtros.pais || ""; const e = draftEstado.trim() || filtros.estado || ""; const c = draftCidade.trim() || filtros.cidade || "";
    if (!p && !e && !c) { setMsg("Informe ao menos país, estado ou cidade."); setTimeout(() => setMsg(null), 3000); return; }
    try { await salvarLocalidade(token, { pais: p || undefined, estado: e || undefined, cidade: c || undefined }); setMsg("Localidade salva."); await fetchSalvas(); } catch (err: unknown) { setMsg((err as Error)?.message || "Erro ao salvar."); }
    setTimeout(() => setMsg(null), 3000);
  }
  async function handleRemover(l: LocalidadeSalva) {
    if (!token) return;
    try { await removerLocalidade(token, { pais: l.pais || undefined, estado: l.estado || undefined, cidade: l.cidade || undefined }); setSalvas((s) => s.filter((x) => !(x.pais === l.pais && x.estado === l.estado && x.cidade === l.cidade))); } catch {}
  }
  function usarSalva(l: LocalidadeSalva) { setDraftPais(l.pais || ""); setDraftEstado(l.estado || ""); setDraftCidade(l.cidade || ""); setFiltros({ pais: l.pais || undefined, estado: l.estado || undefined, cidade: l.cidade || undefined }); setEvoPais(l.pais || ""); setEvoEstado(l.estado || ""); setEvoCidade(l.cidade || ""); }

  const assuntos = tend?.assuntos_em_alta ?? [];
  const evoExibido = evo && !premiumGeral ? { ...evo, serie: evo.serie.slice(-7) } : evo;
  const maxEvo = evoExibido ? Math.max(...evoExibido.serie.map((s) => s.numero_noticias), 1) : 1;

  return (
    <div className="mx-auto max-w-4xl space-y-4 py-6 px-4">
      <div className="hud-line" aria-hidden />
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div><h1 className="text-2xl font-bold text-[var(--cor-texto)] flex items-center gap-2"><TrendingUp className="h-6 w-6 text-[var(--cor-neon-ciano)]" />Radar de tendências</h1><p className="text-sm text-[var(--cor-texto-suave)] flex items-center gap-1 mt-1"><MapPin className="h-3.5 w-3.5" />{tend ? locLabel(tend.localidade) : locLabel(filtros)}</p></div>
        <Button variant="outline" size="sm" onClick={() => { fetchTend(filtros); if (token) fetchEvo(evoFiltros); fetchSalvas(); }} className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]"><RefreshCw className="h-4 w-4" />Atualizar</Button>
      </div>

      {tend?.aviso_metodologia && <Alert className="border-[var(--cor-neon-ciano)]/30 bg-[var(--cor-destaque-suave)]"><AlertCircle className="h-4 w-4 text-[var(--cor-neon-ciano)]" /><AlertTitle className="text-[var(--cor-texto)] text-sm">Metodologia</AlertTitle><AlertDescription className="text-[var(--cor-texto-suave)] text-xs">{tend.aviso_metodologia}</AlertDescription></Alert>}
      {msg && <Alert className="border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)]"><AlertDescription className="text-sm text-[var(--cor-texto)]">{msg}</AlertDescription></Alert>}

      <Card className="bento border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
        <CardHeader className="pb-3"><CardTitle className="text-base flex items-center gap-2"><MapPin className="h-4 w-4 text-[var(--cor-neon-ciano)]" />Filtros de localidade</CardTitle><CardDescription className="text-[var(--cor-texto-suave)]">Aplique um recorte para tendências e evolução</CardDescription></CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div className="space-y-1"><Label htmlFor="pais">País</Label><Input id="pais" placeholder="Brasil" value={draftPais} onChange={(e) => setDraftPais(e.target.value)} className="bg-[var(--cor-fundo-card)] border-[var(--cor-borda)]" /></div>
            <div className="space-y-1"><Label htmlFor="estado">Estado</Label><Input id="estado" placeholder="SP" value={draftEstado} onChange={(e) => setDraftEstado(e.target.value)} className="bg-[var(--cor-fundo-card)] border-[var(--cor-borda)]" /></div>
            <div className="space-y-1"><Label htmlFor="cidade">Cidade</Label><Input id="cidade" placeholder="São Paulo" value={draftCidade} onChange={(e) => setDraftCidade(e.target.value)} className="bg-[var(--cor-fundo-card)] border-[var(--cor-borda)]" /></div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button onClick={aplicar} className="bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)] min-h-[44px]">Aplicar</Button>
            <Button variant="outline" onClick={limpar} className="border-[var(--cor-borda)] min-h-[44px]">Limpar</Button>
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
              {loadingT ? <div className="grid gap-3">{Array.from({ length: 4 }).map((_, i) => <div key={i} className="h-16 animate-pulse rounded-[var(--raio-md)] bg-[var(--cor-borda)]" />)}</div> : assuntos.length === 0 ? <div className="rounded-[var(--raio-md)] border border-dashed border-[var(--cor-borda)] p-8 text-center"><p className="text-sm text-[var(--cor-texto-suave)]">Nenhum assunto em alta para este recorte.</p><p className="text-xs text-[var(--cor-texto-suave)] mt-1">Tente limpar filtros ou escolher outro recorte.</p></div> : <div className="grid gap-3">{assuntos.map((a, i) => {
                const href = a.cluster_id ? `/noticia/cluster/${a.cluster_id}` : a.item_id ? `/noticia/item/${a.item_id}` : `/noticia/${a.item_id ?? a.cluster_id ?? ""}`;
                const hasLink = !!(a.cluster_id || a.item_id);
                return (
                  <div key={`${a.categoria}-${i}`} className={cn("flex items-center justify-between rounded-[var(--raio-md)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-3 glass")}>
                    <div className="min-w-0"><p className="font-medium capitalize text-[var(--cor-texto)] truncate">{a.categoria}</p><p className="text-xs text-[var(--cor-texto-suave)]">{a.numero_noticias} notícias · {a.numero_fontes} fontes</p></div>
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
                  <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
                    <div className="space-y-1">
                      <Label>Categoria</Label>
                      <Select value={evoCat} onValueChange={setEvoCat}>
                        <SelectTrigger className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]"><SelectValue placeholder="Todas" /></SelectTrigger>
                        <SelectContent>{CATS.map((c) => <SelectItem key={c} value={c}>{c || "Todas"}</SelectItem>)}</SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-1"><Label>País</Label><Input placeholder="Brasil" value={evoPais} onChange={(e) => setEvoPais(e.target.value)} className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]" /></div>
                    <div className="space-y-1"><Label>Estado</Label><Input placeholder="SP" value={evoEstado} onChange={(e) => setEvoEstado(e.target.value)} className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]" /></div>
                    <div className="space-y-1"><Label>Cidade</Label><Input placeholder="São Paulo" value={evoCidade} onChange={(e) => setEvoCidade(e.target.value)} className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]" /></div>
                  </div>
                   <div className="flex items-center gap-2"><Button onClick={aplicarEvo} size="sm" className="bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)] min-h-[44px]">Aplicar</Button>{!premiumGeral && evo && <Badge variant="outline" className="border-[var(--cor-premium)] text-[var(--cor-premium)]"><Crown className="mr-1 h-3 w-3" /> 7 dias no Free</Badge>}</div>
                  {evoExibido?.aviso_metodologia && <p className="text-xs text-[var(--cor-texto-suave)] border-l-2 border-[var(--cor-neon-ciano)] pl-2">{evoExibido.aviso_metodologia}</p>}
                  {loadingE ? <div className="h-40 animate-pulse rounded-[var(--raio-md)] bg-[var(--cor-borda)]" /> : !evoExibido || evoExibido.serie.length === 0 ? <div className="rounded-[var(--raio-md)] border border-dashed border-[var(--cor-borda)] p-8 text-center text-sm text-[var(--cor-texto-suave)]">Sem dados para esta categoria/recorte.</div> : (
                    <>
                      <div className="rounded-[var(--raio-md)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-3">
                        <div className="flex items-end gap-1 h-40">
                          {evoExibido.serie.map((p) => (
                            <div key={p.dia} className="flex flex-1 flex-col items-center justify-end gap-1">
                              <span className="text-[10px] font-medium text-[var(--cor-texto)]">{p.numero_noticias}</span>
                              <div className="w-full rounded-t-[var(--raio-sm)] bg-[var(--cor-neon-ciano)] transition-all" style={{ height: `${Math.max(4, (p.numero_noticias / maxEvo) * 100)}%`, minHeight: 4 }} aria-label={`${p.dia}: ${p.numero_noticias}`} />
                              <span className="text-[10px] text-[var(--cor-texto-suave)]">{fmtDia(p.dia)}</span>
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
