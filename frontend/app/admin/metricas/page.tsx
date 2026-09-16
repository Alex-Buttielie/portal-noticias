"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import * as api from "@/lib/api";
import { usePainelMetricas } from "@/lib/queries";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { EmptyState, ErrorState, SkeletonLista } from "@/components/ui/Estados";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";

function pct(v: number) {
  return new Intl.NumberFormat("pt-BR", { style: "percent", minimumFractionDigits: 1, maximumFractionDigits: 1 }).format(v);
}

function moeda(v: string | number) {
  const n = typeof v === "string" ? Number(v) : v;
  if (Number.isNaN(n)) return String(v);
  return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(n);
}

function maxY(series: api.SeriePonto[]) {
  return Math.max(1, ...series.map((p) => p.total));
}

function Sparkline({ serie, cor = "var(--cor-primaria)", titulo }: { serie: api.SeriePonto[]; cor?: string; titulo: string }) {
  if (!serie.length) return <p className="text-sm text-[var(--cor-texto-suave)]">Sem dados no período.</p>;
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
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={H} role="img" aria-label={titulo}>
        <rect x={0} y={0} width={W} height={H} rx={10} fill="var(--cor-fundo-elevado)" />
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
      <div className="flex justify-between text-xs text-[var(--cor-texto-suave)]">
        <span>{serie[0]?.dia}</span>
        <span>{serie[serie.length - 1]?.dia}</span>
      </div>
    </div>
  );
}

function Barras({ itens, cor = "var(--cor-primaria)", titulo }: { itens: api.DistribuicaoItem[]; cor?: string; titulo: string }) {
  if (!itens.length) return <p className="text-sm text-[var(--cor-texto-suave)]">Sem dados.</p>;
  const m = Math.max(1, ...itens.map((x) => x.total));
  return (
    <div className="grid gap-2" role="img" aria-label={titulo}>
      {itens.map((it) => (
        <div key={it.label} className="grid grid-cols-[120px_1fr_40px] items-center gap-2">
          <span className="truncate text-xs font-medium text-[var(--cor-texto)]" title={it.label}>
            {it.label}
          </span>
          <div className="h-2 overflow-hidden rounded-full bg-[var(--cor-borda)]">
            <div className="h-full rounded-full" style={{ width: `${(it.total / m) * 100}%`, background: cor }} />
          </div>
          <span className="text-xs tabular-nums text-[var(--cor-texto-suave)]">{it.total}</span>
        </div>
      ))}
    </div>
  );
}

function Donut({ itens, size = 140, titulo }: { itens: api.DistribuicaoItem[]; size?: number; titulo: string }) {
  if (!itens.length) return <p className="text-sm text-[var(--cor-texto-suave)]">Sem dados.</p>;
  const total = itens.reduce((a, b) => a + b.total, 0) || 1;
  const cores = ["var(--cor-primaria)", "var(--cor-sucesso)", "var(--cor-alerta)", "var(--cor-erro)"];
  let acc = 0;
  const r = 52;
  const cx = size / 2;
  const cy = size / 2;
  const circ = 2 * Math.PI * r;
  return (
    <div className="flex flex-col items-center gap-3">
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img" aria-label={titulo}>
        <circle cx={cx} cy={cy} r={r} fill="none" stroke="var(--cor-borda)" strokeWidth={18} />
        {itens.map((it, i) => {
          const frac = it.total / total;
          const len = frac * circ;
          const dash = `${len} ${circ - len}`;
          const offset = circ * 0.25 - acc;
          acc += len;
          return <circle key={it.label} cx={cx} cy={cy} r={r} fill="none" stroke={cores[i % cores.length]} strokeWidth={18} strokeDasharray={dash} strokeDashoffset={offset} />;
        })}
        <circle cx={cx} cy={cy} r={36} fill="var(--cor-fundo-elevado)" stroke="var(--cor-borda)" />
        <text x={cx} y={cy} textAnchor="middle" dominantBaseline="central" fontSize={13} fontWeight={700} fill="var(--cor-texto)">
          {total}
        </text>
      </svg>
      <ul className="grid gap-1 text-xs">
        {itens.map((it, i) => (
          <li key={it.label} className="flex items-center gap-2">
            <span className="h-3 w-3 shrink-0 rounded-full" style={{ background: cores[i % cores.length] }} aria-hidden="true" /> {it.label}: {it.total} ({pct(it.total / total)})
          </li>
        ))}
      </ul>
    </div>
  );
}

function KpiCard({ titulo, valor, subtitulo, destaque }: { titulo: string; valor: string; subtitulo?: string; destaque?: string }) {
  return (
    <Card className="min-w-0 overflow-hidden">
      <CardContent className="min-w-0 p-5">
        <p className="text-xs font-semibold uppercase tracking-wider text-[var(--cor-texto-suave)]">{titulo}</p>
        <p className="mt-1 break-words text-2xl font-bold tracking-tight text-[var(--cor-texto)]">{valor}</p>
        {subtitulo && <p className="mt-1 break-words text-xs text-[var(--cor-texto-suave)]">{subtitulo}</p>}
        {destaque && (
          <div className="mt-2">
            <Badge variant="secondary">{destaque}</Badge>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function Bloco({ titulo, children }: { titulo: string; children: React.ReactNode }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{titulo}</CardTitle>
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}

export default function PaginaAdminMetricas() {
  const router = useRouter();
  const { token, usuario, carregando: carregandoAuth } = useAuth();
  const [dias, setDias] = useState(30);
  const painelQuery = usePainelMetricas(dias);

  useEffect(() => {
    if (!carregandoAuth && !token) {
      router.push("/login");
    }
  }, [carregandoAuth, token, router]);

  const painel = painelQuery.data ?? null;
  const carregando = carregandoAuth || painelQuery.isLoading;
  const erro =
    usuario && usuario.papel !== "admin"
      ? "Acesso restrito à administração."
      : painelQuery.isError
        ? "Não foi possível carregar o painel."
        : null;

  const conteudo = useMemo(() => {
    if (!painel) return null;
    const d = painel.distribuicoes;
    const k = painel.kpis;
    const s = painel.series;
    const f = painel.funil;
    return { d, k, s, f };
  }, [painel]);

  if (carregando) return <SkeletonLista quantidade={2} />;
  if (erro) return <ErrorState mensagem={erro} aoTentarNovamente={() => void painelQuery.refetch()} />;
  if (!painel || !conteudo) return <EmptyState titulo="Sem dados" descricao="Nenhuma métrica para o período." />;
  const { d, k, s, f } = conteudo;

  return (
    <section className="grid min-w-0 gap-6" aria-labelledby="admin-metricas-titulo">
      <div className="grid min-w-0 gap-1">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <h1 id="admin-metricas-titulo" className="font-[var(--fonte-titulo)] text-2xl font-bold tracking-tight text-balance text-[var(--cor-texto)]">
            Métricas
          </h1>
          <div className="flex items-center gap-2">
            <Label htmlFor="dias">Período</Label>
            <select
              id="dias"
              value={dias}
              onChange={(e) => setDias(Number(e.target.value))}
              className="h-10 min-h-[44px] rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]"
            >
              <option value={7}>7 dias</option>
              <option value={30}>30 dias</option>
              <option value={90}>90 dias</option>
            </select>
          </div>
        </div>
        <p className="max-w-2xl break-words text-sm text-[var(--cor-texto-suave)]">
          Acompanhe cadastros, receita, conteúdo e moderação. Séries por dia (UTC) no período selecionado;
          distribuições cobrem o mesmo período salvo onde indicado. Dados 100% do banco — sem mock.
        </p>
      </div>

      <Tabs defaultValue="overview" className="grid gap-6">
        <TabsList aria-label="Dimensões das métricas" className="flex-wrap">
          <TabsTrigger value="overview">Visão geral</TabsTrigger>
          <TabsTrigger value="receita">Receita e assinaturas</TabsTrigger>
          <TabsTrigger value="conteudo">Conteúdo e comunidade</TabsTrigger>
          <TabsTrigger value="moderacao">Moderação e operação</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="grid gap-4">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <KpiCard titulo="Usuários totais" valor={String(painel.usuarios_cadastrados_total)} subtitulo={`+${painel.usuarios_cadastrados_periodo} no período`} destaque={`${painel.periodo_dias} dias`} />
            <KpiCard titulo="DAU / MAU" valor={`${painel.usuarios_ativos_diarios} / ${painel.usuarios_ativos_mensais}`} subtitulo={`Retenção ${pct(painel.retencao_periodo)}`} />
            <KpiCard titulo="Assinaturas ativas" valor={String(painel.assinaturas_ativas)} subtitulo={`Conversão ${pct(painel.conversao_free_premium)} · Churn ${pct(painel.churn_periodo)}`} />
            <KpiCard titulo="Receita no período" valor={moeda(painel.receita_recorrente_periodo)} subtitulo={`Ticket médio ${moeda(painel.receita_media_por_assinante)} · Renovação ${pct(painel.taxa_renovacao_periodo)}`} />
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            <Bloco titulo="Cadastros por dia">
              <Sparkline serie={s.cadastros} cor="var(--cor-primaria)" titulo="Cadastros por dia" />
            </Bloco>
            <Bloco titulo="Receita por dia (R$)">
              <Sparkline serie={s.receita} cor="var(--cor-sucesso)" titulo="Receita por dia" />
            </Bloco>
            <Bloco titulo="Novas assinaturas por dia">
              <Sparkline serie={s.assinaturas} cor="var(--cor-alerta)" titulo="Novas assinaturas por dia" />
            </Bloco>
            <Bloco titulo="Notícias ingeridas por dia">
              <Sparkline serie={s.noticias} titulo="Notícias ingeridas por dia" />
            </Bloco>
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            <Bloco titulo="Funil — lista, cadastro e premium">
              <dl className="grid gap-2 text-sm">
                <div className="flex items-center justify-between gap-2">
                  <dt className="text-[var(--cor-texto-suave)]">Lista de espera</dt>
                  <dd className="font-bold tabular-nums">{f.lista_espera}</dd>
                </div>
                <p className="text-xs text-[var(--cor-texto-suave)]">Conversão lista para cadastro: {pct(f.taxa_lista_para_cadastro)}</p>
                <div className="flex items-center justify-between gap-2">
                  <dt className="text-[var(--cor-texto-suave)]">Cadastrados</dt>
                  <dd className="font-bold tabular-nums">{f.cadastrados}</dd>
                </div>
                <p className="text-xs text-[var(--cor-texto-suave)]">Conversão cadastro para premium: {pct(f.taxa_cadastro_para_premium)}</p>
                <div className="flex items-center justify-between gap-2">
                  <dt className="text-[var(--cor-texto-suave)]">Premium ativos</dt>
                  <dd className="font-bold tabular-nums">{f.assinantes}</dd>
                </div>
              </dl>
            </Bloco>
            <Bloco titulo="Usuários por papel">
              <Donut itens={d.papel} titulo="Usuários por papel" />
            </Bloco>
            <Bloco titulo="Assinaturas por status">
              <Barras itens={d.assinaturas_status} cor="var(--cor-alerta)" titulo="Assinaturas por status" />
            </Bloco>
          </div>
        </TabsContent>

        <TabsContent value="receita" className="grid gap-4">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <KpiCard titulo="Receita período" valor={moeda(painel.receita_recorrente_periodo)} />
            <KpiCard titulo="Ticket médio" valor={moeda(painel.receita_media_por_assinante)} />
            <KpiCard titulo="Churn" valor={pct(painel.churn_periodo)} subtitulo={`Renovação ${pct(painel.taxa_renovacao_periodo)}`} />
            <KpiCard titulo="Conversão free para premium" valor={pct(painel.conversao_free_premium)} subtitulo={`${painel.assinaturas_ativas} ativas`} />
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            <Bloco titulo="Receita por dia">
              <Sparkline serie={s.receita} cor="var(--cor-sucesso)" titulo="Receita por dia" />
            </Bloco>
            <Bloco titulo="Assinaturas criadas por dia">
              <Sparkline serie={s.assinaturas} cor="var(--cor-alerta)" titulo="Assinaturas criadas por dia" />
            </Bloco>
            <Bloco titulo="Status das assinaturas">
              <Donut itens={d.assinaturas_status} titulo="Status das assinaturas" />
            </Bloco>
            <Bloco titulo="B2B — planos das organizações">
              <Barras itens={d.b2b_plano} cor="var(--cor-primaria)" titulo="B2B por plano" />
              <p className="mt-2 text-sm text-[var(--cor-texto-suave)]">
                B2B ativas: {k.b2b.ativas} / {k.b2b.total} · Critérios ativos: {k.b2b.criterios_ativos}
              </p>
            </Bloco>
          </div>
          <Bloco titulo="Lista de espera por dia">
            <Sparkline serie={s.lista_espera} cor="var(--cor-primaria)" titulo="Lista de espera por dia" />
            <p className="mt-2 text-sm text-[var(--cor-texto-suave)]">Total em espera: {k.lista_espera.total}</p>
          </Bloco>
          <Bloco titulo="Newsletter">
            <Barras itens={d.newsletter_tipo} cor="var(--cor-sucesso)" titulo="Newsletter por tipo" />
            <p className="mt-2 text-sm text-[var(--cor-texto-suave)]">
              Ativas {k.newsletter.ativas} / {k.newsletter.total}
            </p>
          </Bloco>
        </TabsContent>

        <TabsContent value="conteudo" className="grid gap-4">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <KpiCard titulo="Notícias no período" valor={String(k.ingestao.noticias_periodo)} subtitulo={`Pendentes moderação: ${k.ingestao.noticias_pendentes}`} />
            <KpiCard titulo="Taxa aprovação" valor={pct(k.ingestao.taxa_aprovacao)} subtitulo="aprovadas + não aplicável / total" />
            <KpiCard titulo="Publicações" valor={`${k.comunidade.publicacoes_publicadas} / ${k.comunidade.publicacoes_total}`} subtitulo="publicadas / total" />
            <KpiCard titulo="Comentários / Seguidores" valor={`${k.comunidade.comentarios_total} / ${k.comunidade.seguidores_total}`} />
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            <Bloco titulo="Notícias por dia">
              <Sparkline serie={s.noticias} titulo="Notícias por dia" />
            </Bloco>
            <Bloco titulo="Publicações por dia">
              <Sparkline serie={s.publicacoes} titulo="Publicações por dia" />
            </Bloco>
            <Bloco titulo="Comentários por dia">
              <Sparkline serie={s.comentarios} cor="var(--cor-alerta)" titulo="Comentários por dia" />
            </Bloco>
            <Bloco titulo="Ingestão — custo estimado/dia (USD)">
              <Sparkline serie={s.ingestao_custo} cor="var(--cor-erro)" titulo="Custo de ingestão por dia" />
              <p className="mt-2 text-sm text-[var(--cor-texto-suave)]">
                Custo no período: ${k.ingestao.custo_periodo.toFixed(4)} · Hoje: ${(painel.custo_llm_hoje_usd ?? 0).toFixed(4)} / teto ${(painel.teto_llm_diario_usd ?? 0).toFixed(2)}
              </p>
            </Bloco>
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            <Bloco titulo="Notícias por categoria">
              <Barras itens={d.noticias_categoria} titulo="Notícias por categoria" />
            </Bloco>
            <Bloco titulo="Notícias por fonte">
              <Barras itens={d.noticias_fonte} cor="var(--cor-sucesso)" titulo="Notícias por fonte" />
            </Bloco>
            <Bloco titulo="Status revisão (notícias)">
              <Donut itens={d.noticias_status} titulo="Notícias por status de revisão" />
            </Bloco>
            <Bloco titulo="Publicações por status">
              <Donut itens={d.publicacoes_status} titulo="Publicações por status" />
            </Bloco>
          </div>
        </TabsContent>

        <TabsContent value="moderacao" className="grid gap-4">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <KpiCard titulo="Denúncias pendentes" valor={String(k.moderacao.denuncias_pendentes)} subtitulo={`Total ${k.moderacao.denuncias_total}`} destaque={k.moderacao.denuncias_pendentes > 0 ? "Ação necessária" : "Em dia"} />
            <KpiCard titulo="Ações de moderação" valor={String(k.moderacao.acoes_total)} />
            <KpiCard titulo="Solicitações credenciamento" valor={String(d.credenciamento_status.reduce((a, b) => a + b.total, 0))} subtitulo="total histórico" />
            <KpiCard titulo="Custo LLM hoje" valor={`$${(painel.custo_llm_hoje_usd ?? 0).toFixed(4)}`} subtitulo={`Teto $${(painel.teto_llm_diario_usd ?? 0).toFixed(2)}${painel.teto_llm_excedido_hoje ? " · EXCEDIDO" : ""}`} />
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            <Bloco titulo="Denúncias por status">
              <Donut itens={d.denuncias_status} titulo="Denúncias por status" />
            </Bloco>
            <Bloco titulo="Ações por tipo">
              <Barras itens={d.acoes_tipo} cor="var(--cor-erro)" titulo="Ações por tipo" />
            </Bloco>
            <Bloco titulo="Credenciamento por status">
              <Donut itens={d.credenciamento_status} titulo="Credenciamento por status" />
            </Bloco>
            <Bloco titulo="B2B — critérios por tipo">
              <Barras itens={d.criterio_tipo} cor="var(--cor-alerta)" titulo="Critérios por tipo" />
              <p className="mt-2 text-sm text-[var(--cor-texto-suave)]">Critérios ativos: {k.b2b.criterios_ativos}</p>
            </Bloco>
          </div>
        </TabsContent>
      </Tabs>
    </section>
  );
}
