"use client";
import { useEffect, useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Separator } from "@/components/ui/separator";
import { useAuth } from "@/lib/auth-context";
import * as api from "@/lib/api";
import { useQueryAdminFila } from "@/lib/queries";
import { queryKeys } from "@/lib/query-keys";
import { formatarDataHoraCompleta } from "@/lib/datas";
import { Clock, Filter, CheckCheck, XCircle, RefreshCw, AlertTriangle, Layers, Search, CheckSquare, Square, Zap, Sparkles } from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";

type Item = api.AdminFilaItem;
const STATUS_OPS = ["pendente","aprovado","rejeitado","nao_aplicavel"] as const;
const PAGE_SIZE = 20;

function timeAgo(iso:string){
  const d = Date.now() - new Date(iso).getTime();
  const h = Math.floor(d/3600000);
  if(h<1) return "agora";
  if(h<24) return `${h}h`;
  return `${Math.floor(h/24)}d`;
}

const MOCK: Item[] = [
  { tipo: "item", id: 1, titulo: "Reforma tributária entra em fase de regulamentação", categoria: "economia", status_revisao: "pendente", nome_fonte: "Fonte Exemplo", url_fonte_original: "https://example.com/a", urgente: false, cluster: null, cluster_titulo: "", timestamp_ingestao: new Date().toISOString() },
  { tipo: "cluster", id: 2, titulo: "Frente fria avança pelo Sudeste", categoria: "cidades", status_revisao: "pendente", nome_fonte: "G1", url_fonte_original: "https://example.com/b", urgente: true, cluster: 10, cluster_titulo: "Frente fria no Sudeste", timestamp_ingestao: new Date(Date.now()-3600000*2).toISOString() },
  { tipo: "item", id: 3, titulo: "Vacina nacional entra em testes finais", categoria: "saúde", status_revisao: "pendente", nome_fonte: "CNN", url_fonte_original: "https://example.com/c", urgente: false, cluster: null, cluster_titulo: "", timestamp_ingestao: new Date(Date.now()-3600000*5).toISOString() },
];

export default function Page(){
  const { usuario, token } = useAuth();
  const tk = token||"";
  const cliente = useQueryClient();
  const [status,setStatus]=useState<string>("pendente");
  const [busca,setBusca]=useState(""); const [q,setQ]=useState("");
  const [cat,setCat]=useState<string>("todas");
  const [soUrgente,setSoUrgente]=useState(false);
  const [soCluster,setSoCluster]=useState(false);
  const [ordem,setOrdem]=useState<"recente"|"antigo"|"titulo">("recente");
  const [page,setPage]=useState(1);
  const [ok,setOk]=useState<string|null>(null); const [erroMutacao,setErroMutacao]=useState<string|null>(null);
  const [sel,setSel]=useState<Set<number>>(new Set());
  const [acting,setActing]=useState<number|null>(null);
  const [bulk,setBulk]=useState(false);
  const [aprovarTudoOpen,setAprovarTudoOpen]=useState(false);
  const [aprovarTudoProg,setAprovarTudoProg]=useState<{done:number; total:number; fail:number} | null>(null);
  const [aprovarTudoRunning,setAprovarTudoRunning]=useState(false);
  const [auto,setAuto]=useState(false);

  // Fila de curadoria: leitura sempre fresca (staleTime 0), com polling
  // opcional de 30s (Auto) e preservação da página anterior durante a troca.
  const consultaFila = useQueryAdminFila({
    token,
    usuarioId: usuario?.id ?? 0,
    status,
    page,
    intervaloMs: auto ? 30_000 : 0,
  });
  // Memorizado de propósito: sem isto o `?? []` cria um array novo a cada
  // render e as dependências de `cats`/`filtrados` mudam sempre — os dois
  // useMemo abaixo nunca acertam o cache. `MOCK` é constante de módulo e
  // `consultaFila.data` é referência estável do React Query, então a
  // referência de `itens` só muda quando os dados mudam de fato.
  const itens = useMemo(
    () => (consultaFila.isError ? MOCK : (consultaFila.data?.results ?? [])),
    [consultaFila.isError, consultaFila.data]
  );
  const total = consultaFila.isError ? MOCK.length : (consultaFila.data?.count ?? 0);
  const loading = consultaFila.isFetching;
  const err = consultaFila.isError
    ? (consultaFila.error instanceof Error ? consultaFila.error.message : "Falha ao carregar fila — tente novamente em instantes")
    : erroMutacao;

  // Cada carregamento limpa a mensagem anterior (como o antigo carregar fazia).
  useEffect(() => {
    if (consultaFila.isFetching) setOk(null);
  }, [consultaFila.isFetching]);
  // Mensagem quando a fila volta vazia para o status atual.
  useEffect(() => {
    if (!consultaFila.isSuccess) return;
    if (!(consultaFila.data?.results ?? []).length) setOk(status === "pendente" ? "Fila vazia — nada pendente para curadoria." : `Nenhum item com status "${status}".`);
  }, [consultaFila.isSuccess, consultaFila.data, status]);

  useEffect(()=>{ setPage(1); },[status]);

  const recarregar = () => { setErroMutacao(null); void consultaFila.refetch(); };

  const cats = useMemo(()=> Array.from(new Set(itens.map(i=>i.categoria).filter(Boolean))).sort(),[itens]);

  const filtrados = useMemo(()=>{
    let r=[...itens];
    if(q){ const qq=q.toLowerCase(); r=r.filter(i=> i.titulo.toLowerCase().includes(qq) || i.nome_fonte.toLowerCase().includes(qq) || i.url_fonte_original.toLowerCase().includes(qq) || i.categoria.toLowerCase().includes(qq) || (i.cluster_titulo||"").toLowerCase().includes(qq)); }
    if(cat!=="todas") r=r.filter(i=>i.categoria===cat);
    if(soUrgente) r=r.filter(i=>i.urgente);
    if(soCluster) r=r.filter(i=> !!i.cluster);
    r.sort((a,b)=>{
      if(ordem==="titulo") return a.titulo.localeCompare(b.titulo);
      const ta=new Date(a.timestamp_ingestao).getTime(); const tb=new Date(b.timestamp_ingestao).getTime();
      return ordem==="recente"? tb-ta : ta-tb;
    });
    return r;
  },[itens,q,cat,soUrgente,soCluster,ordem]);

  const pendentes = itens.filter(i=>i.status_revisao==="pendente").length;
  const urgentes = itens.filter(i=>i.urgente).length;
  const clusters = itens.filter(i=> !!i.cluster).length;
  const totalSel = sel.size;
  const allSel = filtrados.length>0 && filtrados.every(i=> sel.has(i.id));

  const toggleSel=(id:number)=> setSel(prev=>{ const n=new Set(prev); if(n.has(id)) n.delete(id); else n.add(id); return n; });
  const toggleAll=()=> setSel(prev=>{ if(allSel) return new Set(); return new Set(filtrados.map(i=>i.id)); });

  const decidir=async(id:number,acao:"aprovar"|"rejeitar")=>{
    setActing(id); setErroMutacao(null);
    try{ await api.adminDecidirFila(tk,id,acao); setOk(acao==="aprovar"?"Aprovado.":"Rejeitado."); setSel(prev=>{ const n=new Set(prev); n.delete(id); return n; }); await cliente.invalidateQueries({ queryKey: queryKeys.admin.filaRaiz() }); }
    catch(e:any){ setErroMutacao(e?.message||"Falha na decisão."); }
    finally{ setActing(null); }
  };
  const bulkDecidir=async(acao:"aprovar"|"rejeitar")=>{
    if(!sel.size) return;
    if(!confirm(`${acao==="aprovar"?"Aprovar":"Rejeitar"} ${sel.size} itens selecionados?`)) return;
    setBulk(true); setErroMutacao(null);
    let okC=0; let fail=0;
    for(const id of Array.from(sel)){
      try{ await api.adminDecidirFila(tk,id,acao); okC++; } catch{ fail++; }
    }
    setBulk(false); setSel(new Set());
    setOk(`${okC} ${acao==="aprovar"?"aprovados":"rejeitados"}${fail?` — ${fail} falhas`:""}.`);
    await cliente.invalidateQueries({ queryKey: queryKeys.admin.filaRaiz() });
  };

  const executarAprovarTudo=async()=>{
    const pendentesIds = filtrados.filter(i=>i.status_revisao==="pendente").map(i=>i.id);
    let allIds=[...pendentesIds];
    if(total>itens.length && status==="pendente"){
      const pages=Math.ceil(total/PAGE_SIZE);
      for(let pg=1; pg<=pages; pg++){
        if(pg===page) continue;
        try{ const r=await api.adminListarFila(tk,{status:"pendente",page:pg}); const batch=(r.results||[]).filter(x=>x.status_revisao==="pendente").map(x=>x.id); allIds.push(...batch); }catch{}
      }
    }
    allIds=[...new Set(allIds)];
    if(!allIds.length){ setOk("Nada pendente nos filtros atuais."); setAprovarTudoOpen(false); return; }
    setAprovarTudoRunning(true); setErroMutacao(null); setAprovarTudoProg({done:0,total:allIds.length,fail:0});
    let done=0; let fail=0;
    for(const id of allIds){
      try{ await api.adminDecidirFila(tk,id,"aprovar"); done++; }catch{ fail++; }
      setAprovarTudoProg({done,total:allIds.length,fail});
    }
    setAprovarTudoRunning(false); setAprovarTudoOpen(false); setAprovarTudoProg(null); setSel(new Set());
    setOk(`${done} aprovados${fail?` — ${fail} falhas`:""} (aprovar tudo${total>itens.length?` — ${allIds.length} itens em ${Math.ceil(total/PAGE_SIZE)} páginas`:""}).`);
    await cliente.invalidateQueries({ queryKey: queryKeys.admin.filaRaiz() });
  };

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="space-y-4">
      <Card className="bento">
        <CardHeader>
          <CardTitle className="flex items-center gap-2"><Layers className="h-5 w-5 text-[var(--cor-neon-violeta)]" /> Fila de curadoria</CardTitle>
          <CardDescription className="text-[var(--cor-texto-suave)]">Triagem, filtros e publicação — aprove para publicar, rejeite para arquivar.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid gap-2 md:grid-cols-4">
            <div className="rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-3 text-center"><p className="text-xs tracking-widest text-[var(--cor-texto-suave)]">PENDENTES</p><p className="text-2xl font-bold text-[var(--cor-texto)]">{pendentes}</p></div>
            <div className="rounded-md border border-[var(--cor-sinal)] bg-[var(--cor-erro-suave)] p-3 text-center"><p className="text-xs tracking-widest text-[var(--cor-erro)]">URGENTES</p><p className="text-2xl font-bold text-[var(--cor-erro)]">{urgentes}</p></div>
            <div className="rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-3 text-center"><p className="text-xs tracking-widest text-[var(--cor-texto-suave)]">CLUSTERS</p><p className="text-2xl font-bold text-[var(--cor-neon-violeta)]">{clusters}</p></div>
            <div className="rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-3 text-center"><p className="text-xs tracking-widest text-[var(--cor-texto-suave)]">TOTAL NA PÁGINA</p><p className="text-2xl font-bold text-[var(--cor-texto)]">{itens.length}</p><p className="text-xs text-[var(--cor-texto-suave)]">{total} no total · pág {page}/{totalPages}</p></div>
          </div>

          <div className="flex flex-wrap gap-2">
            <Button onClick={recarregar} disabled={loading} variant="outline" className="min-h-[36px]"><RefreshCw className={`mr-1 h-4 w-4 ${loading?"animate-spin":""}`} /> Atualizar</Button>
            <Button onClick={()=>setAprovarTudoOpen(true)} disabled={!filtrados.some(i=>i.status_revisao==="pendente")||bulk||aprovarTudoRunning||!tk||loading} className="min-h-[36px] bg-emerald-600 text-white hover:bg-emerald-700 gap-1.5"><Sparkles className="h-4 w-4" /> Aprovar tudo <Badge variant="outline" className="ml-1 border-white/30 bg-white/15 text-white">{filtrados.filter(i=>i.status_revisao==="pendente").length}{total>itens.length?` de ${total}`:""} pendentes</Badge></Button>
            <Button onClick={()=>{const ids=filtrados.filter(i=>i.status_revisao==="pendente").map(i=>i.id); if(!ids.length) return; setSel(new Set(ids)); window.scrollTo({top: document.body.scrollHeight/3, behavior:"smooth"});}} disabled={!filtrados.some(i=>i.status_revisao==="pendente")||bulk} variant="outline" className="min-h-[36px] gap-1"><Zap className="h-4 w-4" /> Selecionar todos pendentes</Button>
            <div className="flex items-center gap-2 rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] px-3 py-1 text-xs"><Switch checked={auto} onCheckedChange={setAuto} id="auto" /><Label htmlFor="auto" className="text-xs">Auto 30s</Label></div>
            {totalSel>0&&<Badge className="bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]">{totalSel} selecionados</Badge>}
            {!tk&&<Badge variant="outline" className="border-[var(--cor-erro)] text-[var(--cor-erro)]">Login admin requerido</Badge>}
          </div>
          {err&&<p className="rounded-md border border-[var(--cor-erro)] bg-[var(--cor-erro-suave)] px-3 py-2 text-sm text-[var(--cor-erro)]">{err}</p>}
          {ok&&<p className="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700 dark:border-emerald-900 dark:bg-emerald-950 dark:text-emerald-300">{ok}</p>}
        </CardContent>
      </Card>

      <Card className="bento">
        <CardContent className="p-3">
          <div className="flex items-center gap-2 text-xs font-semibold tracking-widest text-[var(--cor-texto-suave)]"><Filter className="h-4 w-4" /> FILTROS & BUSCA</div>
          <div className="mt-3 grid gap-3 md:grid-cols-[160px_180px_1fr]">
            <div className="space-y-1"><Label>Status</Label>
              <Select value={status} onValueChange={setStatus}>
                <SelectTrigger className="bg-[var(--cor-fundo-card)]"><SelectValue /></SelectTrigger>
                <SelectContent>{STATUS_OPS.map(s=> <SelectItem key={s} value={s}>{s}</SelectItem>)}<SelectItem value="">todos</SelectItem></SelectContent>
              </Select>
            </div>
            <div className="space-y-1"><Label>Categoria</Label>
              <Select value={cat} onValueChange={setCat}>
                <SelectTrigger className="bg-[var(--cor-fundo-card)]"><SelectValue /></SelectTrigger>
                <SelectContent><SelectItem value="todas">todas</SelectItem>{cats.map(c=> <SelectItem key={c} value={c}>{c}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div className="space-y-1"><Label>Busca (título/fonte/cluster)</Label>
              <div className="flex gap-2">
                <div className="relative flex-1"><Search className="pointer-events-none absolute left-2.5 top-2.5 h-4 w-4 text-[var(--cor-texto-suave)]" /><Input value={busca} onChange={e=>setBusca(e.target.value)} onKeyDown={e=> e.key==="Enter"&&setQ(busca)} placeholder="ex: economia, G1, frente fria..." className="pl-8 bg-[var(--cor-fundo-card)]" /></div>
                <Button variant="outline" onClick={()=>setQ(busca)} className="shrink-0">Filtrar</Button>
                {(q||cat!=="todas"||soUrgente||soCluster)&&<Button variant="ghost" onClick={()=>{setBusca("");setQ("");setCat("todas");setSoUrgente(false);setSoCluster(false);}}>Limpar</Button>}
              </div>
            </div>
          </div>
          <div className="mt-3 flex flex-wrap gap-3">
            <label className="flex items-center gap-2 text-sm"><Switch checked={soUrgente} onCheckedChange={setSoUrgente} /> <span className="flex items-center gap-1"><AlertTriangle className="h-3 w-3 text-[var(--cor-sinal)]" /> Só urgentes</span></label>
            <label className="flex items-center gap-2 text-sm"><Switch checked={soCluster} onCheckedChange={setSoCluster} /> <span className="flex items-center gap-1"><Layers className="h-3 w-3 text-[var(--cor-neon-violeta)]" /> Só clusters</span></label>
            <div className="ml-auto flex items-center gap-2 text-sm">
              <Label>Ordem</Label>
              <Select value={ordem} onValueChange={(v:any)=>setOrdem(v)}>
                <SelectTrigger className="w-[150px] bg-[var(--cor-fundo-card)]"><SelectValue /></SelectTrigger>
                <SelectContent><SelectItem value="recente">Mais recente</SelectItem><SelectItem value="antigo">Mais antigo</SelectItem><SelectItem value="titulo">Título A-Z</SelectItem></SelectContent>
              </Select>
            </div>
          </div>
          <Separator className="my-3" />
          <div className="flex flex-wrap items-center gap-2">
            <Button size="sm" variant={allSel?"default":"outline"} onClick={toggleAll} disabled={!filtrados.length} className="gap-1">{allSel?<CheckSquare className="h-4 w-4" />:<Square className="h-4 w-4" />} {allSel?"Desmarcar todos":"Selecionar todos"} ({filtrados.length})</Button>
            <Button size="sm" onClick={()=>bulkDecidir("aprovar")} disabled={!totalSel||bulk} className="gap-1 bg-emerald-600 text-white hover:bg-emerald-700"><CheckCheck className="h-4 w-4" /> Aprovar selecionados</Button>
            <Button size="sm" variant="destructive" onClick={()=>bulkDecidir("rejeitar")} disabled={!totalSel||bulk} className="gap-1"><XCircle className="h-4 w-4" /> Rejeitar selecionados</Button>
            {bulk&&<span className="text-xs text-[var(--cor-texto-suave)]">Processando lote...</span>}
            <span className="ml-auto text-xs text-[var(--cor-texto-suave)] flex items-center gap-1"><Clock className="h-3 w-3" /> {filtrados.length} em exibição · {total} no total · pág {page}/{totalPages}</span>
          </div>
        </CardContent>
      </Card>

      <Card className="bento">
        <CardContent className="p-0">
          <div className="divide-y divide-[var(--cor-borda)]">
            {filtrados.map((it)=> {
              const checked=sel.has(it.id);
              return (
                <div key={`${it.tipo}-${it.id}`} className={`flex gap-3 p-3 ${checked?"bg-[var(--cor-primaria-suave)]":"bg-[var(--cor-fundo-card)]"} hover:bg-[var(--cor-fundo-elevado)] transition-colors`}>
                  <Checkbox checked={checked} onCheckedChange={()=>toggleSel(it.id)} aria-label={`Selecionar ${it.titulo}`} className="mt-1" />
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge variant="outline" className="border-[var(--cor-borda)] text-xs">{it.status_revisao}</Badge>
                      <Badge variant="outline" className="border-[var(--cor-borda)] text-xs capitalize">{it.categoria||"—"}</Badge>
                      <Badge variant={it.tipo==="cluster"?"default":"outline"} className={it.tipo==="cluster"?"bg-[var(--cor-neon-violeta)] text-[var(--cor-texto-invertido)] text-xs":"text-xs"}>{it.tipo}</Badge>
                      {it.urgente&&<Badge className="bg-[var(--cor-sinal)] text-[var(--cor-texto-invertido)] text-xs">urgente</Badge>}
                      {it.cluster&&<Badge variant="outline" className="border-[var(--cor-neon-ciano)] text-[var(--cor-neon-ciano)] text-xs">cluster #{it.cluster}</Badge>}
                      <span className="ml-auto flex items-center gap-1 text-xs text-[var(--cor-texto-suave)]"><Clock className="h-3 w-3" />{timeAgo(it.timestamp_ingestao)} · {formatarDataHoraCompleta(it.timestamp_ingestao)}</span>
                    </div>
                    <p className="mt-1 line-clamp-2 text-sm font-semibold leading-tight text-[var(--cor-texto)]">{it.titulo}</p>
                    {it.cluster_titulo&&<p className="text-xs text-[var(--cor-neon-violeta)]">↳ {it.cluster_titulo}</p>}
                    <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-[var(--cor-texto-suave)]">
                      <span className="font-medium text-[var(--cor-texto)]">{it.nome_fonte}</span>
                      <span className="truncate max-w-[320px]">{it.url_fonte_original}</span>
                      <a href={it.url_fonte_original} target="_blank" rel="noopener noreferrer" className="shrink-0 text-[var(--cor-primaria)] hover:underline">abrir fonte →</a>
                    </div>
                    <div className="mt-2 flex flex-wrap gap-2">
                      <Button size="sm" onClick={()=>decidir(it.id,"aprovar")} disabled={!!acting} className="h-7 bg-emerald-600 px-3 text-xs text-white hover:bg-emerald-700">{acting===it.id?"...":"Aprovar"}</Button>
                      <Button size="sm" variant="destructive" onClick={()=>decidir(it.id,"rejeitar")} disabled={!!acting} className="h-7 px-3 text-xs">{acting===it.id?"...":"Rejeitar"}</Button>
                      <Button size="sm" variant="outline" asChild className="h-7 px-3 text-xs"><a href={it.url_fonte_original} target="_blank" rel="noopener noreferrer">Ver na fonte</a></Button>
                    </div>
                  </div>
                </div>
              );
            })}
            {!filtrados.length&&!loading&&<div className="p-8 text-center text-sm text-[var(--cor-texto-suave)]">Nenhum item com os filtros atuais. Ajuste busca/categoria ou mude o status.</div>}
            {loading&&<div className="p-8 text-center text-sm text-[var(--cor-texto-suave)]">Carregando fila...</div>}
          </div>

          <div className="flex flex-wrap items-center justify-between gap-2 border-t border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-3">
            <div className="flex gap-2">
              <Button size="sm" variant="outline" disabled={page<=1||loading} onClick={()=>setPage(p=>Math.max(1,p-1))}>← Anterior</Button>
              <Button size="sm" variant="outline" disabled={page>=totalPages||loading} onClick={()=>setPage(p=>p+1)}>Próxima →</Button>
            </div>
            <div className="flex items-center gap-3 text-xs text-[var(--cor-texto-suave)]">
              <span>Página <span className="font-medium text-[var(--cor-texto)]">{page}</span> de {totalPages} · {total} itens</span>
              <Select value={String(page)} onValueChange={v=>setPage(Number(v))}>
                <SelectTrigger className="h-7 w-[110px] bg-[var(--cor-fundo-card)]"><SelectValue /></SelectTrigger>
                <SelectContent>{Array.from({length: Math.min(totalPages,20)},(_,i)=> i+1).map(n=> <SelectItem key={n} value={String(n)}>Pág {n}</SelectItem>)}</SelectContent>
              </Select>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card className="bento border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)]">
        <CardContent className="p-3 text-xs leading-relaxed text-[var(--cor-texto-suave)]">
          <p className="font-medium text-[var(--cor-texto)]">Como funciona esta tela</p>
          <p>Aprovar publica no feed; rejeitar arquiva. <span className="font-medium text-emerald-700">Aprovar tudo</span> publica todos os pendentes dos filtros atuais, passando por todas as páginas quando necessário. Seleção em lote é processada uma a uma com confirmação. 20 itens por página. Atualização automática opcional a cada 30s.</p>
        </CardContent>
      </Card>

      <Dialog open={aprovarTudoOpen} onOpenChange={(o)=>{ if(aprovarTudoRunning) return; setAprovarTudoOpen(o); if(!o) setAprovarTudoProg(null); }}>
        <DialogContent className="max-w-md bg-[var(--cor-fundo-card)]">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2"><Sparkles className="h-5 w-5 text-emerald-600" /> Aprovar tudo</DialogTitle>
            <DialogDescription className="text-[var(--cor-texto-suave)]">
              {aprovarTudoRunning ? "Processando — não feche esta janela." : <>Isso vai <span className="font-semibold text-emerald-700">aprovar e publicar</span> todos os itens pendentes com os filtros atuais.</>}
              {!aprovarTudoRunning && (()=>{ const n=filtrados.filter(i=>i.status_revisao==="pendente").length; return ` • ${n} na página atual${total>itens.length?` • ${total} no total (todas as páginas serão percorridas)`:""} • ${q?` busca "${q}"`:cat!=="todas"?` categoria ${cat}`:soUrgente||soCluster?"com filtros aplicados":"sem filtros extras"}.` })()}
            </DialogDescription>
          </DialogHeader>
          {aprovarTudoProg && (
            <div className="space-y-2 rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-3">
              <div className="flex justify-between text-xs"><span className="text-[var(--cor-texto-suave)]">{aprovarTudoProg.done} / {aprovarTudoProg.total}</span><span className={aprovarTudoProg.fail?"text-[var(--cor-erro)]":"text-emerald-700"}>{aprovarTudoProg.fail?`${aprovarTudoProg.fail} falhas`:"ok"}</span></div>
              <div className="h-2 overflow-hidden rounded-full bg-[var(--cor-borda)]"><div className="h-full bg-emerald-600 transition-all" style={{width:`${aprovarTudoProg.total?Math.round((aprovarTudoProg.done/aprovarTudoProg.total)*100):0}%`}} /></div>
              <p className="text-xs text-[var(--cor-texto-suave)]">Publicando um a um — aguarde.</p>
            </div>
          )}
          <DialogFooter className="gap-2">
            <Button variant="outline" disabled={aprovarTudoRunning} onClick={()=>setAprovarTudoOpen(false)}>Cancelar</Button>
            <Button disabled={aprovarTudoRunning||!filtrados.some(i=>i.status_revisao==="pendente")} onClick={executarAprovarTudo} className="bg-emerald-600 text-white hover:bg-emerald-700 gap-1.5"><CheckCheck className="h-4 w-4" /> {aprovarTudoRunning?"Aprovando...":"Confirmar — aprovar tudo"}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}