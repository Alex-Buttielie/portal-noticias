"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import * as api from "@/lib/api";
import Tabs from "@/components/Tabs";
import Badge from "@/components/Badge";

function pct(v: number) {
  return `${(v * 100).toFixed(1)}%`;
}
function moeda(v: string | number) {
  const n = typeof v === "string" ? Number(v) : v;
  if (Number.isNaN(n)) return String(v);
  return n.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}
function maxY(series: api.SeriePonto[]) {
  return Math.max(1, ...series.map((p) => p.total));
}
function Sparkline({ serie, cor = "var(--cor-primaria)" }: { serie: api.SeriePonto[]; cor?: string }) {
  if (!serie.length) return <p className="texto-suave">Sem dados no período.</p>;
  const W = 520;
  const H = 96;
  const pad = 12;
  const n = serie.length;
  const m = maxY(serie);
  const xs = serie.map((_, i) => pad + (i * (W - pad * 2)) / Math.max(1, n - 1));
  const ys = serie.map((p) => H - pad - (p.total / m) * (H - pad * 2));
  const d = xs.map((x, i) => `${i === 0 ? "M" : "L"} ${x} ${ys[i]}`).join(" ");
  const area = `${d} L ${xs[n - 1]} ${H - pad} L ${xs[0]} ${H - pad} Z`;
  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={H} role="img" aria-label="Série temporal">
        <rect x={0} y={0} width={W} height={H} rx={10} fill="var(--cor-fundo-card)" />
        {[0, 0.5, 1].map((t) => {
          const y = H - pad - t * (H - pad * 2);
          const v = Math.round(t * m);
          return (
            <g key={t}>
              <line x1={pad} x2={W - pad} y1={y} y2={y} stroke="var(--cor-borda)" strokeDasharray="3 4" />
              <text x={W - pad} y={y - 4} textAnchor="end" fontSize={10} fill="var(--cor-texto-suave)">
                {v}
              </text>
            </g>
          );
        })}
        <path d={area} fill={cor} opacity={0.12} />
        <path d={d} fill="none" stroke={cor} strokeWidth={2.2} strokeLinejoin="round" strokeLinecap="round" />
        {xs.map((x, i) => (
          <circle key={i} cx={x} cy={ys[i]} r={2.6} fill={cor} />
        ))}
      </svg>
      <div className="dashboard-legenda">
        <span className="texto-suave">{serie[0]?.dia}</span>
        <span className="texto-suave">{serie[serie.length - 1]?.dia}</span>
      </div>
    </div>
  );
}

function Barras({ itens, cor = "var(--cor-primaria)" }: { itens: api.DistribuicaoItem[]; cor?: string }) {
  if (!itens.length) return <p className="texto-suave">Sem dados.</p>;
  const m = Math.max(1, ...itens.map((x) => x.total));
  return (
    <div className="barras">
      {itens.map((it) => (
        <div key={it.label} className="barra-linha">
          <span className="barra-rotulo" title={it.label}>
            {it.label}
          </span>
          <div className="barra-trilho">
            <div className="barra-preenchida" style={{ width: `${(it.total / m) * 100}%`, background: cor }} />
          </div>
          <span className="barra-valor">{it.total}</span>
        </div>
      ))}
    </div>
  );
}

function Donut({ itens, size = 140 }: { itens: api.DistribuicaoItem[]; size?: number }) {
  if (!itens.length) return <p className="texto-suave">Sem dados.</p>;
  const total = itens.reduce((a, b) => a + b.total, 0) || 1;
  const cores = ["var(--cor-primaria)", "var(--cor-sucesso)", "var(--cor-premium)", "var(--cor-erro)", "#7c5cff", "#00b8a9", "#888"];
  let acc = 0;
  const r = 52;
  const cx = size / 2;
  const cy = size / 2;
  const circ = 2 * Math.PI * r;
  return (
    <div className="donut-wrap">
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img" aria-label="Distribuição">
        <circle cx={cx} cy={cy} r={r} fill="none" stroke="var(--cor-borda)" strokeWidth={18} />
        {itens.map((it, i) => {
          const frac = it.total / total;
          const len = frac * circ;
          const dash = `${len} ${circ - len}`;
          const offset = circ * 0.25 - acc;
          acc += len;
          return <circle key={it.label} cx={cx} cy={cy} r={r} fill="none" stroke={cores[i % cores.length]} strokeWidth={18} strokeDasharray={dash} strokeDashoffset={offset} />;
        })}
        <circle cx={cx} cy={cy} r={36} fill="var(--cor-fundo-card)" stroke="var(--cor-borda)" />
        <text x={cx} y={cy} textAnchor="middle" dominantBaseline="central" fontSize={13} fontWeight={700} fill="var(--cor-texto)">
          {total}
        </text>
      </svg>
      <div className="donut-legenda">
        {itens.map((it, i) => (
          <span key={it.label} className="donut-legenda-item">
            <span className="donut-bolinha" style={{ background: cores[i % cores.length] }} /> {it.label}: {it.total} ({pct(it.total / total)})
          </span>
        ))}
      </div>
    </div>
  );
}

function KpiCard({ titulo, valor, subtitulo, destaque }: { titulo: string; valor: string; subtitulo?: string; destaque?: string }) {
  return (
    <div className="kpi">
      <div className="kpi-titulo">{titulo}</div>
      <div className="kpi-valor">{valor}</div>
      {subtitulo && <div className="kpi-sub">{subtitulo}</div>}
      {destaque && <Badge variante="neutro">{destaque}</Badge>}
    </div>
  );
}

export default function PaginaAdminMetricas() {
  const router = useRouter();
  const { token, usuario, carregando: carregandoAuth } = useAuth();
  const [dias, setDias] = useState(30);
  const [painel, setPainel] = useState<api.PainelMetricas | null>(null);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    if (carregandoAuth) return;
    if (!token) {
      router.push("/login");
      return;
    }
    if (usuario && usuario.papel !== "admin") {
      setErro("Acesso restrito à administração.");
      setCarregando(false);
      return;
    }
    setCarregando(true);
    setErro(null);
    api
      .obterPainelMetricas(token, dias)
      .then(setPainel)
      .catch((e: unknown) => setErro(e instanceof api.ApiError ? e.message : "Não foi possível carregar o painel."))
      .finally(() => setCarregando(false));
  }, [token, usuario, carregandoAuth, router, dias]);

  const abas = useMemo(() => {
    if (!painel) return [];
    const d = painel.distribuicoes;
    const k = painel.kpis;
    const s = painel.series;
    const f = painel.funil;
    return [
      {
        chave: "overview",
        rotulo: "Visão geral",
        conteudo: (
          <div>
            <div className="kpi-grid">
              <KpiCard titulo="Usuários totais" valor={String(painel.usuarios_cadastrados_total)} subtitulo={`+${painel.usuarios_cadastrados_periodo} no período`} destaque={`${painel.periodo_dias} dias`} />
              <KpiCard titulo="DAU / MAU" valor={`${painel.usuarios_ativos_diarios} / ${painel.usuarios_ativos_mensais}`} subtitulo={`Retenção ${pct(painel.retencao_periodo)}`} />
              <KpiCard titulo="Assinaturas ativas" valor={String(painel.assinaturas_ativas)} subtitulo={`Conversão ${pct(painel.conversao_free_premium)} · Churn ${pct(painel.churn_periodo)}`} />
              <KpiCard titulo="Receita no período" valor={moeda(painel.receita_recorrente_periodo)} subtitulo={`Ticket médio ${moeda(painel.receita_media_por_assinante)} · Renovação ${pct(painel.taxa_renovacao_periodo)}`} />
            </div>

            <div className="dashboard-grid">
              <div className="dashboard-card">
                <h3>Cadastros por dia</h3>
                <Sparkline serie={s.cadastros} cor="var(--cor-primaria)" />
              </div>
              <div className="dashboard-card">
                <h3>Receita por dia (R$)</h3>
                <Sparkline serie={s.receita} cor="var(--cor-sucesso)" />
              </div>
              <div className="dashboard-card">
                <h3>Novas assinaturas por dia</h3>
                <Sparkline serie={s.assinaturas} cor="var(--cor-premium)" />
              </div>
              <div className="dashboard-card">
                <h3>Notícias ingeridas por dia</h3>
                <Sparkline serie={s.noticias} />
              </div>
            </div>

            <div className="dashboard-grid">
              <div className="dashboard-card">
                <h3>Funil — lista → cadastro → premium</h3>
                <div className="funil">
                  <div className="funil-etapa">
                    <span>Lista de espera</span>
                    <strong>{f.lista_espera}</strong>
                  </div>
                  <div className="funil-seta">→ {pct(f.taxa_lista_para_cadastro)} →</div>
                  <div className="funil-etapa">
                    <span>Cadastrados</span>
                    <strong>{f.cadastrados}</strong>
                  </div>
                  <div className="funil-seta">→ {pct(f.taxa_cadastro_para_premium)} →</div>
                  <div className="funil-etapa funil-etapa--destaque">
                    <span>Premium ativos</span>
                    <strong>{f.assinantes}</strong>
                  </div>
                </div>
              </div>
              <div className="dashboard-card">
                <h3>Usuários por papel</h3>
                <Donut itens={d.papel} />
              </div>
              <div className="dashboard-card">
                <h3>Assinaturas por status</h3>
                <Barras itens={d.assinaturas_status} cor="var(--cor-premium)" />
              </div>
            </div>
          </div>
        ),
      },
      {
        chave: "receita",
        rotulo: "Receita & Assinaturas",
        conteudo: (
          <div>
            <div className="kpi-grid">
              <KpiCard titulo="Receita período" valor={moeda(painel.receita_recorrente_periodo)} />
              <KpiCard titulo="Ticket médio" valor={moeda(painel.receita_media_por_assinante)} />
              <KpiCard titulo="Churn" valor={pct(painel.churn_periodo)} subtitulo={`Renovação ${pct(painel.taxa_renovacao_periodo)}`} />
              <KpiCard titulo="Conversão free→premium" valor={pct(painel.conversao_free_premium)} subtitulo={`${painel.assinaturas_ativas} ativas`} />
            </div>
            <div className="dashboard-grid">
              <div className="dashboard-card">
                <h3>Receita por dia</h3>
                <Sparkline serie={s.receita} cor="var(--cor-sucesso)" />
              </div>
              <div className="dashboard-card">
                <h3>Assinaturas criadas por dia</h3>
                <Sparkline serie={s.assinaturas} cor="var(--cor-premium)" />
              </div>
              <div className="dashboard-card">
                <h3>Status das assinaturas</h3>
                <Donut itens={d.assinaturas_status} />
              </div>
              <div className="dashboard-card">
                <h3>B2B — planos das organizações</h3>
                <Barras itens={d.b2b_plano} cor="#7c5cff" />
                <p className="texto-suave">
                  B2B ativas: {k.b2b.ativas} / {k.b2b.total} · Critérios ativos: {k.b2b.criterios_ativos}
                </p>
              </div>
            </div>
            <div className="dashboard-card">
              <h3>Lista de espera por dia</h3>
              <Sparkline serie={s.lista_espera} cor="var(--cor-primaria)" />
              <p className="texto-suave">Total em espera: {k.lista_espera.total}</p>
            </div>
            <div className="dashboard-card">
              <h3>Newsletter</h3>
              <Barras itens={d.newsletter_tipo} cor="#00b8a9" />
              <p className="texto-suave">
                Ativas {k.newsletter.ativas} / {k.newsletter.total}
              </p>
            </div>
          </div>
        ),
      },
      {
        chave: "conteudo",
        rotulo: "Conteúdo & Comunidade",
        conteudo: (
          <div>
            <div className="kpi-grid">
              <KpiCard titulo="Notícias no período" valor={String(k.ingestao.noticias_periodo)} subtitulo={`Pendentes moderação: ${k.ingestao.noticias_pendentes}`} />
              <KpiCard titulo="Taxa aprovação" valor={pct(k.ingestao.taxa_aprovacao)} subtitulo="aprovadas + não aplicável / total" />
              <KpiCard titulo="Publicações" valor={`${k.comunidade.publicacoes_publicadas} / ${k.comunidade.publicacoes_total}`} subtitulo="publicadas / total" />
              <KpiCard titulo="Comentários / Seguidores" valor={`${k.comunidade.comentarios_total} / ${k.comunidade.seguidores_total}`} />
            </div>
            <div className="dashboard-grid">
              <div className="dashboard-card">
                <h3>Notícias por dia</h3>
                <Sparkline serie={s.noticias} />
              </div>
              <div className="dashboard-card">
                <h3>Publicações por dia</h3>
                <Sparkline serie={s.publicacoes} />
              </div>
              <div className="dashboard-card">
                <h3>Comentários por dia</h3>
                <Sparkline serie={s.comentarios} cor="var(--cor-premium)" />
              </div>
              <div className="dashboard-card">
                <h3>Ingestão — custo estimado/dia (USD)</h3>
                <Sparkline serie={s.ingestao_custo} cor="var(--cor-erro)" />
                <p className="texto-suave">Custo no período: ${k.ingestao.custo_periodo.toFixed(4)} · Hoje: ${(painel.custo_llm_hoje_usd ?? 0).toFixed(4)} / teto ${(painel.teto_llm_diario_usd ?? 0).toFixed(2)}</p>
              </div>
            </div>
            <div className="dashboard-grid">
              <div className="dashboard-card">
                <h3>Notícias por categoria</h3>
                <Barras itens={d.noticias_categoria} />
              </div>
              <div className="dashboard-card">
                <h3>Notícias por fonte</h3>
                <Barras itens={d.noticias_fonte} cor="var(--cor-sucesso)" />
              </div>
              <div className="dashboard-card">
                <h3>Status revisão (notícias)</h3>
                <Donut itens={d.noticias_status} />
              </div>
              <div className="dashboard-card">
                <h3>Publicações por status</h3>
                <Donut itens={d.publicacoes_status} />
              </div>
            </div>
          </div>
        ),
      },
      {
        chave: "moderacao",
        rotulo: "Moderação & Operação",
        conteudo: (
          <div>
            <div className="kpi-grid">
              <KpiCard titulo="Denúncias pendentes" valor={String(k.moderacao.denuncias_pendentes)} subtitulo={`Total ${k.moderacao.denuncias_total}`} destaque={k.moderacao.denuncias_pendentes > 0 ? "Ação necessária" : "Em dia"} />
              <KpiCard titulo="Ações de moderação" valor={String(k.moderacao.acoes_total)} />
              <KpiCard titulo="Solicitações credenciamento" valor={String(d.credenciamento_status.reduce((a, b) => a + b.total, 0))} subtitulo="total histórico" />
              <KpiCard titulo="Custo LLM hoje" valor={`$${(painel.custo_llm_hoje_usd ?? 0).toFixed(4)}`} subtitulo={`Teto $${(painel.teto_llm_diario_usd ?? 0).toFixed(2)}${painel.teto_llm_excedido_hoje ? " · EXCEDIDO" : ""}`} />
            </div>
            <div className="dashboard-grid">
              <div className="dashboard-card">
                <h3>Denúncias por status</h3>
                <Donut itens={d.denuncias_status} />
              </div>
              <div className="dashboard-card">
                <h3>Ações por tipo</h3>
                <Barras itens={d.acoes_tipo} cor="var(--cor-erro)" />
              </div>
              <div className="dashboard-card">
                <h3>Credenciamento por status</h3>
                <Donut itens={d.credenciamento_status} />
              </div>
              <div className="dashboard-card">
                <h3>B2B — critérios por tipo</h3>
                <Barras itens={d.criterio_tipo} cor="#7c5cff" />
                <p className="texto-suave">Critérios ativos: {k.b2b.criterios_ativos}</p>
              </div>
            </div>
          </div>
        ),
      },
    ];
  }, [painel]);

  if (carregandoAuth || carregando) return <p className="texto-suave">Carregando métricas…</p>;
  if (erro) return <p className="mensagem-erro">{erro}</p>;
  if (!painel) return <p className="texto-suave">Sem dados.</p>;

  return (
    <div>
      <div className="metricas-topbar">
        <h1 style={{ margin: 0 }}>Métricas — dashboards</h1>
        <div className="metricas-controles">
          <label className="texto-suave" htmlFor="dias">
            Período
          </label>
          <select id="dias" value={dias} onChange={(e) => setDias(Number(e.target.value))}>
            <option value={7}>7 dias</option>
            <option value={30}>30 dias</option>
            <option value={90}>90 dias</option>
          </select>
        </div>
      </div>
      <p className="texto-suave" style={{ marginTop: 6 }}>
        Séries são por dia (UTC) no período selecionado; distribuições cobrem o mesmo período salvo onde indicado. Dados 100% do banco — sem mock.
      </p>
      <Tabs abas={abas} abaInicial="overview" />
    </div>
  );
}
