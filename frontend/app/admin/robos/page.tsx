"use client";
import { useEffect, useState } from "react";
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
import Badge from "@/components/Badge";
import { Button } from "@/components/ui/Button";
import { CampoTexto } from "@/components/ui/FormField";
import { DataTable } from "@/components/ui/Data";
import { ErrorState, SkeletonLista } from "@/components/ui/Estados";

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

  const [novaFonte, setNovaFonte] = useState({ nome: "", url: "", categoria_padrao: "", ativo: true });
  const [editFonte, setEditFonte] = useState<api.FonteRobo | null>(null);
  const [cfgForm, setCfgForm] = useState<Partial<api.ConfigRobo>>({});
  const [msg, setMsg] = useState<string | null>(null);

  useEffect(() => {
    if (configQuery.data) setCfgForm(configQuery.data);
  }, [configQuery.data]);

  async function criar() {
    try {
      await criarFonte.mutateAsync(novaFonte);
      setNovaFonte({ nome: "", url: "", categoria_padrao: "", ativo: true });
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

  async function remover(id: number) {
    if (!window.confirm("Remover esta fonte?")) return;
    try {
      await removerFonte.mutateAsync(id);
    } catch (e) {
      notificar(e instanceof api.ApiError ? e.message : "Erro ao remover.", "erro");
    }
  }

  async function alternarAtiva(fonte: api.FonteRobo) {
    try {
      await salvarFonte.mutateAsync({ id: fonte.id, dados: { ativo: !fonte.ativo } });
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
    try {
      const r = await executar.mutateAsync();
      setMsg(`Execução #${r.id} concluída: ${r.total_itens_ingeridos} itens.`);
    } catch (e) {
      notificar(e instanceof api.ApiError ? e.message : "Erro ao executar.", "erro");
    }
  }

  const carregando = fontesQuery.isLoading || configQuery.isLoading || execsQuery.isLoading;
  const erro = fontesQuery.isError || configQuery.isError || execsQuery.isError;

  if (!token) return <p className="texto-suave">Carregando...</p>;

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 12 }}>
        <h1>Robôs — Configuração</h1>
        <Button carregando={executar.isPending} onClick={() => void executarAgora()}>
          Executar agora
        </Button>
      </div>
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
        <p className="mensagem-sucesso" onClick={() => setMsg(null)} style={{ cursor: "pointer" }}>
          {msg} (clique para fechar)
        </p>
      )}
      {carregando && <SkeletonLista quantidade={2} />}

      {!carregando && !erro && (
        <>
          <section style={{ marginTop: 24 }}>
            <h2>Fontes RSS</h2>
            <div className="controles-feed">
              <CampoTexto id="fonte-nome" rotulo="Nome (ex: G1)" value={novaFonte.nome} onChange={(e) => setNovaFonte({ ...novaFonte, nome: e.target.value })} />
              <CampoTexto id="fonte-url" rotulo="URL https://" value={novaFonte.url} onChange={(e) => setNovaFonte({ ...novaFonte, url: e.target.value })} />
              <CampoTexto
                id="fonte-categoria"
                rotulo="Categoria padrão (opcional)"
                value={novaFonte.categoria_padrao}
                onChange={(e) => setNovaFonte({ ...novaFonte, categoria_padrao: e.target.value })}
              />
              <Button onClick={() => void criar()} carregando={criarFonte.isPending}>
                Adicionar
              </Button>
            </div>
            <DataTable
              legenda="Fontes RSS"
              linhas={fontesQuery.data ?? []}
              colunas={[
                {
                  cabecalho: "Nome",
                  render: (f) =>
                    editFonte?.id === f.id ? (
                      <input aria-label="Nome da fonte" value={editFonte.nome} onChange={(e) => setEditFonte({ ...editFonte, nome: e.target.value })} />
                    ) : (
                      f.nome
                    ),
                },
                {
                  cabecalho: "URL",
                  render: (f) =>
                    editFonte?.id === f.id ? (
                      <input aria-label="URL da fonte" value={editFonte.url} onChange={(e) => setEditFonte({ ...editFonte, url: e.target.value })} style={{ width: "100%" }} />
                    ) : (
                      <a href={f.url} target="_blank" rel="noreferrer">
                        {f.url}
                      </a>
                    ),
                },
                {
                  cabecalho: "Cat.",
                  render: (f) =>
                    editFonte?.id === f.id ? (
                      <input aria-label="Categoria padrão" value={editFonte.categoria_padrao} onChange={(e) => setEditFonte({ ...editFonte, categoria_padrao: e.target.value })} style={{ width: 100 }} />
                    ) : (
                      f.categoria_padrao || "—"
                    ),
                },
                {
                  cabecalho: "Ativo",
                  render: (f) => (
                    <Button variante={f.ativo ? "primaria" : "secundaria"} tamanho="pequeno" onClick={() => void alternarAtiva(f)}>
                      {f.ativo ? "ativo" : "inativo"}
                    </Button>
                  ),
                },
                {
                  cabecalho: "Ações",
                  render: (f) => (
                    <span style={{ display: "flex", gap: 6 }}>
                      {editFonte?.id === f.id ? (
                        <>
                          <Button tamanho="pequeno" onClick={() => void salvarEdicao()}>
                            Salvar
                          </Button>
                          <Button variante="secundaria" tamanho="pequeno" onClick={() => setEditFonte(null)}>
                            Cancelar
                          </Button>
                        </>
                      ) : (
                        <>
                          <Button variante="secundaria" tamanho="pequeno" onClick={() => setEditFonte(f)}>
                            Editar
                          </Button>
                          <Button variante="secundaria" tamanho="pequeno" onClick={() => void remover(f.id)}>
                            Remover
                          </Button>
                        </>
                      )}
                    </span>
                  ),
                },
              ]}
            />
            {(fontesQuery.data?.length ?? 0) === 0 && (
              <p className="texto-suave">Nenhuma fonte. Cadastradas no DB sobrescrevem as de settings; se vazias, usam as 4 padrão.</p>
            )}
          </section>

          <section style={{ marginTop: 32 }}>
            <h2>Parâmetros do robô</h2>
            <p className="texto-suave">
              Valores editáveis viram padrão da próxima ingestão; se o registro não existir ainda, o sistema usa os
              defaults de settings.py.
            </p>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(260px,1fr))", gap: 12, marginTop: 12 }}>
              <CampoTexto id="cfg-intervalo" rotulo="Intervalo (min)" type="number" value={cfgForm.intervalo_minutos ?? ""} onChange={(e) => setCfgForm({ ...cfgForm, intervalo_minutos: Number(e.target.value) })} />
              <CampoTexto id="cfg-categorias" rotulo="Categorias sensíveis (vírgula)" value={cfgForm.categorias_sensiveis ?? ""} onChange={(e) => setCfgForm({ ...cfgForm, categorias_sensiveis: e.target.value })} />
              <CampoTexto id="cfg-limiar" rotulo="Limiar fontes alta relevância" type="number" value={cfgForm.limiar_fontes_alta_relevancia ?? ""} onChange={(e) => setCfgForm({ ...cfgForm, limiar_fontes_alta_relevancia: Number(e.target.value) })} />
              <CampoTexto id="cfg-dedup-limiar" rotulo="Dedup limiar (0-1)" type="number" step="0.01" value={cfgForm.dedup_limiar_similaridade ?? ""} onChange={(e) => setCfgForm({ ...cfgForm, dedup_limiar_similaridade: Number(e.target.value) })} />
              <CampoTexto id="cfg-dedup-janela" rotulo="Dedup janela (h)" type="number" step="0.5" value={cfgForm.dedup_janela_horas ?? ""} onChange={(e) => setCfgForm({ ...cfgForm, dedup_janela_horas: Number(e.target.value) })} />
              <CampoTexto id="cfg-dedup-max" rotulo="Dedup max itens" type="number" value={cfgForm.dedup_max_itens ?? ""} onChange={(e) => setCfgForm({ ...cfgForm, dedup_max_itens: Number(e.target.value) })} />
              <CampoTexto id="cfg-resumo-sim" rotulo="Resumo similaridade max (0-1)" type="number" step="0.01" value={cfgForm.resumo_similaridade_maxima ?? ""} onChange={(e) => setCfgForm({ ...cfgForm, resumo_similaridade_maxima: Number(e.target.value) })} />
              <CampoTexto id="cfg-resumo-trecho" rotulo="Resumo trecho copiado max (0-1)" type="number" step="0.01" value={cfgForm.resumo_trecho_copiado_maximo ?? ""} onChange={(e) => setCfgForm({ ...cfgForm, resumo_trecho_copiado_maximo: Number(e.target.value) })} />
              <CampoTexto id="cfg-llm-model" rotulo="LLM modelo" value={cfgForm.llm_model ?? ""} onChange={(e) => setCfgForm({ ...cfgForm, llm_model: e.target.value })} />
              <CampoTexto id="cfg-llm-url" rotulo="LLM base URL" value={cfgForm.llm_api_base_url ?? ""} onChange={(e) => setCfgForm({ ...cfgForm, llm_api_base_url: e.target.value })} />
              <CampoTexto id="cfg-llm-lote" rotulo="LLM tamanho lote" type="number" value={cfgForm.llm_tamanho_lote ?? ""} onChange={(e) => setCfgForm({ ...cfgForm, llm_tamanho_lote: Number(e.target.value) })} />
              <CampoTexto id="cfg-llm-tokens" rotulo="LLM max tokens/item" type="number" value={cfgForm.llm_max_tokens_por_item ?? ""} onChange={(e) => setCfgForm({ ...cfgForm, llm_max_tokens_por_item: Number(e.target.value) })} />
              <CampoTexto id="cfg-llm-teto" rotulo="LLM teto USD/dia" type="number" step="0.01" value={cfgForm.llm_teto_gasto_diario_usd ?? ""} onChange={(e) => setCfgForm({ ...cfgForm, llm_teto_gasto_diario_usd: Number(e.target.value) })} />
              <CampoTexto id="cfg-llm-preco" rotulo="LLM preço /1k tokens" type="number" step="0.01" value={cfgForm.llm_preco_por_1k_tokens ?? ""} onChange={(e) => setCfgForm({ ...cfgForm, llm_preco_por_1k_tokens: Number(e.target.value) })} />
              <CampoTexto id="cfg-llm-timeout" rotulo="LLM timeout (s)" type="number" value={cfgForm.llm_timeout_segundos ?? ""} onChange={(e) => setCfgForm({ ...cfgForm, llm_timeout_segundos: Number(e.target.value) })} />
            </div>
            <div style={{ display: "flex", gap: 12, marginTop: 12, flexWrap: "wrap" }}>
              <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <input type="checkbox" checked={!!cfgForm.ativo} onChange={(e) => setCfgForm({ ...cfgForm, ativo: e.target.checked })} /> Robô ativo
              </label>
              <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <input type="checkbox" checked={!!cfgForm.dedup_cluster_sempre_exige_revisao} onChange={(e) => setCfgForm({ ...cfgForm, dedup_cluster_sempre_exige_revisao: e.target.checked })} /> Cluster sempre exige revisão
              </label>
            </div>
            <Button style={{ marginTop: 16 }} carregando={salvarConfig.isPending} onClick={() => void salvarConfig.mutateAsync(cfgForm)}>
              Salvar configuração
            </Button>
          </section>

          <section style={{ marginTop: 32 }}>
            <h2>Últimas execuções</h2>
            <DataTable
              legenda="Execuções do robô"
              linhas={execsQuery.data ?? []}
              colunas={[
                { cabecalho: "Quando", render: (r) => new Date(r.executado_em).toLocaleString("pt-BR") },
                { cabecalho: "Itens", render: (r) => String(r.total_itens_ingeridos) },
                { cabecalho: "Grupos", render: (r) => String(r.total_grupos_formados) },
                { cabecalho: "Dedup", render: (r) => String(r.total_duplicatas_agrupadas) },
                { cabecalho: "LLM calls", render: (r) => String(r.chamadas_summarization_provider) },
                { cabecalho: "Custo USD", render: (r) => r.custo_estimado_summarization_usd?.toFixed(4) ?? "—" },
                {
                  cabecalho: "Por fonte / erros",
                  render: (r) => (
                    <span style={{ fontSize: 12 }}>
                      {Object.entries(r.itens_por_fonte).map(([k, v]) => (
                        <span key={k} style={{ marginRight: 8 }}>
                          {k}:{v}
                        </span>
                      ))}
                      {Object.keys(r.erros_por_fonte).length > 0 && (
                        <Badge variante="erro">{Object.keys(r.erros_por_fonte).length} erros</Badge>
                      )}
                    </span>
                  ),
                },
              ]}
            />
            {(execsQuery.data?.length ?? 0) === 0 && (
              <p className="texto-suave">Nenhuma execução registrada.</p>
            )}
          </section>
        </>
      )}
    </div>
  );
}
