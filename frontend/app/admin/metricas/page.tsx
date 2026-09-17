"use client";

/**
 * FRENTE 6 — Central de Inteligência (`/admin/metricas`).
 *
 * Consome `GET /api/metricas/inteligencia/` (só admin): audiência, tráfego,
 * conteúdo, comportamento, localização, séries temporais, comparativo com o
 * período anterior e insights editoriais automáticos — tudo agregado de
 * eventos reais. Sem dados, a tela mostra "sem dados", nunca números
 * inventados (o fallback mock da versão anterior foi removido).
 *
 * Inclui ainda os controles editoriais cujos overrides o algoritmo
 * respeita: `DestaqueEditorial` (manchete/destaque/bloqueio por entrada,
 * consumido por `feed/recomendacao.py`) e `RegraCuradoria`
 * (categoria/colunista/ordem/selos, aplicada no feed geral).
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { useAuth } from "@/lib/auth-context";
import * as api from "@/lib/api";
import type { CentralInteligencia, PeriodoInteligencia } from "@/lib/api";

const PERIODOS: { chave: PeriodoInteligencia; rotulo: string }[] = [
  { chave: "hoje", rotulo: "Hoje" },
  { chave: "ontem", rotulo: "Ontem" },
  { chave: "7d", rotulo: "7d" },
  { chave: "30d", rotulo: "30d" },
  { chave: "90d", rotulo: "90d" },
  { chave: "custom", rotulo: "Custom" },
];

function fmt(n: number | undefined | null): string {
  if (n === undefined || n === null || Number.isNaN(n)) return "—";
  return Number(n).toLocaleString("pt-BR");
}

function Delta({ delta }: { delta: number | null | undefined }) {
  if (delta === null || delta === undefined) {
    return (
      <Badge variant="outline" className="border-[var(--cor-borda)] text-[var(--cor-texto-suave)]">
        sem base anterior
      </Badge>
    );
  }
  const pos = delta >= 0;
  return (
    <Badge
      variant="outline"
      className={pos ? "border-[var(--cor-sucesso)] text-[var(--cor-sucesso)]" : "border-[var(--cor-erro)] text-[var(--cor-erro)]"}
    >
      {pos ? "▲" : "▼"} {Math.abs(delta).toLocaleString("pt-BR")}% vs. anterior
    </Badge>
  );
}

function Kpi({ rotulo, valor, detalhe, delta }: { rotulo: string; valor: string; detalhe?: string; delta?: number | null }) {
  return (
    <div className="rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-3">
      <p className="text-xs tracking-widest text-[var(--cor-texto-suave)]">{rotulo}</p>
      <p className="mt-1 text-xl font-bold text-[var(--cor-texto)]">{valor}</p>
      {detalhe && <p className="mt-0.5 text-xs text-[var(--cor-texto-suave)]">{detalhe}</p>}
      {delta !== undefined && (
        <div className="mt-1.5">
          <Delta delta={delta} />
        </div>
      )}
    </div>
  );
}

function Barras({ itens, max = 8 }: { itens: { label: string; total: number }[]; max?: number }) {
  const lista = (itens || []).slice(0, max);
  const teto = Math.max(1, ...lista.map((i) => i.total));
  if (!lista.length) return <p className="text-xs text-[var(--cor-texto-suave)]">Sem dados no período.</p>;
  return (
    <div className="space-y-1.5">
      {lista.map((i, idx) => (
        <div key={`${i.label}-${idx}`} className="flex items-center gap-2 text-xs">
          <span className="w-28 shrink-0 truncate font-medium capitalize text-[var(--cor-texto)]" title={i.label}>
            {i.label || "—"}
          </span>
          <div className="h-2.5 min-w-0 flex-1 overflow-hidden rounded-full bg-[var(--cor-fundo-elevado)]">
            <div
              className="h-full rounded-full bg-[var(--cor-primaria)]"
              style={{ width: `${Math.max(2, Math.round((i.total / teto) * 100))}%` }}
            />
          </div>
          <span className="w-12 shrink-0 text-right font-mono text-[var(--cor-texto-suave)]">{fmt(i.total)}</span>
        </div>
      ))}
    </div>
  );
}

function SerieLinha({ series, altura = 140 }: { series: { rotulo: string; cor: string; pontos: { dia: string; total: number }[] }[]; altura?: number }) {
  const largura = 560;
  const todos = series.flatMap((s) => s.pontos.map((p) => p.total));
  const max = Math.max(1, ...todos);
  const n = Math.max(1, ...series.map((s) => s.pontos.length));
  const rotulos = series[0]?.pontos.map((p) => p.dia.slice(5)) || [];
  const caminho = (pontos: { total: number }[]) =>
    pontos
      .map((p, i) => {
        const x = n === 1 ? largura / 2 : (i / (n - 1)) * (largura - 8) + 4;
        const y = altura - 8 - (p.total / max) * (altura - 24);
        return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
      })
      .join(" ");
  if (!n || todos.every((t) => t === 0)) {
    return <p className="text-xs text-[var(--cor-texto-suave)]">Sem movimento no período.</p>;
  }
  return (
    <div>
      <svg viewBox={`0 0 ${largura} ${altura}`} className="w-full" role="img" aria-label="Evolução temporal">
        {[0.25, 0.5, 0.75].map((f) => (
          <line key={f} x1={0} x2={largura} y1={altura * f} y2={altura * f} stroke="var(--cor-borda)" strokeWidth={1} opacity={0.6} />
        ))}
        {series.map((s) => (
          <path key={s.rotulo} d={caminho(s.pontos)} fill="none" stroke={s.cor} strokeWidth={2.5} strokeLinejoin="round" />
        ))}
      </svg>
      <div className="mt-1 flex flex-wrap gap-3 text-xs text-[var(--cor-texto-suave)]">
        {series.map((s) => (
          <span key={s.rotulo} className="inline-flex items-center gap-1.5">
            <span className="inline-block h-2 w-4 rounded-full" style={{ background: s.cor }} />
            {s.rotulo}
          </span>
        ))}
        {rotulos.length > 1 && (
          <span className="ml-auto font-mono">
            {rotulos[0]} → {rotulos[rotulos.length - 1]}
          </span>
        )}
      </div>
    </div>
  );
}

function TabelaRank({
  titulo,
  linhas,
  colunas,
}: {
  titulo: string;
  linhas: Record<string, React.ReactNode>[];
  colunas: string[];
}) {
  if (!linhas.length) {
    return (
      <div className="rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-3">
        <p className="text-sm font-medium text-[var(--cor-texto)]">{titulo}</p>
        <p className="mt-1 text-xs text-[var(--cor-texto-suave)]">Sem dados no período.</p>
      </div>
    );
  }
  return (
    <div className="overflow-x-auto rounded-md border border-[var(--cor-borda)]">
      <table className="w-full min-w-[420px] text-sm">
        <caption className="bg-[var(--cor-fundo-elevado)] px-3 py-2 text-left text-sm font-medium text-[var(--cor-texto)]">
          {titulo}
        </caption>
        <thead>
          <tr className="border-y border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] text-left text-xs text-[var(--cor-texto-suave)]">
            {colunas.map((c) => (
              <th key={c} className="px-3 py-2 font-medium">
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {linhas.map((l, i) => (
            <tr key={i} className="border-b border-[var(--cor-borda)] last:border-0">
              {colunas.map((c) => (
                <td key={c} className="px-3 py-2 align-top text-[var(--cor-texto)]">
                  {l[c]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const TIPO_INSIGHT_ROTULO: Record<string, string> = {
  categoria_crescimento: "crescimento",
  categoria_emergente: "emergente",
  regiao_crescimento: "região",
  pico_audiencia: "pico",
  horarios_pico: "horários",
  retencao_alta: "retenção alta",
  retencao_baixa: "retenção baixa",
  busca_emergente: "busca emergente",
  busca_em_alta: "busca em alta",
};

export default function Page() {
  const { token } = useAuth();
  const [periodo, setPeriodo] = useState<PeriodoInteligencia>("30d");
  const [inicio, setInicio] = useState("");
  const [fim, setFim] = useState("");
  const [data, setData] = useState<CentralInteligencia | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const [destaques, setDestaques] = useState<api.DestaqueEditorial[]>([]);
  const [regras, setRegras] = useState<api.RegraCuradoria[]>([]);
  const [novoDestaque, setNovoDestaque] = useState({ tipo: "manchete", entry_tipo: "item", entry_id: "", motivo: "" });
  const [novaRegra, setNovaRegra] = useState({ tipo: "boost_categoria", alvo: "", entry_tipo: "item", entry_id: "", ordem: "0", motivo: "" });
  const [msgOverride, setMsgOverride] = useState<string | null>(null);

  const carregar = useCallback(async () => {
    if (!token) return;
    setErr(null);
    setLoading(true);
    try {
      const r = await api.obterCentralInteligencia(token, { periodo, inicio: inicio || undefined, fim: fim || undefined });
      setData(r);
      const [d, rg] = await Promise.all([api.adminListarDestaques(token).catch(() => []), api.adminListarRegras(token).catch(() => [])]);
      setDestaques(d);
      setRegras(rg);
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Falha ao carregar a Central.");
    } finally {
      setLoading(false);
    }
  }, [token, periodo, inicio, fim]);

  useEffect(() => {
    if (token) void carregar();
  }, [token, carregar]);

  const comp = data?.comparativo;
  const series = useMemo(() => {
    if (!data) return [];
    return [
      { rotulo: "Visitas", cor: "var(--cor-primaria)", pontos: data.series.visitas || [] },
      { rotulo: "Views em notícias", cor: "var(--cor-sucesso)", pontos: (data.series.views_noticia as { dia: string; total: number }[]) || [] },
      { rotulo: "Buscas", cor: "var(--cor-alerta)", pontos: (data.series.buscas as { dia: string; total: number }[]) || [] },
    ];
  }, [data]);

  async function alternarDestaque(d: api.DestaqueEditorial) {
    if (!token) return;
    try {
      const atualizado = await api.adminAtualizarDestaque(token, d.id, { ativo: !d.ativo });
      setDestaques((atual) => atual.map((x) => (x.id === d.id ? atualizado : x)));
    } catch (e: unknown) {
      setMsgOverride(e instanceof Error ? e.message : "Falha ao atualizar.");
    }
  }

  async function excluirDestaque(id: number) {
    if (!token) return;
    try {
      await api.adminExcluirDestaque(token, id);
      setDestaques((atual) => atual.filter((x) => x.id !== id));
    } catch (e: unknown) {
      setMsgOverride(e instanceof Error ? e.message : "Falha ao excluir.");
    }
  }

  async function criarDestaque() {
    if (!token) return;
    const entryId = Number(novoDestaque.entry_id);
    if (!Number.isFinite(entryId) || entryId <= 0) {
      setMsgOverride("Informe o ID da notícia/acontecimento.");
      return;
    }
    try {
      const criado = await api.adminCriarDestaque(token, {
        tipo: novoDestaque.tipo,
        entry_tipo: novoDestaque.entry_tipo,
        entry_id: entryId,
        motivo: novoDestaque.motivo,
      });
      setDestaques((atual) => [criado, ...atual]);
      setNovoDestaque({ tipo: "manchete", entry_tipo: "item", entry_id: "", motivo: "" });
      setMsgOverride(null);
    } catch (e: unknown) {
      setMsgOverride(e instanceof Error ? e.message : "Falha ao criar destaque.");
    }
  }

  async function criarRegra() {
    if (!token) return;
    try {
      const entryId = Number(novaRegra.entry_id);
      const criado = await api.adminCriarRegra(token, {
        tipo: novaRegra.tipo,
        alvo: novaRegra.alvo,
        entry_tipo: novaRegra.entry_tipo,
        entry_id: Number.isFinite(entryId) && entryId > 0 ? entryId : undefined,
        ordem: Number(novaRegra.ordem) || 0,
        motivo: novaRegra.motivo,
      });
      setRegras((atual) => [criado, ...atual]);
      setNovaRegra({ tipo: "boost_categoria", alvo: "", entry_tipo: "item", entry_id: "", ordem: "0", motivo: "" });
      setMsgOverride(null);
    } catch (e: unknown) {
      setMsgOverride(e instanceof Error ? e.message : "Falha ao criar regra.");
    }
  }

  async function alternarRegra(r: api.RegraCuradoria) {
    if (!token) return;
    try {
      const atualizado = await api.adminAtualizarRegra(token, r.id, { ativo: !r.ativo });
      setRegras((atual) => atual.map((x) => (x.id === r.id ? atualizado : x)));
    } catch (e: unknown) {
      setMsgOverride(e instanceof Error ? e.message : "Falha ao atualizar.");
    }
  }

  async function excluirRegra(id: number) {
    if (!token) return;
    try {
      await api.adminExcluirRegra(token, id);
      setRegras((atual) => atual.filter((x) => x.id !== id));
    } catch (e: unknown) {
      setMsgOverride(e instanceof Error ? e.message : "Falha ao excluir.");
    }
  }

  return (
    <div className="space-y-4">
      <Card className="bento border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
        <CardHeader>
          <CardTitle>Central de Inteligência</CardTitle>
          <CardDescription className="text-[var(--cor-texto-suave)]">
            Audiência, tráfego, conteúdo, comportamento e região — agregados de eventos reais, com comparativo do período anterior e insights editoriais automáticos.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            {PERIODOS.map((p) => (
              <Button
                key={p.chave}
                variant={periodo === p.chave ? "default" : "outline"}
                onClick={() => setPeriodo(p.chave)}
                className="min-h-[44px]"
              >
                {p.rotulo}
              </Button>
            ))}
            {periodo === "custom" && (
              <>
                <Input type="date" aria-label="Início" value={inicio} onChange={(e) => setInicio(e.target.value)} className="h-11 w-auto bg-[var(--cor-fundo-card)]" />
                <Input type="date" aria-label="Fim" value={fim} onChange={(e) => setFim(e.target.value)} className="h-11 w-auto bg-[var(--cor-fundo-card)]" />
              </>
            )}
            <Button onClick={() => void carregar()} disabled={loading} className="min-h-[44px] bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]">
              {loading ? "Carregando..." : "Atualizar"}
            </Button>
            {data && (
              <span className="text-xs text-[var(--cor-texto-suave)]">
                {data.periodo.chave} • {data.periodo.dias}d • comparando com período anterior
              </span>
            )}
          </div>
          {err && (
            <p className="rounded-md border border-[var(--cor-erro)] bg-[var(--cor-erro-suave)] px-3 py-2 text-sm text-[var(--cor-erro)]">{err}</p>
          )}
          {!err && !data && !loading && (
            <p className="text-sm text-[var(--cor-texto-suave)]">Carregando a Central...</p>
          )}
        </CardContent>
      </Card>

      {data && (
        <>
          <div className="grid gap-3 md:grid-cols-4">
            <Kpi rotulo="VISITAS" valor={fmt(data.audiencia.visitas)} detalhe={`${fmt(data.audiencia.sessoes)} sessões`} delta={comp?.visitas?.delta_pct} />
            <Kpi rotulo="USUÁRIOS NOVOS" valor={fmt(data.audiencia.usuarios_novos)} detalhe={`${fmt(data.audiencia.usuarios_recorrentes)} recorrentes`} delta={comp?.usuarios_novos?.delta_pct} />
            <Kpi rotulo="VIEWS EM NOTÍCIAS" valor={fmt(data.comportamento.views_noticia)} detalhe={`${fmt(data.audiencia.views_por_noticia)} views/notícia`} delta={comp?.views_noticia?.delta_pct} />
            <Kpi rotulo="TAXA DE RETORNO" valor={`${data.audiencia.taxa_retorno_pct.toLocaleString("pt-BR")}%`} detalhe="sessões em 2+ dias" />
            <Kpi rotulo="TEMPO MÉDIO DE LEITURA" valor={`${fmt(data.audiencia.tempo_medio_leitura_seg)}s`} detalhe={`${fmt(data.audiencia.leituras_com_tempo)} leituras medidas`} />
            <Kpi rotulo="BUSCAS" valor={fmt(data.comportamento.buscas_total)} detalhe={`${fmt(data.conteudo.buscas_sem_resultado)} sem resultado`} delta={comp?.buscas?.delta_pct} />
            <Kpi rotulo="COMPARTILHAMENTOS" valor={fmt(data.comportamento.shares)} detalhe={`${fmt(data.comportamento.salvos)} salvos`} delta={comp?.compartilhamentos?.delta_pct} />
            <Kpi rotulo="VIEWS NO RADAR" valor={fmt(data.comportamento.radar_views)} detalhe={`${fmt(data.comportamento.comunidade.views)} views na comunidade`} delta={comp?.radar_views?.delta_pct} />
          </div>

          <Card className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
            <CardHeader>
              <CardTitle className="text-base">Evolução temporal</CardTitle>
              <CardDescription className="text-[var(--cor-texto-suave)]">Visitas, views em notícias e buscas por dia.</CardDescription>
            </CardHeader>
            <CardContent>
              <SerieLinha series={series} />
            </CardContent>
          </Card>

          <Card className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
            <CardHeader>
              <CardTitle className="text-base">Inteligência editorial automática</CardTitle>
              <CardDescription className="text-[var(--cor-texto-suave)]">
                Gerada só com dados reais do período — assuntos em crescimento, picos, horários, retenção e buscas emergentes.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {data.inteligencia.sem_dados ? (
                <p className="text-sm text-[var(--cor-texto-suave)]">{data.inteligencia.mensagem}</p>
              ) : (
                <div className="grid gap-3 md:grid-cols-2">
                  {(data.inteligencia.itens || []).map((ins, i) => (
                    <div key={i} className="rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-3">
                      <Badge variant="outline" className="border-[var(--cor-primaria)] text-[var(--cor-primaria)]">
                        {TIPO_INSIGHT_ROTULO[ins.tipo] || ins.tipo}
                      </Badge>
                      <p className="mt-1.5 text-sm font-semibold text-[var(--cor-texto)]">{ins.titulo}</p>
                      <p className="mt-0.5 text-xs text-[var(--cor-texto-suave)]">{ins.detalhe}</p>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          <div className="grid gap-3 md:grid-cols-2">
            <Card className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
              <CardHeader><CardTitle className="text-base">Origem do tráfego</CardTitle></CardHeader>
              <CardContent><Barras itens={data.trafego.origens} /></CardContent>
            </Card>
            <Card className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
              <CardHeader><CardTitle className="text-base">Dispositivos</CardTitle></CardHeader>
              <CardContent><Barras itens={data.trafego.dispositivos} /></CardContent>
            </Card>
            <Card className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
              <CardHeader><CardTitle className="text-base">Categorias por views</CardTitle></CardHeader>
              <CardContent><Barras itens={data.conteudo.categorias_top} max={10} /></CardContent>
            </Card>
            <Card className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
              <CardHeader><CardTitle className="text-base">Seções da Home</CardTitle></CardHeader>
              <CardContent>
                <p className="mb-2 text-xs text-[var(--cor-texto-suave)]">
                  {fmt(data.comportamento.home.views)} views • {fmt(data.comportamento.home.cliques)} cliques
                </p>
                <Barras itens={data.comportamento.home.por_secao} />
              </CardContent>
            </Card>
          </div>

          <div className="grid gap-3 md:grid-cols-2">
            <TabelaRank
              titulo="Mais acessadas"
              colunas={["Notícia", "Categoria", "Views"]}
              linhas={data.conteudo.mais_acessadas.map((r) => ({
                Notícia: <span title={`${r.tipo}:${r.id}`}>{r.titulo}</span>,
                Categoria: <span className="capitalize">{r.categoria || "—"}</span>,
                Views: <span className="font-mono">{fmt(r.total)}</span>,
              }))}
            />
            <TabelaRank
              titulo="Mais compartilhadas"
              colunas={["Notícia", "Shares"]}
              linhas={data.conteudo.mais_compartilhadas.map((r) => ({
                Notícia: <span title={`${r.tipo}:${r.id}`}>{r.titulo}</span>,
                Shares: <span className="font-mono">{fmt(r.total)}</span>,
              }))}
            />
            <TabelaRank
              titulo="Maior tempo médio de leitura (3+ leituras)"
              colunas={["Notícia", "Média", "Leituras"]}
              linhas={data.conteudo.maior_tempo_medio.map((r) => ({
                Notícia: <span title={`${r.tipo}:${r.id}`}>{r.titulo}</span>,
                Média: <span className="font-mono">{fmt(r.media_seg)}s</span>,
                Leituras: <span className="font-mono">{fmt(r.leituras)}</span>,
              }))}
            />
            <TabelaRank
              titulo="Termos mais pesquisados"
              colunas={["Termo", "Buscas"]}
              linhas={data.conteudo.mais_pesquisadas.map((t) => ({
                Termo: <span>“{t.termo}”</span>,
                Buscas: <span className="font-mono">{fmt(t.total)}</span>,
              }))}
            />
            <TabelaRank
              titulo="Urgentes mais vistas"
              colunas={["Notícia", "Views"]}
              linhas={data.conteudo.urgentes_top.map((r) => ({
                Notícia: <span title={`${r.tipo}:${r.id}`}>{r.titulo}</span>,
                Views: <span className="font-mono">{fmt(r.total)}</span>,
              }))}
            />
            <TabelaRank
              titulo="Colunistas (publicações)"
              colunas={["Colunista", "Publicações"]}
              linhas={data.conteudo.colunistas_top.map((c) => ({
                Colunista: <span>{c.label}</span>,
                Publicações: <span className="font-mono">{fmt(c.total)}</span>,
              }))}
            />
            <TabelaRank
              titulo={data.conteudo.autores_sem_dados ? "Autores (sem dados de autoria no período)" : "Autores por views"}
              colunas={["Autor", "Views"]}
              linhas={data.conteudo.autores_top.map((c) => ({
                Autor: <span>{c.label}</span>,
                Views: <span className="font-mono">{fmt(c.total)}</span>,
              }))}
            />
            <TabelaRank
              titulo="Páginas de entrada / saída"
              colunas={["Página", "Entradas"]}
              linhas={data.audiencia.top_entradas.map((e) => ({
                Página: <span className="break-all font-mono text-xs">{e.label}</span>,
                Entradas: <span className="font-mono">{fmt(e.total)}</span>,
              }))}
            />
          </div>

          <div className="grid gap-3 md:grid-cols-2">
            <Card className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
              <CardHeader>
                <CardTitle className="text-base">Localização (consentida)</CardTitle>
                <CardDescription className="text-[var(--cor-texto-suave)]">
                  {data.localizacao.nota} • {fmt(data.localizacao.localidades_salvas_total)} localidades salvas.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <div>
                  <p className="mb-1 text-xs font-semibold tracking-widest text-[var(--cor-texto-suave)]">ESTADOS</p>
                  <Barras itens={data.localizacao.estados} max={6} />
                </div>
                <div>
                  <p className="mb-1 text-xs font-semibold tracking-widest text-[var(--cor-texto-suave)]">CIDADES</p>
                  <Barras itens={data.localizacao.cidades} max={6} />
                </div>
              </CardContent>
            </Card>
            <Card className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
              <CardHeader><CardTitle className="text-base">Comportamento e navegação</CardTitle></CardHeader>
              <CardContent className="space-y-3">
                <p className="text-xs text-[var(--cor-texto-suave)]">
                  Scroll médio {fmt(data.comportamento.scroll_medio_pct)}% • Tempo médio na página {fmt(data.audiencia.tempo_medio_pagina_seg)}s •
                  Comunidade: {fmt(data.comportamento.comunidade.views)} views, {fmt(data.comportamento.comunidade.interacoes)} interações
                </p>
                <div>
                  <p className="mb-1 text-xs font-semibold tracking-widest text-[var(--cor-texto-suave)]">PÁGINAS MAIS VISTAS</p>
                  <Barras itens={data.comportamento.top_paths} max={6} />
                </div>
                <div>
                  <p className="mb-1 text-xs font-semibold tracking-widest text-[var(--cor-texto-suave)]">CATEGORIAS NAVEGADAS</p>
                  <Barras itens={data.comportamento.categorias_navegadas} max={6} />
                </div>
              </CardContent>
            </Card>
          </div>

          <Card className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
            <CardHeader>
              <CardTitle className="text-base">Controles editoriais (overrides do algoritmo)</CardTitle>
              <CardDescription className="text-[var(--cor-texto-suave)]">
                Manchetes/destaques/bloqueios por entrada (respeitados pela recomendação) e regras de categoria, colunista, ordem e selos (aplicadas no feed geral).
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {msgOverride && (
                <p className="rounded-md border border-[var(--cor-alerta)] px-3 py-2 text-sm text-[var(--cor-alerta)]">{msgOverride}</p>
              )}
              <div>
                <p className="text-sm font-semibold text-[var(--cor-texto)]">Destaques / manchetes / bloqueios</p>
                <div className="mt-2 flex flex-wrap gap-2">
                  <select aria-label="Tipo de override" value={novoDestaque.tipo} onChange={(e) => setNovoDestaque({ ...novoDestaque, tipo: e.target.value })} className="h-11 rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] px-2 text-sm">
                    <option value="manchete">Manchete</option>
                    <option value="destaque">Destaque</option>
                    <option value="bloqueio">Bloqueio</option>
                  </select>
                  <select aria-label="Tipo de entrada" value={novoDestaque.entry_tipo} onChange={(e) => setNovoDestaque({ ...novoDestaque, entry_tipo: e.target.value })} className="h-11 rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] px-2 text-sm">
                    <option value="item">Notícia</option>
                    <option value="cluster">Acontecimento</option>
                  </select>
                  <Input placeholder="ID" inputMode="numeric" value={novoDestaque.entry_id} onChange={(e) => setNovoDestaque({ ...novoDestaque, entry_id: e.target.value })} className="h-11 w-24 bg-[var(--cor-fundo-card)]" />
                  <Input placeholder="Motivo (opcional)" value={novoDestaque.motivo} onChange={(e) => setNovoDestaque({ ...novoDestaque, motivo: e.target.value })} className="h-11 min-w-[200px] flex-1 bg-[var(--cor-fundo-card)]" />
                  <Button onClick={() => void criarDestaque()} className="min-h-[44px] bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]">Adicionar</Button>
                </div>
                <div className="mt-2 space-y-1.5">
                  {destaques.length === 0 && <p className="text-xs text-[var(--cor-texto-suave)]">Nenhum override por entrada.</p>}
                  {destaques.map((d) => (
                    <div key={d.id} className="flex flex-wrap items-center gap-2 rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] px-3 py-2 text-sm">
                      <Badge variant="outline" className="capitalize">{d.tipo}</Badge>
                      <span className="font-mono text-xs text-[var(--cor-texto-suave)]">{d.entry_tipo}:{d.entry_id}</span>
                      <span className="min-w-0 flex-1 truncate text-[var(--cor-texto)]">{d.titulo || d.motivo || "—"}</span>
                      <Badge variant="outline" className={d.ativo ? "border-[var(--cor-sucesso)] text-[var(--cor-sucesso)]" : "border-[var(--cor-borda)] text-[var(--cor-texto-suave)]"}>
                        {d.ativo ? "ativo" : "inativo"}
                      </Badge>
                      <Button size="sm" variant="outline" onClick={() => void alternarDestaque(d)}>{d.ativo ? "Desativar" : "Ativar"}</Button>
                      <Button size="sm" variant="ghost" onClick={() => void excluirDestaque(d.id)}>Excluir</Button>
                    </div>
                  ))}
                </div>
              </div>
              <div>
                <p className="text-sm font-semibold text-[var(--cor-texto)]">Regras (categorias, colunistas, ordem, selos)</p>
                <div className="mt-2 flex flex-wrap gap-2">
                  <select aria-label="Tipo de regra" value={novaRegra.tipo} onChange={(e) => setNovaRegra({ ...novaRegra, tipo: e.target.value })} className="h-11 rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] px-2 text-sm">
                    <option value="boost_categoria">Boost categoria</option>
                    <option value="bloqueio_categoria">Bloqueio categoria</option>
                    <option value="ordem_categorias">Ordem de categorias</option>
                    <option value="colunista_destaque">Colunista destaque</option>
                    <option value="boost_entrada">Boost entrada</option>
                    <option value="bloqueio_entrada">Bloqueio entrada</option>
                    <option value="selo_forcado">Selo forçado</option>
                    <option value="urgente_forcado">Urgente forçado</option>
                    <option value="exclusivo_forcado">Exclusivo forçado</option>
                  </select>
                  <Input placeholder="Alvo (categoria, autor, selo ou lista)" value={novaRegra.alvo} onChange={(e) => setNovaRegra({ ...novaRegra, alvo: e.target.value })} className="h-11 min-w-[220px] flex-1 bg-[var(--cor-fundo-card)]" />
                  <Input placeholder="ID entrada (só regras por entrada)" inputMode="numeric" value={novaRegra.entry_id} onChange={(e) => setNovaRegra({ ...novaRegra, entry_id: e.target.value })} className="h-11 w-28 bg-[var(--cor-fundo-card)]" />
                  <Button onClick={() => void criarRegra()} className="min-h-[44px] bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]">Adicionar</Button>
                </div>
                <div className="mt-2 space-y-1.5">
                  {regras.length === 0 && <p className="text-xs text-[var(--cor-texto-suave)]">Nenhuma regra.</p>}
                  {regras.map((r) => (
                    <div key={r.id} className="flex flex-wrap items-center gap-2 rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] px-3 py-2 text-sm">
                      <Badge variant="outline">{r.tipo.replace(/_/g, " ")}</Badge>
                      <span className="min-w-0 flex-1 truncate text-[var(--cor-texto)]">
                        {r.alvo || `${r.entry_tipo}:${r.entry_id}`} {r.motivo ? `• ${r.motivo}` : ""}
                      </span>
                      <Badge variant="outline" className={r.ativo ? "border-[var(--cor-sucesso)] text-[var(--cor-sucesso)]" : "border-[var(--cor-borda)] text-[var(--cor-texto-suave)]"}>
                        {r.ativo ? "ativa" : "inativa"}
                      </Badge>
                      <Button size="sm" variant="outline" onClick={() => void alternarRegra(r)}>{r.ativo ? "Desativar" : "Ativar"}</Button>
                      <Button size="sm" variant="ghost" onClick={() => void excluirRegra(r.id)}>Excluir</Button>
                    </div>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
