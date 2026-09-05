"use client";
import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import * as api from "@/lib/api";

export default function AdminRobosPage() {
  const { token } = useAuth();
  const [fontes, setFontes] = useState<api.FonteRobo[]>([]);
  const [config, setConfig] = useState<api.ConfigRobo | null>(null);
  const [execs, setExecs] = useState<api.ExecucaoRobo[]>([]);
  const [erro, setErro] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(true);

  const [novaFonte, setNovaFonte] = useState({ nome: "", url: "", categoria_padrao: "", ativo: true });
  const [editFonte, setEditFonte] = useState<api.FonteRobo | null>(null);
  const [cfgForm, setCfgForm] = useState<Partial<api.ConfigRobo>>({});
  const [executando, setExecutando] = useState(false);

  async function carregar() {
    if (!token) return;
    setCarregando(true);
    setErro(null);
    try {
      const [f, c, e] = await Promise.all([
        api.robosListarFontes(token),
        api.robosObterConfig(token),
        api.robosListarExecucoes(token),
      ]);
      setFontes(f);
      setConfig(c);
      setCfgForm(c);
      setExecs(e);
    } catch (e) {
      setErro(e instanceof api.ApiError ? e.message : "Erro ao carregar.");
    } finally {
      setCarregando(false);
    }
  }
  useEffect(() => { void carregar(); }, [token]);

  async function criarFonte() {
    if (!token) return;
    try {
      await api.robosCriarFonte(token, novaFonte);
      setNovaFonte({ nome: "", url: "", categoria_padrao: "", ativo: true });
      setMsg("Fonte criada.");
      await carregar();
    } catch (e) { setErro(e instanceof api.ApiError ? e.message : "Erro ao criar fonte."); }
  }
  async function salvarEdit() {
    if (!token || !editFonte) return;
    try {
      await api.robosAtualizarFonte(token, editFonte.id, editFonte);
      setEditFonte(null);
      setMsg("Fonte atualizada.");
      await carregar();
    } catch (e) { setErro(e instanceof api.ApiError ? e.message : "Erro ao atualizar."); }
  }
  async function removerFonte(id: number) {
    if (!token || !confirm("Remover esta fonte?")) return;
    try { await api.robosRemoverFonte(token, id); await carregar(); } catch (e) { setErro(e instanceof api.ApiError ? e.message : "Erro ao remover."); }
  }
  async function toggleFonte(f: api.FonteRobo) {
    if (!token) return;
    try { await api.robosAtualizarFonte(token, f.id, { ativo: !f.ativo } as Partial<api.FonteRobo>); await carregar(); } catch (e) { setErro(e instanceof api.ApiError ? e.message : "Erro."); }
  }
  async function salvarConfig() {
    if (!token) return;
    try {
      const c = await api.robosSalvarConfig(token, cfgForm);
      setConfig(c);
      setCfgForm(c);
      setMsg("Configuração salva.");
    } catch (e) { setErro(e instanceof api.ApiError ? e.message : "Erro ao salvar configuração."); }
  }
  async function executarAgora() {
    if (!token) return;
    setExecutando(true);
    setErro(null);
    try {
      const r = await api.robosExecutar(token);
      setMsg(`Execução #${r.id} concluída: ${r.total_itens_ingeridos} itens.`);
      await carregar();
    } catch (e) { setErro(e instanceof api.ApiError ? e.message : "Erro ao executar."); }
    finally { setExecutando(false); }
  }

  if (carregando) return <p className="texto-suave">Carregando…</p>;

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 12 }}>
        <h1>Robôs — Configuração</h1>
        <button className="botao" onClick={executarAgora} disabled={executando}>{executando ? "Executando…" : "Executar agora"}</button>
      </div>
      {erro && <p className="mensagem-erro">{erro}</p>}
      {msg && <p className="mensagem-sucesso" onClick={() => setMsg(null)} style={{ cursor: "pointer" }}>{msg} (clique para fechar)</p>}

      <section style={{ marginTop: 24 }}>
        <h2>Fontes RSS</h2>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 12 }}>
          <input placeholder="Nome (ex: G1)" value={novaFonte.nome} onChange={(e) => setNovaFonte({ ...novaFonte, nome: e.target.value })} />
          <input placeholder="URL https://" value={novaFonte.url} onChange={(e) => setNovaFonte({ ...novaFonte, url: e.target.value })} style={{ minWidth: 280 }} />
          <input placeholder="Categoria padrão (opcional)" value={novaFonte.categoria_padrao} onChange={(e) => setNovaFonte({ ...novaFonte, categoria_padrao: e.target.value })} />
          <label style={{ display: "flex", alignItems: "center", gap: 6 }}><input type="checkbox" checked={novaFonte.ativo} onChange={(e) => setNovaFonte({ ...novaFonte, ativo: e.target.checked })} /> ativo</label>
          <button className="botao" onClick={criarFonte}>Adicionar</button>
        </div>
        <div className="tabela-wrapper">
          <table className="tabela">
            <thead><tr><th>Nome</th><th>URL</th><th>Cat.</th><th>Ativo</th><th>Ações</th></tr></thead>
            <tbody>
              {fontes.map((f) => (
                <tr key={f.id}>
                  <td>{editFonte?.id === f.id ? <input value={editFonte.nome} onChange={(e) => setEditFonte({ ...editFonte, nome: e.target.value })} /> : f.nome}</td>
                  <td style={{ maxWidth: 320, overflow: "hidden", textOverflow: "ellipsis" }}>{editFonte?.id === f.id ? <input value={editFonte.url} onChange={(e) => setEditFonte({ ...editFonte, url: e.target.value })} style={{ width: "100%" }} /> : <a href={f.url} target="_blank" rel="noreferrer">{f.url}</a>}</td>
                  <td>{editFonte?.id === f.id ? <input value={editFonte.categoria_padrao} onChange={(e) => setEditFonte({ ...editFonte, categoria_padrao: e.target.value })} style={{ width: 100 }} /> : (f.categoria_padrao || "—")}</td>
                  <td><button className={`botao ${f.ativo ? "" : "botao-secundario"}`} onClick={() => toggleFonte(f)}>{f.ativo ? "ativo" : "inativo"}</button></td>
                  <td style={{ display: "flex", gap: 6 }}>
                    {editFonte?.id === f.id ? (
                      <><button className="botao" onClick={salvarEdit}>Salvar</button><button className="botao botao-secundario" onClick={() => setEditFonte(null)}>Cancelar</button></>
                    ) : (
                      <><button className="botao botao-secundario" onClick={() => setEditFonte(f)}>Editar</button><button className="botao botao-secundario" onClick={() => removerFonte(f.id)}>Remover</button></>
                    )}
                  </td>
                </tr>
              ))}
              {!fontes.length && <tr><td colSpan={5} className="texto-suave">Nenhuma fonte. Cadastradas no DB sobrescrevem as de settings; se vazias, usam as 4 padrão.</td></tr>}
            </tbody>
          </table>
        </div>
      </section>

      <section style={{ marginTop: 32 }}>
        <h2>Parâmetros do robô</h2>
        <p className="texto-suave">Valores editáveis viram padrão da próxima ingestão; se o registro não existir ainda, o sistema usa os defaults de settings.py.</p>
        {config && (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(260px,1fr))", gap: 12, marginTop: 12 }}>
            <label>Intervalo (min)<input type="number" value={cfgForm.intervalo_minutos ?? ""} onChange={(e) => setCfgForm({ ...cfgForm, intervalo_minutos: Number(e.target.value) })} /></label>
            <label style={{ display: "flex", alignItems: "center", gap: 8 }}><input type="checkbox" checked={!!cfgForm.ativo} onChange={(e) => setCfgForm({ ...cfgForm, ativo: e.target.checked })} /> Robô ativo</label>
            <label>Categorias sensíveis (vírgula)<input value={cfgForm.categorias_sensiveis ?? ""} onChange={(e) => setCfgForm({ ...cfgForm, categorias_sensiveis: e.target.value })} /></label>
            <label>Limiar fontes alta relevância<input type="number" value={cfgForm.limiar_fontes_alta_relevancia ?? ""} onChange={(e) => setCfgForm({ ...cfgForm, limiar_fontes_alta_relevancia: Number(e.target.value) })} /></label>
            <label>Dedup limiar (0-1)<input type="number" step="0.01" value={cfgForm.dedup_limiar_similaridade ?? ""} onChange={(e) => setCfgForm({ ...cfgForm, dedup_limiar_similaridade: Number(e.target.value) })} /></label>
            <label>Dedup janela (h)<input type="number" step="0.5" value={cfgForm.dedup_janela_horas ?? ""} onChange={(e) => setCfgForm({ ...cfgForm, dedup_janela_horas: Number(e.target.value) })} /></label>
            <label>Dedup max itens<input type="number" value={cfgForm.dedup_max_itens ?? ""} onChange={(e) => setCfgForm({ ...cfgForm, dedup_max_itens: Number(e.target.value) })} /></label>
            <label>Resumo similaridade max (0-1)<input type="number" step="0.01" value={cfgForm.resumo_similaridade_maxima ?? ""} onChange={(e) => setCfgForm({ ...cfgForm, resumo_similaridade_maxima: Number(e.target.value) })} /></label>
            <label>Resumo trecho copiado max (0-1)<input type="number" step="0.01" value={cfgForm.resumo_trecho_copiado_maximo ?? ""} onChange={(e) => setCfgForm({ ...cfgForm, resumo_trecho_copiado_maximo: Number(e.target.value) })} /></label>
            <label style={{ display: "flex", alignItems: "center", gap: 8 }}><input type="checkbox" checked={!!cfgForm.dedup_cluster_sempre_exige_revisao} onChange={(e) => setCfgForm({ ...cfgForm, dedup_cluster_sempre_exige_revisao: e.target.checked })} /> Cluster sempre exige revisão</label>
            <label>LLM modelo<input value={cfgForm.llm_model ?? ""} onChange={(e) => setCfgForm({ ...cfgForm, llm_model: e.target.value })} /></label>
            <label>LLM base URL<input value={cfgForm.llm_api_base_url ?? ""} onChange={(e) => setCfgForm({ ...cfgForm, llm_api_base_url: e.target.value })} /></label>
            <label>LLM tamanho lote<input type="number" value={cfgForm.llm_tamanho_lote ?? ""} onChange={(e) => setCfgForm({ ...cfgForm, llm_tamanho_lote: Number(e.target.value) })} /></label>
            <label>LLM max tokens/item<input type="number" value={cfgForm.llm_max_tokens_por_item ?? ""} onChange={(e) => setCfgForm({ ...cfgForm, llm_max_tokens_por_item: Number(e.target.value) })} /></label>
            <label>LLM teto USD/dia<input type="number" step="0.01" value={cfgForm.llm_teto_gasto_diario_usd ?? ""} onChange={(e) => setCfgForm({ ...cfgForm, llm_teto_gasto_diario_usd: Number(e.target.value) })} /></label>
            <label>LLM preço /1k tokens<input type="number" step="0.01" value={cfgForm.llm_preco_por_1k_tokens ?? ""} onChange={(e) => setCfgForm({ ...cfgForm, llm_preco_por_1k_tokens: Number(e.target.value) })} /></label>
            <label>LLM timeout (s)<input type="number" value={cfgForm.llm_timeout_segundos ?? ""} onChange={(e) => setCfgForm({ ...cfgForm, llm_timeout_segundos: Number(e.target.value) })} /></label>
          </div>
        )}
        <button className="botao" style={{ marginTop: 16 }} onClick={salvarConfig}>Salvar configuração</button>
      </section>

      <section style={{ marginTop: 32 }}>
        <h2>Últimas execuções</h2>
        <div className="tabela-wrapper">
          <table className="tabela">
            <thead><tr><th>Quando</th><th>Itens</th><th>Grupos</th><th>Dedup</th><th>LLM calls</th><th>Custo USD</th><th>Por fonte / erros</th></tr></thead>
            <tbody>
              {execs.map((r) => (
                <tr key={r.id}>
                  <td>{new Date(r.executado_em).toLocaleString("pt-BR")}</td>
                  <td>{r.total_itens_ingeridos}</td>
                  <td>{r.total_grupos_formados}</td>
                  <td>{r.total_duplicatas_agrupadas}</td>
                  <td>{r.chamadas_summarization_provider}</td>
                  <td>{r.custo_estimado_summarization_usd?.toFixed(4) ?? "—"}</td>
                  <td style={{ maxWidth: 320, fontSize: 12 }}>
                    {Object.entries(r.itens_por_fonte).map(([k, v]) => <span key={k} style={{ marginRight: 8 }}>{k}:{v}</span>)}
                    {Object.keys(r.erros_por_fonte).length > 0 && <div style={{ color: "var(--cor-erro)" }}>{Object.entries(r.erros_por_fonte).map(([k, v]) => <div key={k}>{k}: {String(v).slice(0, 120)}</div>)}</div>}
                  </td>
                </tr>
              ))}
              {!execs.length && <tr><td colSpan={7} className="texto-suave">Nenhuma execução registrada.</td></tr>}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
