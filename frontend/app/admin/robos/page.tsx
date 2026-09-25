"use client";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Switch } from "@/components/ui/switch";
import { Separator } from "@/components/ui/separator";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import { useAuth } from "@/lib/auth-context";
import {
  useQueryAdminFontes,
  useQueryAdminRoboConfig,
  useQueryAdminRoboExecucoes,
} from "@/lib/queries";
import { queryKeys } from "@/lib/query-keys";
import * as api from "@/lib/api";
import { formatarDataHoraCompleta, formatarHoraComSegundos } from "@/lib/datas";
import { Bot, Play, Settings, History, AlertTriangle, CheckCircle2, XCircle, Activity, Clock, DollarSign, Database, Search, Trash2, Pencil, Plus, RefreshCw, ExternalLink, Power, Timer, Layers, Cpu, SlidersHorizontal, Shield } from "lucide-react";

type Fonte = api.FonteRobo;
type Cfg = api.ConfigRobo;
type Exec = api.ExecucaoRobo;

/**
 * Sem `FONTES_MOCK`.
 *
 * As duas fontes de exemplo ("G1" e "UOL" com `id` 1 e 2) apareciam na tela
 * quando a API falhava, e os botões de remover/editar seguiam ativos: they'd
 * emitir `DELETE /api/admin/robos/fontes/1/`, que é a fonte REAL de id 1. Num
 * robô de ingestão, desativar ou apagar a fonte errada significa parar de
 * coletar de um veículo real sem que ninguém tenha decidido isso. Estado
 * explícito de "API indisponível" é o único desfecho aceitável.
 */
function rel(iso: string) {
  const d = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (d < 60) return `há ${d}s`;
  if (d < 3600) return `há ${Math.floor(d / 60)} min`;
  if (d < 86400) return `há ${Math.floor(d / 3600)} h`;
  return `há ${Math.floor(d / 86400)} dias`;
}
function isUrl(v: string) {
  try { const u = new URL(v); return u.protocol === "http:" || u.protocol === "https:"; } catch { return false; }
}
function fmtUSD(v: number | null | undefined) {
  if (v == null) return "—";
  return `$ ${Number(v).toFixed(4)}`;
}

export default function Page() {
  const { token, usuario } = useAuth();
  const tk = token || "";
  const usuarioId = usuario?.id ?? 0;
  const queryClient = useQueryClient();
  const [tab, setTab] = useState("visao");
  const [err, setErr] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);

  const [fontes, setFontes] = useState<Fonte[]>([]);
  const [busca, setBusca] = useState("");
  const [filtroAtivo, setFiltroAtivo] = useState<"todos" | "ativo" | "inativo">("todos");
  const [nome, setNome] = useState("");
  const [url, setUrl] = useState("");
  const [cat, setCat] = useState("");
  const [ativo, setAtivo] = useState(true);
  const [editId, setEditId] = useState<number | null>(null);
  const [editNome, setEditNome] = useState("");
  const [editUrl, setEditUrl] = useState("");
  const [editCat, setEditCat] = useState("");
  const [editAtivo, setEditAtivo] = useState(true);
  const [confirmRemove, setConfirmRemove] = useState<number | null>(null);

  const [cfg, setCfg] = useState<Cfg | null>(null);
  const [cfgOrig, setCfgOrig] = useState<Cfg | null>(null);
  const [savingC, setSavingC] = useState(false);

  const [execs, setExecs] = useState<Exec[]>([]);
  const [execLoading, setExecLoading] = useState(false);
  const [confirmExec, setConfirmExec] = useState(false);
  const [execLog, setExecLog] = useState<string[]>([]);
  const [execPage, setExecPage] = useState(1);
  const [expandErr, setExpandErr] = useState<number | null>(null);
  const perPage = 10;

  // --- Migração TanStack Query: fontes, config e execuções do robô
// (staleTime 0 — telas de decisão). O fallback mock de fontes em erro é
// preservado; o estado local permite updates otimistas nas mutations.
const fontesQuery = useQueryAdminFontes({ token: tk || null, usuarioId });
const cfgQuery = useQueryAdminRoboConfig({ token: tk || null, usuarioId });
const execsQuery = useQueryAdminRoboExecucoes({ token: tk || null, usuarioId });

const loadingF = fontesQuery.isLoading;
const loadingC = cfgQuery.isLoading;
const loadingE = execsQuery.isLoading;

// Sincroniza dados da query ao estado local. Em erro a lista de fontes é
// ESVAZIADA (antes recebia o fallback fictício): uma lista vazia com a tela
// avisando "API indisponível" impede que um `id` de exemplo vire um
// DELETE/PATCH numa fonte real.
useEffect(() => {
  if (fontesQuery.isError) {
    setFontes([]);
    return;
  }
  if (fontesQuery.data) {
    setFontes(fontesQuery.data);
    if (fontesQuery.data.length === 0) setOk("Nenhuma fonte cadastrada — crie a primeira abaixo.");
  }
  if (cfgQuery.data) { setCfg(cfgQuery.data); setCfgOrig(cfgQuery.data); }
  if (execsQuery.data) setExecs(execsQuery.data);
}, [fontesQuery.data, fontesQuery.isError, cfgQuery.data, execsQuery.data]);

const recarregar = useCallback(async () => {
  await Promise.all([
    queryClient.invalidateQueries({ queryKey: queryKeys.admin.fontes() }),
    queryClient.invalidateQueries({ queryKey: queryKeys.admin.roboConfig() }),
    queryClient.invalidateQueries({ queryKey: queryKeys.admin.roboExecucoes() }),
  ]);
}, [queryClient]);

// Wrappers de invalidação com os nomes originais — mutations e botões de
// recarregar continuam chamando as mesmas funções; a query refetch sozinha.
const carregarFontes = useCallback(async () => {
  await queryClient.invalidateQueries({ queryKey: queryKeys.admin.fontes() });
}, [queryClient]);
const carregarCfg = useCallback(async () => {
  await queryClient.invalidateQueries({ queryKey: queryKeys.admin.roboConfig() });
}, [queryClient]);
const carregarExecs = useCallback(async () => {
  await queryClient.invalidateQueries({ queryKey: queryKeys.admin.roboExecucoes() });
}, [queryClient]);

// Erro de carregamento das queries (mutação usa o estado local `err`).
const erroCarregamento = fontesQuery.isError
  ? (fontesQuery.error?.message || "Falha ao listar fontes")
  : cfgQuery.isError
    ? (cfgQuery.error?.message || "Falha ao carregar configuração")
    : execsQuery.isError
      ? (execsQuery.error?.message || "Falha ao listar execuções")
      : null;

  const fontesFiltradas = useMemo(() => {
    return fontes.filter((f) => {
      if (filtroAtivo === "ativo" && !f.ativo) return false;
      if (filtroAtivo === "inativo" && f.ativo) return false;
      if (busca.trim()) {
        const b = busca.toLowerCase();
        if (!f.nome.toLowerCase().includes(b) && !f.url.toLowerCase().includes(b) && !(f.categoria_padrao || "").toLowerCase().includes(b)) return false;
      }
      return true;
    });
  }, [fontes, busca, filtroAtivo]);

  const healthPorFonte = useMemo(() => {
    const last = execs[0];
    if (!last?.erros_por_fonte) return {};
    return last.erros_por_fonte as Record<string, string>;
  }, [execs]);

  const custoHoje = useMemo(() => {
    const hoje = new Date().toISOString().slice(0, 10);
    return execs.filter((e) => e.executado_em.slice(0, 10) === hoje).reduce((a, e) => a + (e.custo_estimado_summarization_usd || 0), 0);
  }, [execs]);

  const custoAcumulado = useMemo(() => execs.reduce((a, e) => a + (e.custo_estimado_summarization_usd || 0), 0), [execs]);
  const totalItensHoje = useMemo(() => {
    const hoje = new Date().toISOString().slice(0, 10);
    return execs.filter((e) => e.executado_em.slice(0, 10) === hoje).reduce((a, e) => a + e.total_itens_ingeridos, 0);
  }, [execs]);

  const dirty = useMemo(() => JSON.stringify(cfg) !== JSON.stringify(cfgOrig), [cfg, cfgOrig]);
  const cfgInvalido = useMemo(() => {
    if (!cfg) return "carregando";
    if (cfg.intervalo_minutos < 1 || cfg.intervalo_minutos > 1440) return "Intervalo deve ser entre 1 e 1440 min";
    if (cfg.dedup_limiar_similaridade < 0 || cfg.dedup_limiar_similaridade > 1) return "Limiar similaridade 0–1";
    if (cfg.resumo_similaridade_maxima < 0 || cfg.resumo_similaridade_maxima > 1) return "Resumo similaridade 0–1";
    if (cfg.resumo_trecho_copiado_maximo < 0 || cfg.resumo_trecho_copiado_maximo > 1) return "Trecho copiado 0–1";
    return null;
  }, [cfg]);

  const setCfgField = <K extends keyof Cfg>(k: K, v: Cfg[K]) => setCfg((p) => p ? { ...p, [k]: v } : p);

  const criarFonte = async () => {
    setErr(null); setOk(null);
    if (!nome.trim() || !url.trim()) { setErr("Nome e URL são obrigatórios."); return; }
    if (!isUrl(url.trim())) { setErr("URL inválida — use https://exemplo.com/rss"); return; }
    try {
      await api.robosCriarFonte(tk, { nome: nome.trim(), url: url.trim(), ativo, categoria_padrao: cat.trim() });
      setNome(""); setUrl(""); setCat(""); setAtivo(true); setOk("Fonte criada.");
      await carregarFontes();
    } catch (e: unknown) { setErr(e instanceof Error ? e.message : "Falha ao criar fonte."); }
  };
  const iniciarEdicao = (f: Fonte) => { setEditId(f.id); setEditNome(f.nome); setEditUrl(f.url); setEditCat(f.categoria_padrao || ""); setEditAtivo(f.ativo); };
  const salvarEdicao = async () => {
    if (editId == null) return;
    if (!editNome.trim() || !editUrl.trim()) { setErr("Nome e URL obrigatórios."); return; }
    if (!isUrl(editUrl.trim())) { setErr("URL inválida."); return; }
    setErr(null);
    try {
      await api.robosAtualizarFonte(tk, editId, { nome: editNome.trim(), url: editUrl.trim(), categoria_padrao: editCat.trim(), ativo: editAtivo });
      setEditId(null); setOk("Fonte atualizada."); await carregarFontes();
    } catch (e: unknown) { setErr(e instanceof Error ? e.message : "Falha ao atualizar."); }
  };
  const toggleAtivo = async (f: Fonte) => {
    const prev = [...fontes];
    setFontes((p) => p.map((x) => x.id === f.id ? { ...x, ativo: !x.ativo } : x));
    try { await api.robosAtualizarFonte(tk, f.id, { ativo: !f.ativo }); setOk(`${f.nome} ${!f.ativo ? "ativado" : "desativado"}.`); await carregarFontes(); }
    catch (e: unknown) { setFontes(prev); setErr(e instanceof Error ? e.message : "Falha ao alternar."); }
  };
  const removerFonte = async () => {
    if (confirmRemove == null) return;
    try { await api.robosRemoverFonte(tk, confirmRemove); setOk("Fonte removida."); setConfirmRemove(null); await carregarFontes(); }
    catch (e: unknown) { setErr(e instanceof Error ? e.message : "Falha ao remover."); }
  };
  const salvarCfg = async () => {
    if (!cfg || cfgInvalido) return;
    setSavingC(true); setErr(null); setOk(null);
    try {
      const r = await api.robosSalvarConfig(tk, {
        intervalo_minutos: cfg.intervalo_minutos, ativo: cfg.ativo, categorias_sensiveis: cfg.categorias_sensiveis,
        limiar_fontes_alta_relevancia: cfg.limiar_fontes_alta_relevancia,
        dedup_limiar_similaridade: cfg.dedup_limiar_similaridade, dedup_janela_horas: cfg.dedup_janela_horas, dedup_max_itens: cfg.dedup_max_itens,
        resumo_similaridade_maxima: cfg.resumo_similaridade_maxima, resumo_trecho_copiado_maximo: cfg.resumo_trecho_copiado_maximo, dedup_cluster_sempre_exige_revisao: cfg.dedup_cluster_sempre_exige_revisao,
        llm_model: cfg.llm_model, llm_api_base_url: cfg.llm_api_base_url, llm_tamanho_lote: cfg.llm_tamanho_lote, llm_max_tokens_por_item: cfg.llm_max_tokens_por_item,
        llm_teto_gasto_diario_usd: cfg.llm_teto_gasto_diario_usd, llm_preco_por_1k_tokens: cfg.llm_preco_por_1k_tokens, llm_timeout_segundos: cfg.llm_timeout_segundos,
      });
      setCfg(r); setCfgOrig(r); setOk("Configuração salva.");
    } catch (e: unknown) { setErr(e instanceof Error ? e.message : "Falha ao salvar configuração."); }
    finally { setSavingC(false); }
  };
  const executar = async () => {
    setConfirmExec(false); setExecLoading(true); setErr(null); setOk(null);
    setExecLog((p) => [...p, `[${formatarHoraComSegundos(new Date())}] Disparando ingestão...`]);
    try {
      // O endpoint responde 202 imediatamente e roda a ingestão em
      // background (robos_views.py): o resultado aparece na lista de
      // execuções ao recarregar — não vem mais no corpo da resposta.
      const r = await api.robosExecutar(tk);
      const detalhe = (r as { detail?: string })?.detail ?? "Ingestão iniciada em background.";
      setExecLog((p) => [...p, `[${formatarHoraComSegundos(new Date())}] ${detalhe} Acompanhe na lista de execuções abaixo.`]);
      setOk(`${detalhe} Recarregue a lista de execuções em alguns minutos para ver o resultado.`);
      setTimeout(() => { carregarExecs(); }, 5000);
    } catch (e: unknown) {
      const m = e instanceof Error ? e.message : "Falha ao executar robôs.";
      setErr(m); setExecLog((p) => [...p, `[${formatarHoraComSegundos(new Date())}] ERRO: ${m}`]);
    } finally { setExecLoading(false); }
  };

  const execsPag = useMemo(() => {
    const s = (execPage - 1) * perPage;
    return execs.slice(s, s + perPage);
  }, [execs, execPage]);
  const totalPag = Math.max(1, Math.ceil(execs.length / perPage));

  return (
    <div className="space-y-4">
      <Card className="bento border-[var(--cor-borda)]">
        <CardHeader className="pb-3">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="flex gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-[var(--raio-md)] bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]"><Bot className="h-5 w-5" /></div>
              <div>
                <CardTitle className="flex items-center gap-2 text-[var(--cor-texto)]">Robôs — coleta automática <Badge variant="outline" className="border-[var(--cor-borda)] text-xs">{cfg ? (cfg.ativo ? "ativos" : "pausados") : "—"}</Badge></CardTitle>
                <CardDescription className="text-[var(--cor-texto-suave)]">Coleta automática, agrupamento e resumos. Acompanhe fontes, custos e execuções.</CardDescription>
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button onClick={() => setConfirmExec(true)} disabled={execLoading || !tk} className="min-h-[44px] bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]"><Play className="mr-2 h-4 w-4" />{execLoading ? "Executando..." : "Executar agora"}</Button>
              <Button variant="outline" onClick={recarregar} className="min-h-[44px] border-[var(--cor-borda)]"><RefreshCw className="mr-2 h-4 w-4" />Recarregar</Button>
            </div>
          </div>
          {!tk && <Badge variant="outline" className="border-[var(--cor-erro)] text-[var(--cor-erro)]">Faça login como admin</Badge>}
          {(err || erroCarregamento) && <div className="flex items-start gap-2 rounded-md border border-[var(--cor-erro)] bg-[var(--cor-erro-suave)] px-3 py-2 text-sm text-[var(--cor-erro)]"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" /><span className="flex-1">{err || erroCarregamento}</span><Button size="sm" variant="ghost" onClick={recarregar}>Tentar novamente</Button></div>}
          {ok && <div className="flex items-center gap-2 rounded-md border border-[var(--cor-sucesso)] bg-[var(--cor-sucesso-suave)] px-3 py-2 text-sm text-[var(--cor-sucesso)]"><CheckCircle2 className="h-4 w-4" />{ok}</div>}
        </CardHeader>
        <CardContent className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <div className="rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-3">
            <p className="flex items-center gap-1 text-xs tracking-widest text-[var(--cor-texto-suave)]"><Power className="h-3 w-3" />STATUS</p>
            <p className="mt-1 flex items-center gap-2 text-sm font-medium text-[var(--cor-texto)]">{cfg ? (cfg.ativo ? <><CheckCircle2 className="h-4 w-4 text-[var(--cor-sucesso)]" />Ativos</> : <><XCircle className="h-4 w-4 text-[var(--cor-erro)]" />Pausados</>) : "—"}<span className="text-xs font-normal text-[var(--cor-texto-suave)]">· a cada {cfg?.intervalo_minutos ?? "—"} min</span></p>
            <p className="text-xs text-[var(--cor-texto-suave)]">{fontes.filter((f) => f.ativo).length} ativas / {fontes.length} total</p>
          </div>
          <div className="rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-3">
            <p className="flex items-center gap-1 text-xs tracking-widest text-[var(--cor-texto-suave)]"><Clock className="h-3 w-3" />ÚLTIMA EXECUÇÃO</p>
            <p className="mt-1 text-sm font-medium text-[var(--cor-texto)]">{execs[0] ? formatarDataHoraCompleta(execs[0].executado_em) : "Nenhuma ainda"}</p>
            <p className="text-xs text-[var(--cor-texto-suave)]">{execs[0] ? rel(execs[0].executado_em) : "—"} · {execs[0] ? `${execs[0].total_itens_ingeridos} itens` : ""}</p>
          </div>
          <div className="rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-3">
            <p className="flex items-center gap-1 text-xs tracking-widest text-[var(--cor-texto-suave)]"><DollarSign className="h-3 w-3" />CUSTO HOJE</p>
            <p className="mt-1 text-sm font-medium text-[var(--cor-texto)]">{fmtUSD(custoHoje)} <span className="text-xs font-normal text-[var(--cor-texto-suave)]">/ acumulado {fmtUSD(custoAcumulado)}</span></p>
            <p className="text-xs text-[var(--cor-texto-suave)]">{totalItensHoje} itens hoje · {execs[0]?.chamadas_summarization_provider ?? "—"} chamadas LLM última</p>
          </div>
          <div className="rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-3">
            <p className="flex items-center gap-1 text-xs tracking-widest text-[var(--cor-texto-suave)]"><Activity className="h-3 w-3" />HEALTH POR FONTE</p>
            {Object.keys(healthPorFonte).length === 0 ? <p className="mt-1 flex items-center gap-1 text-xs text-[var(--cor-sucesso)]"><CheckCircle2 className="h-3 w-3" />Todas OK na última execução</p> : <div className="mt-1 space-y-1">{Object.entries(healthPorFonte).slice(0, 3).map(([k, v]) => <p key={k} className="flex items-center gap-1 truncate text-xs text-[var(--cor-erro)]"><AlertTriangle className="h-3 w-3 shrink-0" />{k}: {String(v).slice(0, 60)}</p>)} {Object.keys(healthPorFonte).length > 3 && <p className="text-xs text-[var(--cor-texto-suave)]">+{Object.keys(healthPorFonte).length - 3} erros</p>}</div>}
          </div>
        </CardContent>
      </Card>

      <Tabs value={tab} onValueChange={setTab} className="w-full">
        <TabsList className="flex w-full flex-wrap justify-start gap-1 bg-[var(--cor-fundo-elevado)] p-1">
          <TabsTrigger value="visao" className="gap-1"><Layers className="h-3.5 w-3.5" />Visão geral</TabsTrigger>
          <TabsTrigger value="fontes" className="gap-1"><Database className="h-3.5 w-3.5" />Fontes ({fontes.length})</TabsTrigger>
          <TabsTrigger value="config" className="gap-1"><Settings className="h-3.5 w-3.5" />Configuração</TabsTrigger>
          <TabsTrigger value="historico" className="gap-1"><History className="h-3.5 w-3.5" />Histórico & Execução</TabsTrigger>
        </TabsList>

        <TabsContent value="visao" className="mt-3 space-y-3">
          <div className="grid gap-3 md:grid-cols-3">
            <Card className="bento"><CardHeader className="pb-2"><CardTitle className="text-sm flex items-center gap-2"><Database className="h-4 w-4 text-[var(--cor-primaria)]" />Fontes</CardTitle></CardHeader><CardContent>{loadingF ? <Skeleton className="h-16 w-full" /> : <><p className="text-2xl font-bold text-[var(--cor-texto)]">{fontes.filter((f) => f.ativo).length} <span className="text-sm font-normal text-[var(--cor-texto-suave)]">/ {fontes.length} ativas</span></p><Progress value={fontes.length ? (fontes.filter((f) => f.ativo).length / fontes.length) * 100 : 0} className="mt-2" /><p className="mt-1 text-xs text-[var(--cor-texto-suave)]">{fontes.filter((f) => !f.ativo).length} inativas · {Object.keys(healthPorFonte).length} com erro recente</p></>}</CardContent></Card>
            <Card className="bento"><CardHeader className="pb-2"><CardTitle className="text-sm flex items-center gap-2"><Timer className="h-4 w-4 text-[var(--cor-primaria)]" />Execução</CardTitle></CardHeader><CardContent>{loadingE ? <Skeleton className="h-16 w-full" /> : execs[0] ? <><p className="text-sm font-medium text-[var(--cor-texto)]">{execs[0].total_itens_ingeridos} itens · {execs[0].total_grupos_formados} grupos · {execs[0].total_duplicatas_agrupadas} duplicatas</p><p className="text-xs text-[var(--cor-texto-suave)]">{rel(execs[0].executado_em)} · {execs[0].tokens_utilizados_summarization ?? "—"} trechos</p><p className="text-xs text-[var(--cor-texto-suave)]">Custo: {fmtUSD(execs[0].custo_estimado_summarization_usd)}</p></> : <p className="text-sm text-[var(--cor-texto-suave)]">Nenhuma execução ainda — use &quot;Executar agora&quot;.</p>}</CardContent></Card>
            <Card className="bento"><CardHeader className="pb-2"><CardTitle className="text-sm flex items-center gap-2"><DollarSign className="h-4 w-4 text-[var(--cor-primaria)]" />Custo</CardTitle></CardHeader><CardContent>{loadingE ? <Skeleton className="h-16 w-full" /> : <><p className="text-2xl font-bold text-[var(--cor-texto)]">{fmtUSD(custoHoje)} <span className="text-xs font-normal text-[var(--cor-texto-suave)]">hoje</span></p><p className="text-xs text-[var(--cor-texto-suave)]">Acumulado {fmtUSD(custoAcumulado)} · {execs.length} execuções</p><p className="text-xs text-[var(--cor-texto-suave)]">Teto {cfg ? fmtUSD(cfg.llm_teto_gasto_diario_usd) : "—"}/dia {cfg && custoHoje > cfg.llm_teto_gasto_diario_usd ? <span className="text-[var(--cor-erro)]">· teto excedido</span> : ""}</p></>}</CardContent></Card>
          </div>
          <Card className="bento">
            <CardHeader><CardTitle className="text-base flex items-center gap-2"><Activity className="h-4 w-4" />Sucesso por fonte (última execução)</CardTitle><CardDescription className="text-[var(--cor-texto-suave)]">Barras proporcionais aos itens ingeridos. Fonte com erro aparece em vermelho.</CardDescription></CardHeader>
            <CardContent className="space-y-2">
              {loadingE ? <Skeleton className="h-20 w-full" /> : !execs[0] ? <p className="text-sm text-[var(--cor-texto-suave)]">Sem dados — execute os robôs para ver o gráfico.</p> : (() => {
                const porFonte = execs[0].itens_por_fonte || {};
                const entries = Object.entries(porFonte);
                const max = Math.max(1, ...entries.map(([, v]) => Number(v) || 0));
                if (!entries.length) return <p className="text-sm text-[var(--cor-texto-suave)]">Nenhum item por fonte na última execução.</p>;
                return entries.map(([k, v]) => {
                  const n = Number(v) || 0; const pct = (n / max) * 100; const hasErr = !!healthPorFonte[k];
                  return <div key={k} className="space-y-1"><div className="flex items-center justify-between gap-2 text-xs"><span className="truncate font-medium text-[var(--cor-texto)] flex items-center gap-1">{hasErr ? <AlertTriangle className="h-3 w-3 text-[var(--cor-erro)]" /> : <CheckCircle2 className="h-3 w-3 text-[var(--cor-sucesso)]" />}{k} {hasErr && <span className="text-[var(--cor-erro)]">· erro</span>}</span><span className="text-[var(--cor-texto-suave)]">{n} itens</span></div><Progress value={pct} className={hasErr ? "[&>div]:bg-[var(--cor-erro)]" : ""} />{hasErr && <p className="truncate text-xs text-[var(--cor-erro)]">{healthPorFonte[k]}</p>}</div>;
                });
              })()}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="fontes" className="mt-3 space-y-3">
          <Card className="bento">
            <CardHeader><CardTitle className="text-base flex items-center gap-2"><Database className="h-4 w-4" />Fontes RSS</CardTitle><CardDescription className="text-[var(--cor-texto-suave)]">Cada fonte é um feed RSS. Ative/desative para controlar o que os robôs coletam. URL precisa ser https://.</CardDescription></CardHeader>
            <CardContent className="space-y-3">
              <div className="flex flex-col gap-2 md:flex-row md:items-center">
                <div className="relative flex-1"><Search className="pointer-events-none absolute left-2 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--cor-texto-suave)]" /><Input value={busca} onChange={(e) => setBusca(e.target.value)} placeholder="Buscar por nome, URL ou categoria" className="pl-8" /></div>
                <Select value={filtroAtivo} onValueChange={(v) => setFiltroAtivo(v as typeof filtroAtivo)}><SelectTrigger className="md:w-[160px]"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="todos">Todos</SelectItem><SelectItem value="ativo">Só ativas</SelectItem><SelectItem value="inativo">Só inativas</SelectItem></SelectContent></Select>
                <Button size="sm" variant="outline" onClick={carregarFontes} disabled={loadingF} className="min-h-[36px] border-[var(--cor-borda)]"><RefreshCw className="mr-1 h-3 w-3" />{loadingF ? "Carregando..." : "Atualizar"}</Button>
                <Badge variant="outline" className="border-[var(--cor-borda)]">{fontesFiltradas.length} / {fontes.length}</Badge>
              </div>
              {loadingF ? <div className="space-y-2"><Skeleton className="h-20 w-full" /><Skeleton className="h-20 w-full" /></div> : fontesQuery.isError ? <div role="alert" className="rounded-md border border-dashed border-[var(--cor-erro)] p-8 text-center"><Database className="mx-auto h-8 w-8 text-[var(--cor-texto-suave)]" /><p className="mt-2 text-sm font-medium text-[var(--cor-texto)]">Fontes indisponíveis</p><p className="mt-1 text-xs text-[var(--cor-texto-suave)]">A API não respondeu, então nenhuma fonte real foi carregada. Nenhuma fonte de exemplo é listada e nenhuma ação de remoção/edição fica disponível — ativar ou apagar a fonte errada pararia a coleta de um veículo real.</p></div> : fontesFiltradas.length === 0 ? <div className="rounded-md border border-dashed border-[var(--cor-borda)] p-8 text-center"><Database className="mx-auto h-8 w-8 text-[var(--cor-texto-suave)]" /><p className="mt-2 text-sm font-medium text-[var(--cor-texto)]">{fontes.length === 0 ? "Nenhuma fonte cadastrada" : "Nenhum resultado para o filtro"}</p><p className="text-xs text-[var(--cor-texto-suave)]">Crie a primeira fonte no formulário abaixo.</p></div> : <div className="grid gap-2">
                {fontesFiltradas.map((f) => {
                  const hasErr = !!healthPorFonte[f.nome] || !!healthPorFonte[f.url];
                  return <div key={f.id} className={`rounded-md border p-3 ${hasErr ? "border-[var(--cor-erro)] bg-[var(--cor-erro-suave)]" : "border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)]"}`}>
                    {editId === f.id ? (
                      <div className="space-y-2">
                        <div className="grid gap-2 md:grid-cols-2">
                          <div className="space-y-1"><Label>Nome *</Label><Input value={editNome} onChange={(e) => setEditNome(e.target.value)} placeholder="Ex: G1" />{!editNome.trim() && <p className="text-xs text-[var(--cor-erro)]">Obrigatório</p>}</div>
                          <div className="space-y-1"><Label>URL *</Label><Input value={editUrl} onChange={(e) => setEditUrl(e.target.value)} placeholder="https://..." />{editUrl.trim() && !isUrl(editUrl.trim()) ? <p className="text-xs text-[var(--cor-erro)]">URL precisa começar com https://</p> : <p className="text-xs text-[var(--cor-texto-suave)]">Endereço RSS completo, com https://</p>}</div>
                        </div>
                        <div className="grid gap-2 md:grid-cols-[1fr_auto] md:items-end">
                          <div className="space-y-1"><Label>Categoria padrão</Label><Input value={editCat} onChange={(e) => setEditCat(e.target.value)} placeholder="geral" /><p className="text-xs text-[var(--cor-texto-suave)]">Categoria quando o feed não informar (ex: geral, política)</p></div>
                          <div className="flex items-center gap-2 pb-1"><Label>Ativo</Label><Switch checked={editAtivo} onCheckedChange={setEditAtivo} /><span className="text-xs text-[var(--cor-texto-suave)]">{editAtivo ? "Coletando" : "Pausado"}</span></div>
                        </div>
                        <div className="flex gap-2"><Button size="sm" onClick={salvarEdicao} disabled={!editNome.trim() || !editUrl.trim() || !isUrl(editUrl.trim())} className="bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]">Salvar</Button><Button size="sm" variant="ghost" onClick={() => setEditId(null)}>Cancelar</Button></div>
                      </div>
                    ) : (
                      <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                        <div className="min-w-0 flex-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <p className="truncate font-medium text-[var(--cor-texto)]">{f.nome}</p>
                            <Badge variant={f.ativo ? "default" : "outline"} className={f.ativo ? "bg-[var(--cor-sucesso)] text-[var(--cor-texto-invertido)]" : "border-[var(--cor-borda)]"}>{f.ativo ? "ativo" : "inativo"}</Badge>
                            {f.categoria_padrao && <Badge variant="outline" className="border-[var(--cor-borda)]">{f.categoria_padrao}</Badge>}
                            {hasErr && <Badge variant="outline" className="border-[var(--cor-erro)] text-[var(--cor-erro)] gap-1"><AlertTriangle className="h-3 w-3" />erro recente</Badge>}
                          </div>
                          <a href={f.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 truncate text-xs text-[var(--cor-texto-suave)] hover:text-[var(--cor-primaria)]">{f.url}<ExternalLink className="h-3 w-3 shrink-0" /></a>
                          <p className="text-xs text-[var(--cor-texto-suave)]">Atualizado: {formatarDataHoraCompleta(f.atualizado_em)}</p>
                          {hasErr && <p className="truncate text-xs text-[var(--cor-erro)]">{healthPorFonte[f.nome] || healthPorFonte[f.url]}</p>}
                        </div>
                        <div className="flex flex-wrap gap-1">
                          <Button size="sm" variant="outline" onClick={() => toggleAtivo(f)} className="border-[var(--cor-borda)]">{f.ativo ? "Desativar" : "Ativar"}</Button>
                          <Button size="sm" variant="outline" onClick={() => iniciarEdicao(f)} className="border-[var(--cor-borda)]"><Pencil className="mr-1 h-3 w-3" />Editar</Button>
                          <Button size="sm" variant="outline" onClick={() => window.open(f.url, "_blank")} className="border-[var(--cor-borda)]"><ExternalLink className="mr-1 h-3 w-3" />Testar</Button>
                          <Button size="sm" variant="destructive" onClick={() => setConfirmRemove(f.id)}><Trash2 className="mr-1 h-3 w-3" />Remover</Button>
                        </div>
                      </div>
                    )}
                  </div>;
                })}
              </div>}
              <Separator />
              <div className="rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo)] p-3 space-y-3">
                <p className="flex items-center gap-2 text-sm font-medium text-[var(--cor-texto)]"><Plus className="h-4 w-4" />Nova fonte</p>
                <div className="grid gap-3 md:grid-cols-2">
                  <div className="space-y-1"><Label>Nome *</Label><Input value={nome} onChange={(e) => setNome(e.target.value)} placeholder="Ex: G1" />{nome.trim() ? null : <p className="text-xs text-[var(--cor-texto-suave)]">Nome curto para identificar a fonte</p>}</div>
                  <div className="space-y-1"><Label>URL *</Label><Input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://..." />{url.trim() && !isUrl(url.trim()) ? <p className="text-xs text-[var(--cor-erro)]">Use URL completa com https://</p> : <p className="text-xs text-[var(--cor-texto-suave)]">Link RSS — precisa começar com https://</p>}</div>
                </div>
                <div className="grid gap-3 md:grid-cols-[1fr_auto] md:items-end">
                  <div className="space-y-1"><Label>Categoria padrão</Label><Input value={cat} onChange={(e) => setCat(e.target.value)} placeholder="geral / politica / economia" /><p className="text-xs text-[var(--cor-texto-suave)]">Quando o feed não disser a categoria, usa esta</p></div>
                  <div className="flex items-center gap-2 pb-1"><Label>Ativo</Label><Switch checked={ativo} onCheckedChange={setAtivo} /><span className="text-xs text-[var(--cor-texto-suave)]">{ativo ? "Vai coletar" : "Pausado"}</span></div>
                </div>
                <Button onClick={criarFonte} disabled={!nome.trim() || !url.trim() || !isUrl(url.trim())} className="min-h-[44px] bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]"><Plus className="mr-2 h-4 w-4" />Criar fonte</Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="config" className="mt-3 space-y-3">
          <Card className="bento">
            <CardHeader><CardTitle className="text-base flex items-center gap-2"><Settings className="h-4 w-4" />Configuração dos robôs</CardTitle><CardDescription className="text-[var(--cor-texto-suave)]">Ajustes globais. Passe o mouse nos (?) para entender cada campo. Alterações só salvam ao clicar em Salvar.</CardDescription></CardHeader>
            <CardContent className="space-y-4">
              <div className="flex flex-wrap gap-2">
                <Button size="sm" variant="outline" onClick={carregarCfg} disabled={loadingC} className="border-[var(--cor-borda)]"><RefreshCw className="mr-1 h-3 w-3" />{loadingC ? "Carregando..." : "Recarregar"}</Button>
                <Button size="sm" onClick={salvarCfg} disabled={savingC || !cfg || !dirty || !!cfgInvalido} className="bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]">{savingC ? "Salvando..." : dirty ? "Salvar configuração" : "Sem alterações"}</Button>
                {cfg && <Badge variant="outline" className="border-[var(--cor-borda)]">Atualizado: {formatarDataHoraCompleta(cfg.atualizado_em)}</Badge>}
                {dirty && <Badge className="bg-[var(--cor-aviso)] text-[var(--cor-texto)]">alterações pendentes</Badge>}
              </div>
              {cfgInvalido && cfgInvalido !== "carregando" && <p className="rounded-md border border-[var(--cor-erro)] bg-[var(--cor-erro-suave)] px-3 py-2 text-sm text-[var(--cor-erro)]">{cfgInvalido}</p>}
              {!cfg ? (loadingC ? <div className="space-y-2"><Skeleton className="h-24 w-full" /><Skeleton className="h-24 w-full" /></div> : <p className="text-sm text-[var(--cor-texto-suave)]">Sem configuração — verifique login admin.</p>) : (
                <>
                  <div className="rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-3 space-y-3">
                    <p className="flex items-center gap-2 text-xs tracking-widest text-[var(--cor-texto-suave)]"><SlidersHorizontal className="h-3 w-3" />GERAL</p>
                    <div className="grid gap-3 md:grid-cols-3">
                      <div className="space-y-1"><Label>Intervalo (minutos) 1–1440</Label><Input type="number" min={1} max={1440} value={cfg.intervalo_minutos} onChange={(e) => setCfgField("intervalo_minutos", Math.max(1, Math.min(1440, Number(e.target.value) || 15)))} /><p className="text-xs text-[var(--cor-texto-suave)]">A cada quantos minutos os robôs buscam notícias. 60 = 1h, 1440 = 1 dia.</p></div>
                      <div className="space-y-1"><Label>Robôs ativos</Label><div className="flex items-center gap-2 rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] px-3 py-2"><Switch checked={cfg.ativo} onCheckedChange={(v) => setCfgField("ativo", v)} /><span className="text-sm text-[var(--cor-texto)]">{cfg.ativo ? "Coletando automaticamente" : "Pausado — só manual"}</span></div><p className="text-xs text-[var(--cor-texto-suave)]">Desative para pausar sem apagar fontes.</p></div>
                      <div className="space-y-1"><Label>Exigir revisão em cluster sempre</Label><div className="flex items-center gap-2 rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] px-3 py-2"><Switch checked={cfg.dedup_cluster_sempre_exige_revisao} onCheckedChange={(v) => setCfgField("dedup_cluster_sempre_exige_revisao", v)} /><Shield className="h-4 w-4 text-[var(--cor-texto-suave)]" /></div><p className="text-xs text-[var(--cor-texto-suave)]">Se ligado, todo grupo de notícias similares vai para fila de moderação.</p></div>
                    </div>
                    <div className="grid gap-3 md:grid-cols-2">
                      <div className="space-y-1"><Label>Categorias sensíveis (separe por vírgula)</Label><Input value={cfg.categorias_sensiveis} onChange={(e) => setCfgField("categorias_sensiveis", e.target.value)} placeholder="política, economia, segurança pública" /><p className="text-xs text-[var(--cor-texto-suave)]">Categorias que exigem cuidado extra na curadoria.</p></div>
                      <div className="space-y-1"><Label>Limiar fontes alta relevância</Label><Input type="number" min={1} value={cfg.limiar_fontes_alta_relevancia} onChange={(e) => setCfgField("limiar_fontes_alta_relevancia", Number(e.target.value) || 3)} /><p className="text-xs text-[var(--cor-texto-suave)]">Quantas fontes diferentes precisam citar o mesmo assunto para marcar como alta relevância. Ex: 3.</p></div>
                    </div>
                  </div>

                  <div className="rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-3 space-y-3">
                    <p className="flex items-center gap-2 text-xs tracking-widest text-[var(--cor-texto-suave)]"><Layers className="h-3 w-3" />DEDUP / CURADORIA — quando juntar notícias parecidas</p>
                    <div className="grid gap-3 md:grid-cols-3">
                      <div className="space-y-1"><Label>Limiar similaridade {(cfg.dedup_limiar_similaridade * 100).toFixed(0)}% — {cfg.dedup_limiar_similaridade.toFixed(2)}</Label><Slider min={0} max={1} step={0.01} value={cfg.dedup_limiar_similaridade} onChange={(e) => setCfgField("dedup_limiar_similaridade", Number((e.target as HTMLInputElement).value))} /><p className="text-xs text-[var(--cor-texto-suave)]">0.55 = 55% parecidas já agrupa como duplicata. Mais alto = mais rigoroso.</p></div>
                      <div className="space-y-1"><Label>Janela (horas)</Label><Input type="number" step={0.5} value={cfg.dedup_janela_horas} onChange={(e) => setCfgField("dedup_janela_horas", Number(e.target.value))} /><p className="text-xs text-[var(--cor-texto-suave)]">Só compara notícias dentro desta janela. Ex: 48h.</p></div>
                      <div className="space-y-1"><Label>Máx. itens recentes</Label><Input type="number" value={cfg.dedup_max_itens} onChange={(e) => setCfgField("dedup_max_itens", Number(e.target.value))} /><p className="text-xs text-[var(--cor-texto-suave)]">Limite de itens recentes para comparar — evita lentidão.</p></div>
                    </div>
                    <div className="grid gap-3 md:grid-cols-2">
                      <div className="space-y-1"><Label>Resumo similaridade máx. {(cfg.resumo_similaridade_maxima * 100).toFixed(0)}% — {cfg.resumo_similaridade_maxima.toFixed(2)}</Label><Slider min={0} max={1} step={0.01} value={cfg.resumo_similaridade_maxima} onChange={(e) => setCfgField("resumo_similaridade_maxima", Number((e.target as HTMLInputElement).value))} /><p className="text-xs text-[var(--cor-texto-suave)]">Se o resumo ficar muito igual ao original (&gt; este valor), é reprovado. Evita cópia.</p></div>
                      <div className="space-y-1"><Label>Trecho copiado máx. {(cfg.resumo_trecho_copiado_maximo * 100).toFixed(0)}% — {cfg.resumo_trecho_copiado_maximo.toFixed(2)}</Label><Slider min={0} max={1} step={0.01} value={cfg.resumo_trecho_copiado_maximo} onChange={(e) => setCfgField("resumo_trecho_copiado_maximo", Number((e.target as HTMLInputElement).value))} /><p className="text-xs text-[var(--cor-texto-suave)]">Teto de texto literal copiado no resumo. 0.3 = 30%.</p></div>
                    </div>
                  </div>

                  <div className="rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-3 space-y-3">
                    <p className="flex items-center gap-2 text-xs tracking-widest text-[var(--cor-texto-suave)]"><Cpu className="h-3 w-3" />LLM / RESUMO AUTOMÁTICO</p>
                    <div className="grid gap-3 md:grid-cols-2">
                      <div className="space-y-1"><Label>Modelo</Label><Input value={cfg.llm_model} onChange={(e) => setCfgField("llm_model", e.target.value)} placeholder="gpt-4o-mini" /><p className="text-xs text-[var(--cor-texto-suave)]">Nome do modelo (ex: gpt-4o-mini). Depende do provedor.</p></div>
                      <div className="space-y-1"><Label>API Base URL</Label><Input value={cfg.llm_api_base_url} onChange={(e) => setCfgField("llm_api_base_url", e.target.value)} placeholder="https://api.openai.com/v1" /><p className="text-xs text-[var(--cor-texto-suave)]">URL base do provedor. Padrão OpenAI.</p></div>
                    </div>
                    <div className="grid gap-3 md:grid-cols-3">
                      <div className="space-y-1"><Label>Tamanho do lote</Label><Input type="number" value={cfg.llm_tamanho_lote} onChange={(e) => setCfgField("llm_tamanho_lote", Number(e.target.value))} /><p className="text-xs text-[var(--cor-texto-suave)]">Quantos itens envia por vez ao LLM.</p></div>
                      <div className="space-y-1"><Label>Máx. trechos por item</Label><Input type="number" value={cfg.llm_max_tokens_por_item} onChange={(e) => setCfgField("llm_max_tokens_por_item", Number(e.target.value))} /><p className="text-xs text-[var(--cor-texto-suave)]">Limite de tamanho do resumo gerado.</p></div>
                      <div className="space-y-1"><Label>Timeout (segundos)</Label><Input type="number" value={cfg.llm_timeout_segundos} onChange={(e) => setCfgField("llm_timeout_segundos", Number(e.target.value))} /><p className="text-xs text-[var(--cor-texto-suave)]">Tempo máx. esperando resposta do LLM.</p></div>
                    </div>
                    <div className="grid gap-3 md:grid-cols-2">
                      <div className="space-y-1"><Label>Teto gasto diário USD</Label><Input type="number" step={0.1} value={cfg.llm_teto_gasto_diario_usd} onChange={(e) => setCfgField("llm_teto_gasto_diario_usd", Number(e.target.value))} /><p className="text-xs text-[var(--cor-texto-suave)]">Trava de custo — se atingir, pausa resumos no dia.</p></div>
                      <div className="space-y-1"><Label>Preço por 1 mil trechos (USD)</Label><Input type="number" step={0.01} value={cfg.llm_preco_por_1k_tokens} onChange={(e) => setCfgField("llm_preco_por_1k_tokens", Number(e.target.value))} /><p className="text-xs text-[var(--cor-texto-suave)]">Para calcular custo estimado. Ex: 0.0003.</p></div>
                    </div>
                    <Button onClick={salvarCfg} disabled={savingC || !dirty || !!cfgInvalido} className="min-h-[44px] w-full bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)] md:w-auto">{savingC ? "Salvando..." : "Salvar configuração"}</Button>
                  </div>
                </>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="historico" className="mt-3 space-y-3">
          <Card className="bento">
            <CardHeader><CardTitle className="text-base flex items-center gap-2"><History className="h-4 w-4" />Histórico & Execução</CardTitle><CardDescription className="text-[var(--cor-texto-suave)]">Últimas 50 execuções. Barras mostram itens por fonte, erros expandem, custo acumula. Use Executar para forçar ingestão agora.</CardDescription></CardHeader>
            <CardContent className="space-y-3">
              <div className="flex flex-wrap items-center gap-2">
                <Button size="sm" variant="outline" onClick={carregarExecs} disabled={loadingE} className="border-[var(--cor-borda)]"><RefreshCw className="mr-1 h-3 w-3" />{loadingE ? "Carregando..." : "Atualizar"}</Button>
                <Button size="sm" onClick={() => setConfirmExec(true)} disabled={execLoading} className="bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]"><Play className="mr-1 h-3 w-3" />{execLoading ? "Executando..." : "Executar agora"}</Button>
                <Badge variant="outline" className="border-[var(--cor-borda)]">{execs.length} execuções · acumulado {fmtUSD(custoAcumulado)}</Badge>
                {execLoading && <span className="flex items-center gap-1 text-xs text-[var(--cor-texto-suave)]"><RefreshCw className="h-3 w-3 animate-spin" />em andamento...</span>}
              </div>
              {execLog.length > 0 && <div className="max-h-28 overflow-auto rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo)] p-2 font-mono text-xs text-[var(--cor-texto-suave)]">{execLog.map((l, i) => <p key={i}>{l}</p>)}</div>}
              {loadingE ? <div className="space-y-2"><Skeleton className="h-24 w-full" /><Skeleton className="h-24 w-full" /></div> : !execs.length ? <div className="rounded-md border border-dashed border-[var(--cor-borda)] p-8 text-center"><History className="mx-auto h-8 w-8 text-[var(--cor-texto-suave)]" /><p className="mt-2 text-sm text-[var(--cor-texto-suave)]">Nenhuma execução ainda — clique em Executar agora.</p></div> : (
                <>
                  <div className="grid gap-2">
                    {execsPag.map((ex) => {
                      const porFonte = ex.itens_por_fonte || {};
                      const entries = Object.entries(porFonte);
                      const max = Math.max(1, ...entries.map(([, v]) => Number(v) || 0));
                      const hasErr = Object.keys(ex.erros_por_fonte || {}).length > 0;
                      const expanded = expandErr === ex.id;
                      return <div key={ex.id} className={`rounded-md border p-3 ${hasErr ? "border-[var(--cor-aviso)] bg-[var(--cor-fundo-elevado)]" : "border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)]"}`}>
                        <div className="flex flex-wrap items-center gap-2">
                          <Badge variant="outline" className="border-[var(--cor-borda)]">#{ex.id}</Badge>
                          <span className="text-xs text-[var(--cor-texto-suave)] flex items-center gap-1"><Clock className="h-3 w-3" />{formatarDataHoraCompleta(ex.executado_em)} · {rel(ex.executado_em)}</span>
                          <Badge className="bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]">{ex.total_itens_ingeridos} itens</Badge>
                          <Badge variant="outline" className="border-[var(--cor-borda)]">{ex.total_grupos_formados} grupos</Badge>
                          <Badge variant="outline" className="border-[var(--cor-borda)]">{ex.total_duplicatas_agrupadas} dup</Badge>
                          {hasErr ? <Badge variant="outline" className="border-[var(--cor-erro)] text-[var(--cor-erro)]"><AlertTriangle className="mr-1 h-3 w-3" />erro</Badge> : <Badge variant="outline" className="border-[var(--cor-sucesso)] text-[var(--cor-sucesso)]"><CheckCircle2 className="mr-1 h-3 w-3" />ok</Badge>}
                        </div>
                        <p className="mt-1 text-xs text-[var(--cor-texto-suave)]">LLM: {ex.chamadas_summarization_provider} chamadas · {ex.tokens_utilizados_summarization ?? "—"} trechos · {fmtUSD(ex.custo_estimado_summarization_usd)}</p>
                        <div className="mt-2 space-y-1">
                          {entries.length === 0 ? <p className="text-xs text-[var(--cor-texto-suave)]">Sem itens por fonte</p> : entries.map(([k, v]) => {
                            const n = Number(v) || 0; const pct = (n / max) * 100;
                            return <div key={k} className="flex items-center gap-2 text-xs"><span className="w-28 truncate text-[var(--cor-texto)]">{k}</span><Progress value={pct} className="flex-1" /><span className="w-10 text-right text-[var(--cor-texto-suave)]">{n}</span></div>;
                          })}
                        </div>
                        {hasErr && <div className="mt-2"><Button size="sm" variant="ghost" onClick={() => setExpandErr(expanded ? null : ex.id)} className="h-7 text-xs">{expanded ? "Ocultar erros" : `Ver ${Object.keys(ex.erros_por_fonte).length} erro(s)`}</Button>{expanded && <pre className="mt-1 max-h-32 overflow-auto whitespace-pre-wrap break-all rounded bg-[var(--cor-fundo)] p-2 text-xs text-[var(--cor-erro)]">{JSON.stringify(ex.erros_por_fonte, null, 2)}</pre>}</div>}
                      </div>;
                    })}
                  </div>
                  {totalPag > 1 && <div className="flex items-center justify-between gap-2 pt-2"><Button size="sm" variant="outline" disabled={execPage <= 1} onClick={() => setExecPage((p) => p - 1)} className="border-[var(--cor-borda)]">Anterior</Button><span className="text-xs text-[var(--cor-texto-suave)]">Página {execPage} / {totalPag}</span><Button size="sm" variant="outline" disabled={execPage >= totalPag} onClick={() => setExecPage((p) => p + 1)} className="border-[var(--cor-borda)]">Próxima</Button></div>}
                </>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      <Dialog open={confirmRemove !== null} onOpenChange={(o) => !o && setConfirmRemove(null)}>
        <DialogContent><DialogHeader><DialogTitle>Remover fonte?</DialogTitle><DialogDescription>Esta ação não pode ser desfeita. A fonte deixará de ser coletada.</DialogDescription></DialogHeader><DialogFooter><Button variant="outline" onClick={() => setConfirmRemove(null)}>Cancelar</Button><Button variant="destructive" onClick={removerFonte}>Remover</Button></DialogFooter></DialogContent>
      </Dialog>
      <Dialog open={confirmExec} onOpenChange={setConfirmExec}>
        <DialogContent><DialogHeader><DialogTitle className="flex items-center gap-2"><Play className="h-4 w-4" />Executar robôs agora?</DialogTitle><DialogDescription>Vai buscar todas as fontes ativas, agrupar duplicatas e chamar LLM se configurado. Pode levar alguns segundos.</DialogDescription></DialogHeader><DialogFooter><Button variant="outline" onClick={() => setConfirmExec(false)}>Cancelar</Button><Button onClick={executar} className="bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]">Confirmar execução</Button></DialogFooter></DialogContent>
      </Dialog>
    </div>
  );
}
