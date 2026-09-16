"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useAuth } from "@/lib/auth-context";
import { useToast } from "@/components/ToastProvider";
import * as api from "@/lib/api";
import {
  useRobosConfig,
  useRobosCriarFonte,
  useRobosExecutar,
  useRobosExecucoes,
  useRobosFontes,
  useRobosRemoverFonte,
  useRobosSalvarConfig,
  useRobosSalvarFonte,
} from "@/lib/queries";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { CampoTexto } from "@/components/ui/FormField";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { DataTable } from "@/components/ui/Data";
import { ErrorState, SkeletonLista } from "@/components/ui/Estados";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { CheckCircle2 } from "lucide-react";

function formatarDataHora(data: string): string {
  const d = new Date(data);
  if (Number.isNaN(d.getTime())) return data;
  return new Intl.DateTimeFormat("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" }).format(d);
}

export default function AdminRobosPage() {
  const { token } = useAuth();
  const { notificar } = useToast();
  const fontesQuery = useRobosFontes();
  const configQuery = useRobosConfig();
  const execsQuery = useRobosExecucoes();
  const criarFonte = useRobosCriarFonte();
  const salvarFonte = useRobosSalvarFonte();
  const removerFonte = useRobosRemoverFonte();
  const salvarConfig = useRobosSalvarConfig();
  const executar = useRobosExecutar();

  const [novaFonte, setNovaFonte] = useState({ nome: "", url: "", categoria_padrao: "" });
  const [erroNovaFonte, setErroNovaFonte] = useState<string | undefined>(undefined);
  const [editFonte, setEditFonte] = useState<api.FonteRobo | null>(null);
  const [removerAlvo, setRemoverAlvo] = useState<api.FonteRobo | null>(null);
  const [cfgForm, setCfgForm] = useState<Partial<api.ConfigRobo>>({});
  const [msg, setMsg] = useState<string | null>(null);

  useEffect(() => {
    if (configQuery.data) setCfgForm(configQuery.data);
  }, [configQuery.data]);

  async function criar(evento: FormEvent) {
    evento.preventDefault();
    if (!novaFonte.nome.trim()) {
      setErroNovaFonte("Dê um nome à fonte (ex.: G1).");
      document.getElementById("fonte-nome")?.focus();
      return;
    }
    if (!/^https?:\/\/.+/.test(novaFonte.url.trim())) {
      setErroNovaFonte("Informe a URL completa, começando com https://.");
      document.getElementById("fonte-url")?.focus();
      return;
    }
    setErroNovaFonte(undefined);
    try {
      await criarFonte.mutateAsync({ nome: novaFonte.nome.trim(), url: novaFonte.url.trim(), categoria_padrao: novaFonte.categoria_padrao.trim() || undefined, ativo: true });
      setNovaFonte({ nome: "", url: "", categoria_padrao: "" });
      setMsg("Fonte criada.");
    } catch (e) {
      setMsg(null);
      notificar(e instanceof api.ApiError ? e.message : "Erro ao criar fonte.", "erro");
    }
  }

  async function salvarEdicao() {
    if (!editFonte) return;
    try {
      await salvarFonte.mutateAsync({ id: editFonte.id, dados: editFonte });
      setEditFonte(null);
      setMsg("Fonte atualizada.");
    } catch (e) {
      notificar(e instanceof api.ApiError ? e.message : "Erro ao atualizar.", "erro");
    }
  }

  async function confirmarRemocao() {
    if (!removerAlvo) return;
    try {
      await removerFonte.mutateAsync(removerAlvo.id);
      notificar("Fonte removida.", "info");
      setRemoverAlvo(null);
    } catch (e) {
      notificar(e instanceof api.ApiError ? e.message : "Erro ao remover.", "erro");
    }
  }

  async function alternarAtiva(fonte: api.FonteRobo) {
    try {
      await salvarFonte.mutateAsync({ id: fonte.id, dados: { ativo: !fonte.ativo } });
      notificar(fonte.ativo ? "Fonte desativada." : "Fonte ativada.", "info");
    } catch (e) {
      notificar(e instanceof api.ApiError ? e.message : "Erro.", "erro");
    }
  }

  async function salvarConfiguracao() {
    try {
      await salvarConfig.mutateAsync(cfgForm);
      setMsg("Configuração salva.");
    } catch (e) {
      notificar(e instanceof api.ApiError ? e.message : "Erro ao salvar configuração.", "erro");
    }
  }

  async function executarAgora() {
    if (!window.confirm("Executar a ingestão agora? O robô vai buscar as fontes RSS.")) return;
    try {
      const r = await executar.mutateAsync();
      setMsg(`Execução #${r.id} concluída: ${r.total_itens_ingeridos} itens.`);
    } catch (e) {
      notificar(e instanceof api.ApiError ? e.message : "Erro ao executar.", "erro");
    }
  }

  const carregando = fontesQuery.isLoading || configQuery.isLoading || execsQuery.isLoading;
  const erro = fontesQuery.isError || configQuery.isError || execsQuery.isError;

  if (!token) {
    return (
      <div className="mx-auto w-full px-4 py-10">
        <p className="text-sm text-[var(--cor-texto-suave)]">Carregando…</p>
      </div>
    );
  }

  return (
    <section className="grid gap-6" aria-labelledby="admin-robos-titulo">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="grid gap-1">
          <h1 id="admin-robos-titulo" className="font-[var(--fonte-titulo)] text-2xl font-bold tracking-tight text-balance text-[var(--cor-texto)]">
            Robôs
          </h1>
          <p className="text-sm text-[var(--cor-texto-suave)]">Gerencie as fontes RSS, ajuste os parâmetros de ingestão e confira as execuções.</p>
        </div>
        <Button loading={executar.isPending} onClick={() => void executarAgora()}>
          Executar agora
        </Button>
      </div>

      <div aria-live="polite">
        {erro && (
          <ErrorState
            mensagem="Erro ao carregar."
            aoTentarNovamente={() => {
              void fontesQuery.refetch();
              void configQuery.refetch();
              void execsQuery.refetch();
            }}
          />
        )}
        {msg && (
          <Alert variant="success" className="flex items-center justify-between gap-3">
            <span className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 shrink-0" aria-hidden="true" />
              <AlertDescription>{msg}</AlertDescription>
            </span>
            <Button variant="ghost" tamanho="pequeno" onClick={() => setMsg(null)}>
              Fechar
            </Button>
          </Alert>
        )}
      </div>
      {carregando && <SkeletonLista quantidade={2} />}

      {!carregando && !erro && (
        <div className="grid gap-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Fontes RSS</CardTitle>
              <CardDescription>Cadastre e gerencie as fontes que alimentam o portal.</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4">
              <form onSubmit={criar} noValidate className="grid gap-3 rounded-lg border border-[var(--cor-borda)] bg-[var(--cor-fundo)] p-4">
                <div className="flex flex-wrap items-end gap-3">
                  <div className="min-w-[140px] flex-1">
                    <CampoTexto id="fonte-nome" name="fonte-nome" rotulo="Nome (ex.: G1)" autoComplete="off" value={novaFonte.nome} onChange={(e) => setNovaFonte({ ...novaFonte, nome: e.target.value })} />
                  </div>
                  <div className="min-w-[200px] flex-1">
                    <CampoTexto id="fonte-url" name="fonte-url" rotulo="URL https://" type="url" autoComplete="url" placeholder="https://…" value={novaFonte.url} onChange={(e) => setNovaFonte({ ...novaFonte, url: e.target.value })} />
                  </div>
                  <div className="min-w-[160px] flex-1">
                    <CampoTexto id="fonte-categoria" name="fonte-categoria" rotulo="Categoria padrão (opcional)" autoComplete="off" value={novaFonte.categoria_padrao} onChange={(e) => setNovaFonte({ ...novaFonte, categoria_padrao: e.target.value })} />
                  </div>
                  <Button type="submit" loading={criarFonte.isPending} className="h-10">
                    Adicionar
                  </Button>
                </div>
                {erroNovaFonte && (
                  <p role="alert" className="text-xs font-medium text-[var(--cor-erro)]">
                    {erroNovaFonte}
                  </p>
                )}
              </form>
              <div aria-live="polite">
                <DataTable
                  legenda="Fontes RSS"
                  linhas={fontesQuery.data ?? []}
                  colunas={[
                    {
                      cabecalho: "Nome",
                      render: (f) =>
                        editFonte?.id === f.id ? (
                          <Input aria-label="Nome da fonte" value={editFonte.nome} onChange={(e) => setEditFonte({ ...editFonte, nome: e.target.value })} />
                        ) : (
                          f.nome
                        ),
                    },
                    {
                      cabecalho: "URL",
                      render: (f) =>
                        editFonte?.id === f.id ? (
                          <Input aria-label="URL da fonte" value={editFonte.url} onChange={(e) => setEditFonte({ ...editFonte, url: e.target.value })} />
                        ) : (
                          <a href={f.url} target="_blank" rel="noreferrer" className="break-all text-sm text-[var(--cor-primaria)] hover:underline">
                            {f.url}
                          </a>
                        ),
                    },
                    {
                      cabecalho: "Categoria",
                      render: (f) =>
                        editFonte?.id === f.id ? (
                          <Input aria-label="Categoria padrão" value={editFonte.categoria_padrao} onChange={(e) => setEditFonte({ ...editFonte, categoria_padrao: e.target.value })} />
                        ) : (
                          f.categoria_padrao || "—"
                        ),
                    },
                    {
                      cabecalho: "Status",
                      render: (f) => (
                        <Badge variant={f.ativo ? "success" : "secondary"}>{f.ativo ? "ativa" : "inativa"}</Badge>
                      ),
                    },
                    {
                      cabecalho: "Ações",
                      render: (f) => (
                        <span className="flex flex-wrap gap-2">
                          {editFonte?.id === f.id ? (
                            <>
                              <Button tamanho="pequeno" loading={salvarFonte.isPending} onClick={() => void salvarEdicao()}>
                                Salvar
                              </Button>
                              <Button variante="secundaria" tamanho="pequeno" onClick={() => setEditFonte(null)}>
                                Cancelar
                              </Button>
                            </>
                          ) : (
                            <>
                              <Button variante="secundaria" tamanho="pequeno" onClick={() => void alternarAtiva(f)}>
                                {f.ativo ? "Desativar" : "Ativar"}
                              </Button>
                              <Button variante="secundaria" tamanho="pequeno" onClick={() => setEditFonte(f)}>
                                Editar
                              </Button>
                              <Button variante="perigo" tamanho="pequeno" onClick={() => setRemoverAlvo(f)}>
                                Remover
                              </Button>
                            </>
                          )}
                        </span>
                      ),
                    },
                  ]}
                />
              </div>
              {(fontesQuery.data?.length ?? 0) === 0 && (
                <p className="text-sm text-[var(--cor-texto-suave)]">Nenhuma fonte. Cadastradas no DB sobrescrevem as de settings; se vazias, usam as 4 padrão.</p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Parâmetros do robô</CardTitle>
              <CardDescription>Valores editáveis viram padrão da próxima ingestão.</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4">
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                <CampoTexto id="cfg-intervalo" name="cfg-intervalo" rotulo="Intervalo (min)" type="number" value={cfgForm.intervalo_minutos ?? ""} onChange={(e) => setCfgForm({ ...cfgForm, intervalo_minutos: Number(e.target.value) })} />
                <CampoTexto id="cfg-categorias" name="cfg-categorias" rotulo="Categorias sensíveis (vírgula)" value={cfgForm.categorias_sensiveis ?? ""} onChange={(e) => setCfgForm({ ...cfgForm, categorias_sensiveis: e.target.value })} />
                <CampoTexto id="cfg-limiar" name="cfg-limiar" rotulo="Limiar fontes alta relevância" type="number" value={cfgForm.limiar_fontes_alta_relevancia ?? ""} onChange={(e) => setCfgForm({ ...cfgForm, limiar_fontes_alta_relevancia: Number(e.target.value) })} />
                <CampoTexto id="cfg-dedup-limiar" name="cfg-dedup-limiar" rotulo="Dedup limiar (0-1)" type="number" step="0.01" value={cfgForm.dedup_limiar_similaridade ?? ""} onChange={(e) => setCfgForm({ ...cfgForm, dedup_limiar_similaridade: Number(e.target.value) })} />
                <CampoTexto id="cfg-dedup-janela" name="cfg-dedup-janela" rotulo="Dedup janela (h)" type="number" step="0.5" value={cfgForm.dedup_janela_horas ?? ""} onChange={(e) => setCfgForm({ ...cfgForm, dedup_janela_horas: Number(e.target.value) })} />
                <CampoTexto id="cfg-dedup-max" name="cfg-dedup-max" rotulo="Dedup max itens" type="number" value={cfgForm.dedup_max_itens ?? ""} onChange={(e) => setCfgForm({ ...cfgForm, dedup_max_itens: Number(e.target.value) })} />
                <CampoTexto id="cfg-resumo-sim" name="cfg-resumo-sim" rotulo="Resumo similaridade max (0-1)" type="number" step="0.01" value={cfgForm.resumo_similaridade_maxima ?? ""} onChange={(e) => setCfgForm({ ...cfgForm, resumo_similaridade_maxima: Number(e.target.value) })} />
                <CampoTexto id="cfg-resumo-trecho" name="cfg-resumo-trecho" rotulo="Resumo trecho copiado max (0-1)" type="number" step="0.01" value={cfgForm.resumo_trecho_copiado_maximo ?? ""} onChange={(e) => setCfgForm({ ...cfgForm, resumo_trecho_copiado_maximo: Number(e.target.value) })} />
                <CampoTexto id="cfg-llm-model" name="cfg-llm-model" rotulo="LLM modelo" autoComplete="off" value={cfgForm.llm_model ?? ""} onChange={(e) => setCfgForm({ ...cfgForm, llm_model: e.target.value })} />
                <CampoTexto id="cfg-llm-url" name="cfg-llm-url" rotulo="LLM base URL" autoComplete="url" value={cfgForm.llm_api_base_url ?? ""} onChange={(e) => setCfgForm({ ...cfgForm, llm_api_base_url: e.target.value })} />
                <CampoTexto id="cfg-llm-lote" name="cfg-llm-lote" rotulo="LLM tamanho lote" type="number" value={cfgForm.llm_tamanho_lote ?? ""} onChange={(e) => setCfgForm({ ...cfgForm, llm_tamanho_lote: Number(e.target.value) })} />
                <CampoTexto id="cfg-llm-tokens" name="cfg-llm-tokens" rotulo="LLM max tokens/item" type="number" value={cfgForm.llm_max_tokens_por_item ?? ""} onChange={(e) => setCfgForm({ ...cfgForm, llm_max_tokens_por_item: Number(e.target.value) })} />
                <CampoTexto id="cfg-llm-teto" name="cfg-llm-teto" rotulo="LLM teto USD/dia" type="number" step="0.01" value={cfgForm.llm_teto_gasto_diario_usd ?? ""} onChange={(e) => setCfgForm({ ...cfgForm, llm_teto_gasto_diario_usd: Number(e.target.value) })} />
                <CampoTexto id="cfg-llm-preco" name="cfg-llm-preco" rotulo="LLM preço /1k tokens" type="number" step="0.01" value={cfgForm.llm_preco_por_1k_tokens ?? ""} onChange={(e) => setCfgForm({ ...cfgForm, llm_preco_por_1k_tokens: Number(e.target.value) })} />
                <CampoTexto id="cfg-llm-timeout" name="cfg-llm-timeout" rotulo="LLM timeout (s)" type="number" value={cfgForm.llm_timeout_segundos ?? ""} onChange={(e) => setCfgForm({ ...cfgForm, llm_timeout_segundos: Number(e.target.value) })} />
              </div>
              <div className="flex flex-wrap gap-4">
                <div className="flex min-h-[44px] items-center gap-3">
                  <Checkbox
                    id="cfg-ativo"
                    checked={!!cfgForm.ativo}
                    onCheckedChange={(v) => setCfgForm({ ...cfgForm, ativo: v === true })}
                  />
                  <Label htmlFor="cfg-ativo" className="cursor-pointer text-sm font-normal">
                    Robô ativo
                  </Label>
                </div>
                <div className="flex min-h-[44px] items-center gap-3">
                  <Checkbox
                    id="cfg-revisao"
                    checked={!!cfgForm.dedup_cluster_sempre_exige_revisao}
                    onCheckedChange={(v) => setCfgForm({ ...cfgForm, dedup_cluster_sempre_exige_revisao: v === true })}
                  />
                  <Label htmlFor="cfg-revisao" className="cursor-pointer text-sm font-normal">
                    Cluster sempre exige revisão
                  </Label>
                </div>
              </div>
              <Button className="w-fit" loading={salvarConfig.isPending} onClick={() => void salvarConfig.mutateAsync(cfgForm).then(() => setMsg("Configuração salva.")).catch((e: unknown) => notificar(e instanceof api.ApiError ? e.message : "Erro ao salvar configuração.", "erro"))}>
                Salvar configuração
              </Button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Últimas execuções</CardTitle>
            </CardHeader>
            <CardContent>
              <DataTable
                legenda="Execuções do robô"
                linhas={execsQuery.data ?? []}
                colunas={[
                  { cabecalho: "Quando", render: (r) => formatarDataHora(r.executado_em) },
                  { cabecalho: "Itens", render: (r) => String(r.total_itens_ingeridos) },
                  { cabecalho: "Grupos", render: (r) => String(r.total_grupos_formados) },
                  { cabecalho: "Dedup", render: (r) => String(r.total_duplicatas_agrupadas) },
                  { cabecalho: "LLM calls", render: (r) => String(r.chamadas_summarization_provider) },
                  { cabecalho: "Custo USD", render: (r) => r.custo_estimado_summarization_usd?.toFixed(4) ?? "—" },
                  {
                    cabecalho: "Por fonte / erros",
                    render: (r) => (
                      <span className="text-xs">
                        {Object.entries(r.itens_por_fonte).map(([k, v]) => (
                          <span key={k} className="mr-2">
                            {k}:{String(v)}
                          </span>
                        ))}
                        {Object.keys(r.erros_por_fonte).length > 0 && <Badge variant="destructive">{Object.keys(r.erros_por_fonte).length} erros</Badge>}
                      </span>
                    ),
                  },
                ]}
              />
              {(execsQuery.data?.length ?? 0) === 0 && <p className="text-sm text-[var(--cor-texto-suave)]">Nenhuma execução registrada.</p>}
            </CardContent>
          </Card>
        </div>
      )}

      <Dialog open={removerAlvo !== null} onOpenChange={(aberto) => !aberto && setRemoverAlvo(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Remover a fonte “{removerAlvo?.nome}”?</DialogTitle>
            <DialogDescription>
              A fonte deixa de alimentar a ingestão. O histórico já coletado continua no portal. Essa ação não pode
              ser desfeita.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setRemoverAlvo(null)} disabled={removerFonte.isPending}>
              Manter fonte
            </Button>
            <Button variant="destructive" loading={removerFonte.isPending} onClick={() => void confirmarRemocao()}>
              Sim, remover
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </section>
  );
}
