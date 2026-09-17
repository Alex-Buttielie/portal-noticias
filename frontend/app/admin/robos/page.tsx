"use client";
import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Switch } from "@/components/ui/switch";
import { Separator } from "@/components/ui/separator";
import { useAuth } from "@/lib/auth-context";
import * as api from "@/lib/api";

type Fonte = api.FonteRobo;
type Cfg = api.ConfigRobo;
type Exec = api.ExecucaoRobo;

export default function Page(){
  const { token } = useAuth();
  const [tab,setTab]=useState("fontes");
  const [err,setErr]=useState<string|null>(null);
  const [ok,setOk]=useState<string|null>(null);

  const [fontes,setFontes]=useState<Fonte[]>([]); const [loadingF,setLoadingF]=useState(false);
  const [nome,setNome]=useState(""); const [url,setUrl]=useState(""); const [cat,setCat]=useState(""); const [ativo,setAtivo]=useState(true);
  const [editId,setEditId]=useState<number|null>(null); const [editNome,setEditNome]=useState(""); const [editUrl,setEditUrl]=useState(""); const [editCat,setEditCat]=useState(""); const [editAtivo,setEditAtivo]=useState(true);

  const [cfg,setCfg]=useState<Cfg|null>(null); const [loadingC,setLoadingC]=useState(false); const [savingC,setSavingC]=useState(false);
  const [execs,setExecs]=useState<Exec[]>([]); const [loadingE,setLoadingE]=useState(false); const [execLoading,setExecLoading]=useState(false); const [lastExec,setLastExec]=useState<Exec|null>(null);

  const tk = token||"";

  const carregarFontes=async()=>{
    setErr(null); setLoadingF(true);
    try{
      const r=await api.robosListarFontes(tk);
      setFontes(r);
      if(!r.length) setOk("Nenhuma fonte cadastrada — crie a primeira abaixo.");
    }catch(e:any){
      setErr(e?.message||"Falha ao listar fontes (API offline — usando mock)");
      setFontes([{id:1,nome:"G1",url:"https://g1.globo.com/rss/g1/",ativo:true,categoria_padrao:"geral",criado_em:new Date().toISOString(),atualizado_em:new Date().toISOString()},{id:2,nome:"UOL",url:"https://rss.uol.com.br/feed/noticias.xml",ativo:true,categoria_padrao:"geral",criado_em:new Date().toISOString(),atualizado_em:new Date().toISOString()}]);
    } finally{ setLoadingF(false); }
  };
  const carregarCfg=async()=>{
    setErr(null); setLoadingC(true);
    try{ const r=await api.robosObterConfig(tk); setCfg(r); }
    catch(e:any){ setErr(e?.message||"Falha ao carregar configuração"); }
    finally{ setLoadingC(false); }
  };
  const carregarExecs=async()=>{
    setErr(null); setLoadingE(true);
    try{ const r=await api.robosListarExecucoes(tk); setExecs(r); }
    catch(e:any){ setErr(e?.message||"Falha ao listar execuções"); setExecs([]); }
    finally{ setLoadingE(false); }
  };
  useEffect(()=>{ if(tk){ carregarFontes(); carregarCfg(); carregarExecs(); } },[tk]);

  const criarFonte=async()=>{
    setErr(null); setOk(null);
    if(!nome.trim()||!url.trim()){ setErr("Nome e URL são obrigatórios."); return; }
    try{
      await api.robosCriarFonte(tk,{nome:nome.trim(),url:url.trim(),ativo,categoria_padrao:cat.trim()});
      setNome(""); setUrl(""); setCat(""); setAtivo(true); setOk("Fonte criada.");
      await carregarFontes();
    }catch(e:any){ setErr(e?.message||"Falha ao criar fonte."); }
  };
  const iniciarEdicao=(f:Fonte)=>{
    setEditId(f.id); setEditNome(f.nome); setEditUrl(f.url); setEditCat(f.categoria_padrao||""); setEditAtivo(f.ativo);
  };
  const salvarEdicao=async()=>{
    if(editId==null) return;
    setErr(null);
    try{
      await api.robosAtualizarFonte(tk,editId,{nome:editNome.trim(),url:editUrl.trim(),categoria_padrao:editCat.trim(),ativo:editAtivo});
      setEditId(null); setOk("Fonte atualizada."); await carregarFontes();
    }catch(e:any){ setErr(e?.message||"Falha ao atualizar."); }
  };
  const toggleAtivo=async(f:Fonte)=>{
    try{ await api.robosAtualizarFonte(tk,f.id,{ativo:!f.ativo}); await carregarFontes(); setOk(`${f.nome} ${!f.ativo?"ativado":"desativado"}.`); }
    catch(e:any){ setErr(e?.message||"Falha ao alternar."); }
  };
  const removerFonte=async(id:number)=>{
    if(!confirm("Remover esta fonte?")) return;
    try{ await api.robosRemoverFonte(tk,id); setOk("Fonte removida."); await carregarFontes(); }
    catch(e:any){ setErr(e?.message||"Falha ao remover."); }
  };
  const salvarCfg=async()=>{
    if(!cfg) return;
    setSavingC(true); setErr(null); setOk(null);
    try{
      const r=await api.robosSalvarConfig(tk,{
        intervalo_minutos: cfg.intervalo_minutos, ativo: cfg.ativo, categorias_sensiveis: cfg.categorias_sensiveis,
        limiar_fontes_alta_relevancia: cfg.limiar_fontes_alta_relevancia,
        dedup_limiar_similaridade: cfg.dedup_limiar_similaridade, dedup_janela_horas: cfg.dedup_janela_horas, dedup_max_itens: cfg.dedup_max_itens,
        resumo_similaridade_maxima: cfg.resumo_similaridade_maxima, resumo_trecho_copiado_maximo: cfg.resumo_trecho_copiado_maximo, dedup_cluster_sempre_exige_revisao: cfg.dedup_cluster_sempre_exige_revisao,
        llm_model: cfg.llm_model, llm_api_base_url: cfg.llm_api_base_url, llm_tamanho_lote: cfg.llm_tamanho_lote, llm_max_tokens_por_item: cfg.llm_max_tokens_por_item,
        llm_teto_gasto_diario_usd: cfg.llm_teto_gasto_diario_usd, llm_preco_por_1k_tokens: cfg.llm_preco_por_1k_tokens, llm_timeout_segundos: cfg.llm_timeout_segundos,
      });
      setCfg(r); setOk("Configuração salva.");
    }catch(e:any){ setErr(e?.message||"Falha ao salvar configuração."); }
    finally{ setSavingC(false); }
  };
  const executar=async()=>{
    setExecLoading(true); setErr(null); setOk(null);
    try{
      const r=await api.robosExecutar(tk);
      setLastExec(r); setOk(`Ingestão disparada — ${r.total_itens_ingeridos} itens, ${r.total_grupos_formados} grupos.`);
      await carregarExecs();
    }catch(e:any){ setErr(e?.message||"Falha ao executar robôs."); }
    finally{ setExecLoading(false); }
  };

  const setCfgField=<K extends keyof Cfg>(k:K,v:Cfg[K])=> setCfg((prev)=> prev?{...prev,[k]:v}:prev);

  return (
    <div className="space-y-4">
      <Card className="bento">
        <CardHeader>
          <CardTitle>Robôs — painel de controle total</CardTitle>
          <CardDescription className="text-[var(--cor-texto-suave)]">Manipule, configure, execute e monitore toda a ingestão. Singleton de configuração (pk=1), fontes RSS, execuções e disparo manual.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex flex-wrap gap-2">
            <Button onClick={executar} disabled={execLoading||!tk} className="min-h-[44px] bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]">{execLoading?"Executando...":"Executar robôs agora"}</Button>
            <Button variant="outline" onClick={()=>{carregarFontes();carregarCfg();carregarExecs();}} className="min-h-[44px]">Recarregar tudo</Button>
            {!tk&&<Badge variant="outline" className="border-[var(--cor-erro)] text-[var(--cor-erro)]">Faça login como admin</Badge>}
          </div>
          {err&&<p className="rounded-md border border-[var(--cor-erro)] bg-[var(--cor-erro-suave)] px-3 py-2 text-sm text-[var(--cor-erro)]">{err}</p>}
          {ok&&<p className="rounded-md border border-[var(--cor-sucesso)] bg-[var(--cor-sucesso-suave)] px-3 py-2 text-sm text-[var(--cor-sucesso)]">{ok}</p>}
          {lastExec&&(
            <div className="rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-3 text-xs">
              <p className="font-medium text-[var(--cor-texto)]">Última execução — {new Date(lastExec.executado_em).toLocaleString("pt-BR")}</p>
              <p className="text-[var(--cor-texto-suave)]">Itens: {lastExec.total_itens_ingeridos} · Grupos: {lastExec.total_grupos_formados} · Duplicatas: {lastExec.total_duplicatas_agrupadas} · Chamadas LLM: {lastExec.chamadas_summarization_provider} · Custo: {lastExec.custo_estimado_summarization_usd??"—"}</p>
              <p className="text-[var(--cor-texto-suave)]">Por fonte: {JSON.stringify(lastExec.itens_por_fonte)} {Object.keys(lastExec.erros_por_fonte||{}).length?`· Erros: ${JSON.stringify(lastExec.erros_por_fonte)}`:""}</p>
            </div>
          )}
        </CardContent>
      </Card>

      <Tabs value={tab} onValueChange={setTab} className="w-full">
        <TabsList className="flex w-full flex-wrap justify-start gap-1 bg-[var(--cor-fundo-elevado)] p-1">
          <TabsTrigger value="fontes">Fontes ({fontes.length})</TabsTrigger>
          <TabsTrigger value="config">Configuração</TabsTrigger>
          <TabsTrigger value="execucoes">Execuções ({execs.length})</TabsTrigger>
        </TabsList>

        <TabsContent value="fontes" className="space-y-3 mt-3">
          <Card className="bento">
            <CardHeader><CardTitle className="text-base">Fontes RSS</CardTitle><CardDescription className="text-[var(--cor-texto-suave)]">CRUD completo — nome, URL, ativo, categoria padrão. Toggle rápido e edição inline.</CardDescription></CardHeader>
            <CardContent className="space-y-3">
              <div className="flex gap-2">
                <Button size="sm" onClick={carregarFontes} disabled={loadingF} variant="outline" className="min-h-[36px]">{loadingF?"Carregando...":"Atualizar"}</Button>
                <Badge variant="outline" className="border-[var(--cor-borda)]">{fontes.filter(f=>f.ativo).length} ativas / {fontes.length} total</Badge>
              </div>
              <div className="grid gap-2">
                {fontes.map((f)=> (
                  <div key={f.id} className="rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-3">
                    {editId===f.id? (
                      <div className="space-y-2">
                        <div className="grid gap-2 md:grid-cols-2">
                          <div><Label>Nome</Label><Input value={editNome} onChange={e=>setEditNome(e.target.value)} /></div>
                          <div><Label>URL</Label><Input value={editUrl} onChange={e=>setEditUrl(e.target.value)} /></div>
                        </div>
                        <div className="grid gap-2 md:grid-cols-[1fr_auto]">
                          <div><Label>Categoria padrão</Label><Input value={editCat} onChange={e=>setEditCat(e.target.value)} placeholder="geral" /></div>
                          <div className="flex items-end gap-2">
                            <Label className="mb-2">Ativo</Label><Switch checked={editAtivo} onCheckedChange={setEditAtivo} />
                          </div>
                        </div>
                        <div className="flex gap-2">
                          <Button size="sm" onClick={salvarEdicao} className="bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]">Salvar</Button>
                          <Button size="sm" variant="ghost" onClick={()=>setEditId(null)}>Cancelar</Button>
                        </div>
                      </div>
                    ):(
                      <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                        <div className="min-w-0">
                          <div className="flex flex-wrap items-center gap-2">
                            <p className="font-medium text-[var(--cor-texto)] truncate">{f.nome}</p>
                            <Badge variant={f.ativo?"default":"outline"} className={f.ativo?"bg-[var(--cor-sucesso)] text-[var(--cor-texto-invertido)]":"border-[var(--cor-borda)]"}>{f.ativo?"ativo":"inativo"}</Badge>
                            {f.categoria_padrao&&<Badge variant="outline" className="border-[var(--cor-borda)]">{f.categoria_padrao}</Badge>}
                          </div>
                          <p className="truncate text-xs text-[var(--cor-texto-suave)]">{f.url}</p>
                          <p className="text-xs text-[var(--cor-texto-suave)]">Atualizado: {new Date(f.atualizado_em).toLocaleString("pt-BR")}</p>
                        </div>
                        <div className="flex flex-wrap gap-1">
                          <Button size="sm" variant="outline" onClick={()=>toggleAtivo(f)}>{f.ativo?"Desativar":"Ativar"}</Button>
                          <Button size="sm" variant="outline" onClick={()=>iniciarEdicao(f)}>Editar</Button>
                          <Button size="sm" variant="destructive" onClick={()=>removerFonte(f.id)}>Remover</Button>
                        </div>
                      </div>
                    )}
                  </div>
                ))}
                {!fontes.length&&!loadingF&&<p className="text-sm text-[var(--cor-texto-suave)]">Nenhuma fonte — crie abaixo.</p>}
              </div>
              <Separator />
              <div className="rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo)] p-3 space-y-3">
                <p className="text-sm font-medium text-[var(--cor-texto)]">Nova fonte</p>
                <div className="grid gap-3 md:grid-cols-2">
                  <div className="space-y-1"><Label>Nome *</Label><Input value={nome} onChange={e=>setNome(e.target.value)} placeholder="Ex: G1" /></div>
                  <div className="space-y-1"><Label>URL *</Label><Input value={url} onChange={e=>setUrl(e.target.value)} placeholder="https://..." /></div>
                </div>
                <div className="grid gap-3 md:grid-cols-[1fr_auto] items-end">
                  <div className="space-y-1"><Label>Categoria padrão</Label><Input value={cat} onChange={e=>setCat(e.target.value)} placeholder="geral / politica / economia" /></div>
                  <div className="flex items-center gap-2 pb-2"><Label>Ativo</Label><Switch checked={ativo} onCheckedChange={setAtivo} /></div>
                </div>
                <Button onClick={criarFonte} disabled={!nome.trim()||!url.trim()} className="min-h-[44px] bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]">Criar fonte</Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="config" className="space-y-3 mt-3">
          <Card className="bento">
            <CardHeader><CardTitle className="text-base">Configuração dos robôs</CardTitle><CardDescription className="text-[var(--cor-texto-suave)]">Singleton pk=1 — GET/PATCH em /api/admin/robos/config/. Todos os campos editáveis e validados pelo backend.</CardDescription></CardHeader>
            <CardContent className="space-y-4">
              <div className="flex gap-2">
                <Button size="sm" variant="outline" onClick={carregarCfg} disabled={loadingC}>{loadingC?"Carregando...":"Recarregar"}</Button>
                <Button size="sm" onClick={salvarCfg} disabled={savingC||!cfg||loadingC} className="bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]">{savingC?"Salvando...":"Salvar configuração"}</Button>
                {cfg&&<Badge variant="outline" className="border-[var(--cor-borda)]">Atualizado: {new Date(cfg.atualizado_em).toLocaleString("pt-BR")}</Badge>}
              </div>
              {!cfg? <p className="text-sm text-[var(--cor-texto-suave)]">{loadingC?"Carregando...":"Sem configuração — verifique login admin."}</p> : (
                <>
                  <div className="rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-3 space-y-3">
                    <p className="text-xs tracking-widest text-[var(--cor-texto-suave)]">GERAL</p>
                    <div className="grid gap-3 md:grid-cols-3">
                      <div className="space-y-1"><Label>Intervalo (min) 1-1440</Label><Input type="number" min={1} max={1440} value={cfg.intervalo_minutos} onChange={e=>setCfgField("intervalo_minutos", Math.max(1, Math.min(1440, Number(e.target.value)||15)))} /></div>
                      <div className="flex items-end gap-2 pb-2"><Label>Ativo</Label><Switch checked={cfg.ativo} onCheckedChange={(v)=>setCfgField("ativo",v)} /></div>
                      <div className="flex items-end gap-2 pb-2"><Label>Cluster sempre exige revisão</Label><Switch checked={cfg.dedup_cluster_sempre_exige_revisao} onCheckedChange={(v)=>setCfgField("dedup_cluster_sempre_exige_revisao",v)} /></div>
                    </div>
                    <div className="space-y-1"><Label>Categorias sensíveis (vírgula)</Label><Input value={cfg.categorias_sensiveis} onChange={e=>setCfgField("categorias_sensiveis",e.target.value)} placeholder="política,economia,segurança pública" /></div>
                    <div className="space-y-1"><Label>Limiar fontes alta relevância</Label><Input type="number" min={1} value={cfg.limiar_fontes_alta_relevancia} onChange={e=>setCfgField("limiar_fontes_alta_relevancia", Number(e.target.value)||3)} /></div>
                  </div>

                  <div className="rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-3 space-y-3">
                    <p className="text-xs tracking-widest text-[var(--cor-texto-suave)]">DEDUP / CURADORIA</p>
                    <div className="grid gap-3 md:grid-cols-3">
                      <div className="space-y-1"><Label>Limiar similaridade 0-1</Label><Input type="number" step="0.01" min={0} max={1} value={cfg.dedup_limiar_similaridade} onChange={e=>setCfgField("dedup_limiar_similaridade", Number(e.target.value))} /></div>
                      <div className="space-y-1"><Label>Janela horas</Label><Input type="number" step="0.5" value={cfg.dedup_janela_horas} onChange={e=>setCfgField("dedup_janela_horas", Number(e.target.value))} /></div>
                      <div className="space-y-1"><Label>Max itens recentes</Label><Input type="number" value={cfg.dedup_max_itens} onChange={e=>setCfgField("dedup_max_itens", Number(e.target.value))} /></div>
                    </div>
                    <div className="grid gap-3 md:grid-cols-2">
                      <div className="space-y-1"><Label>Resumo similaridade máxima 0-1</Label><Input type="number" step="0.01" min={0} max={1} value={cfg.resumo_similaridade_maxima} onChange={e=>setCfgField("resumo_similaridade_maxima", Number(e.target.value))} /></div>
                      <div className="space-y-1"><Label>Trecho copiado máximo 0-1</Label><Input type="number" step="0.01" min={0} max={1} value={cfg.resumo_trecho_copiado_maximo} onChange={e=>setCfgField("resumo_trecho_copiado_maximo", Number(e.target.value))} /></div>
                    </div>
                  </div>

                  <div className="rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-3 space-y-3">
                    <p className="text-xs tracking-widest text-[var(--cor-texto-suave)]">LLM / SUMMARIZATION</p>
                    <div className="grid gap-3 md:grid-cols-2">
                      <div className="space-y-1"><Label>Modelo</Label><Input value={cfg.llm_model} onChange={e=>setCfgField("llm_model",e.target.value)} placeholder="gpt-4o-mini" /></div>
                      <div className="space-y-1"><Label>API Base URL</Label><Input value={cfg.llm_api_base_url} onChange={e=>setCfgField("llm_api_base_url",e.target.value)} placeholder="https://api.openai.com/v1" /></div>
                    </div>
                    <div className="grid gap-3 md:grid-cols-3">
                      <div className="space-y-1"><Label>Tamanho lote</Label><Input type="number" value={cfg.llm_tamanho_lote} onChange={e=>setCfgField("llm_tamanho_lote", Number(e.target.value))} /></div>
                      <div className="space-y-1"><Label>Max tokens / item</Label><Input type="number" value={cfg.llm_max_tokens_por_item} onChange={e=>setCfgField("llm_max_tokens_por_item", Number(e.target.value))} /></div>
                      <div className="space-y-1"><Label>Timeout (s)</Label><Input type="number" value={cfg.llm_timeout_segundos} onChange={e=>setCfgField("llm_timeout_segundos", Number(e.target.value))} /></div>
                    </div>
                    <div className="grid gap-3 md:grid-cols-2">
                      <div className="space-y-1"><Label>Teto gasto diário USD</Label><Input type="number" step="0.1" value={cfg.llm_teto_gasto_diario_usd} onChange={e=>setCfgField("llm_teto_gasto_diario_usd", Number(e.target.value))} /></div>
                      <div className="space-y-1"><Label>Preço por 1k tokens USD</Label><Input type="number" step="0.01" value={cfg.llm_preco_por_1k_tokens} onChange={e=>setCfgField("llm_preco_por_1k_tokens", Number(e.target.value))} /></div>
                    </div>
                    <Button onClick={salvarCfg} disabled={savingC} className="min-h-[44px] bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)] w-full md:w-auto">{savingC?"Salvando...":"Salvar configuração"}</Button>
                  </div>
                </>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="execucoes" className="space-y-3 mt-3">
          <Card className="bento">
            <CardHeader><CardTitle className="text-base">Execuções</CardTitle><CardDescription className="text-[var(--cor-texto-suave)]">Histórico das últimas 50 ingestões — itens por fonte, erros, grupos, duplicatas, custo LLM.</CardDescription></CardHeader>
            <CardContent className="space-y-3">
              <div className="flex flex-wrap gap-2">
                <Button size="sm" variant="outline" onClick={carregarExecs} disabled={loadingE}>{loadingE?"Carregando...":"Atualizar"}</Button>
                <Button size="sm" onClick={executar} disabled={execLoading} className="bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]">{execLoading?"Executando...":"Executar agora"}</Button>
              </div>
              <div className="grid gap-2">
                {execs.map((ex)=> (
                  <div key={ex.id} className="rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge variant="outline" className="border-[var(--cor-borda)]">#{ex.id}</Badge>
                      <span className="text-xs text-[var(--cor-texto-suave)]">{new Date(ex.executado_em).toLocaleString("pt-BR")}</span>
                      <Badge className="bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]">{ex.total_itens_ingeridos} itens</Badge>
                      <Badge variant="outline" className="border-[var(--cor-borda)]">{ex.total_grupos_formados} grupos</Badge>
                      <Badge variant="outline" className="border-[var(--cor-borda)]">{ex.total_duplicatas_agrupadas} dup</Badge>
                    </div>
                    <p className="mt-1 text-xs text-[var(--cor-texto-suave)]">LLM: {ex.chamadas_summarization_provider} chamadas · {ex.tokens_utilizados_summarization??"—"} tokens · ${ex.custo_estimado_summarization_usd??"—"}</p>
                    <p className="text-xs text-[var(--cor-texto-suave)] break-all">Por fonte: {JSON.stringify(ex.itens_por_fonte)}</p>
                    {Object.keys(ex.erros_por_fonte||{}).length>0&&<p className="text-xs text-[var(--cor-erro)] break-all">Erros: {JSON.stringify(ex.erros_por_fonte)}</p>}
                  </div>
                ))}
                {!execs.length&&!loadingE&&<p className="text-sm text-[var(--cor-texto-suave)]">Nenhuma execução ainda — clique em Executar agora.</p>}
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
