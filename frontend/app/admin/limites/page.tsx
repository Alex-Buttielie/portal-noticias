"use client";
import { useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { toast } from "sonner";
import { useAuth } from "@/lib/auth-context";
import * as api from "@/lib/api";
import { useQueryAdminLimites } from "@/lib/queries";
import { queryKeys } from "@/lib/query-keys";
import { formatarDataHoraCompleta } from "@/lib/datas";
import { Clock3, Layers, Pencil, RefreshCw, Settings2, ShieldCheck, Sparkles, Zap } from "lucide-react";

type Lim = { id: number; chave: string; plano: string; valor: string; descricao: string; atualizado_em?: string | null };

// `referencia` documenta o formato esperado do valor (ex.: "free: 20/dia").
// É texto de apoio à curadoria, não dado presented como real ao leitor.
const META: Record<string, { label: string; desc: string; icon: typeof Layers; referencia: string }> = {
  feed_max_itens: { label: "Itens no feed", desc: "Quantas matérias o usuário vê por dia no feed principal.", icon: Layers, referencia: "free: 20 itens/dia · premium: ilimitado" },
  radar_credito: { label: "Radar", desc: "Consultas ao Radar de tendências e evolução por período.", icon: Zap, referencia: "free: 3 consultas/dia · premium: ilimitado" },
  alertas_max: { label: "Alertas", desc: "Alertas personalizados por tema/categoria.", icon: Sparkles, referencia: "free: 1 alerta · premium: ilimitado" },
  historico_dias: { label: "Histórico", desc: "Dias de histórico e arquivo completo liberados.", icon: Clock3, referencia: "free: 7 dias · premium: histórico completo" },
  feed_sem_anuncios: { label: "Feed sem anúncios", desc: "Remove publicidade do feed para o plano.", icon: ShieldCheck, referencia: "free: com anúncios · premium: sem anúncios" },
};

function human(meta: (typeof META)[string] | undefined, chave: string) {
  return meta?.label ?? chave.replaceAll("_", " ");
}

function isRecente(iso?: string | null) {
  if (!iso) return false;
  const d = new Date(iso).getTime();
  if (Number.isNaN(d)) return false;
  return Date.now() - d < 24 * 60 * 60 * 1000;
}

export default function Page() {
  const { usuario, token } = useAuth();
  const cliente = useQueryClient();
  const consulta = useQueryAdminLimites({ token, usuarioId: usuario?.id ?? 0 });
  const [log, setLog] = useState<string[]>([]);
  const [filtro, setFiltro] = useState("todas");
  const [edit, setEdit] = useState<Lim | null>(null);
  const [valor, setValor] = useState("");
  const [desc, setDesc] = useState("");
  const [saving, setSaving] = useState(false);
  const [erroVal, setErroVal] = useState<string | null>(null);

  const brutas = ((consulta.data?.results as unknown as Lim[]) || []);
  const vazia = consulta.isSuccess && !brutas.length;
  const itens = brutas;
  const loading = consulta.isFetching;
  // P0-08: nada é exibido no lugar da lista real. Erro => estado de erro;
  // vazio de verdade => estado vazio.
  const err = consulta.isError
    ? (consulta.error instanceof Error ? consulta.error.message : "Falha — API offline")
    : vazia
      ? "Nenhum limite cadastrado ainda."
      : null;

  const chaves = useMemo(() => Array.from(new Set(itens.map((i) => i.chave))), [itens]);
  const agrupado = useMemo(() => {
    const m = new Map<string, Lim[]>();
    for (const it of itens) { const a = m.get(it.chave) ?? []; a.push(it); m.set(it.chave, a); }
    return Array.from(m.entries()).sort(([a], [b]) => a.localeCompare(b));
  }, [itens]);
  const filtrado = useMemo(() => (filtro === "todas" ? agrupado : agrupado.filter(([k]) => k === filtro)), [agrupado, filtro]);

  function abrirEdicao(l: Lim) { setEdit(l); setValor(l.valor); setDesc(l.descricao || ""); setErroVal(null); }

  async function salvar() {
    if (!edit) return;
    if (!valor.trim()) { setErroVal("Valor é obrigatório."); return; }
    if (valor.length > 40) { setErroVal("Valor muito longo (máx. 40)."); return; }
    setSaving(true);
    setErroVal(null);
    try {
      await api.adminAtualizarLimite(token || "", edit.id, { valor: valor.trim(), descricao: desc.trim() });
      toast.success("Limite atualizado");
      setLog((p) => [`${formatarDataHoraCompleta(new Date())} — ${edit.chave}/${edit.plano} → ${valor.trim()} — ${desc.trim() || "sem descrição"}`].concat(p).slice(0, 20));
      setEdit(null);
      await cliente.invalidateQueries({ queryKey: queryKeys.admin.limites() });
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Falha ao salvar";
      setErroVal(msg);
      toast.error(msg);
    } finally { setSaving(false); }
  }

  const preview = edit ? `Usuário ${edit.plano} verá: ${META[edit.chave]?.label ?? edit.chave} = ${valor.trim() || "—"}` : "";

  return (
    <div className="space-y-4">
      <Card className="bento">
        <CardHeader>
          <CardTitle className="flex items-center gap-2"><Settings2 className="h-5 w-5 text-[var(--cor-primaria)]" /> Limites por plano</CardTitle>
          <CardDescription className="text-[var(--cor-texto-suave)]">
            Limites controlam o que cada plano pode fazer — ex: quantas matérias por dia, acesso ao Radar, alertas e histórico.
            O plano <strong className="font-semibold text-[var(--cor-texto)]">free</strong> tem cotas menores; o <strong className="font-semibold text-[var(--cor-texto)]">premium</strong> libera ou amplia. Edite cada chave abaixo.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap gap-2">
            <Button onClick={() => void consulta.refetch()} disabled={loading} className="min-h-[44px] bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]"><RefreshCw className="mr-2 h-4 w-4" />{loading ? "Carregando..." : "Recarregar"}</Button>
            <Badge variant="outline" className="border-[var(--cor-borda)] self-center">{itens.length} registros · {chaves.length} chaves</Badge>
          </div>
          {err && <p role="alert" className="rounded-md border border-[var(--cor-alerta)] bg-[var(--cor-alerta-suave)] px-3 py-2 text-sm text-[var(--cor-texto)]">{err}</p>}

          <div className="grid gap-3 md:grid-cols-2">
            {chaves.map((c) => {
              const meta = META[c];
              const Icon = meta?.icon ?? Layers;
              return (
                <div key={c} className="rounded-[var(--raio-lg)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-4">
                  <div className="flex gap-3">
                    <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[var(--raio-md)] bg-[var(--cor-primaria-suave)] text-[var(--cor-primaria)]"><Icon className="h-5 w-5" /></span>
                    <div className="min-w-0">
                      <p className="text-sm font-semibold text-[var(--cor-texto)]">{human(meta, c)}</p>
                      <p className="text-xs text-[var(--cor-texto-suave)]">{meta?.desc ?? "Regra de gating por plano."}</p>
                      <p className="mt-1 font-mono text-xs text-[var(--cor-texto-suave)]">{c}</p>
                      {meta?.referencia && <p className="mt-1 text-xs font-medium text-[var(--cor-primaria)]">{meta.referencia}</p>}
                    </div>
                  </div>
                </div>
              );
            })}
            {!chaves.length && !loading && <p className="text-sm text-[var(--cor-texto-suave)]">Nenhum limite encontrado.</p>}
          </div>

          <Separator className="bg-[var(--cor-borda)]" />

          <Tabs value={filtro} onValueChange={setFiltro}>
            <TabsList className="w-full justify-start overflow-x-auto bg-[var(--cor-borda)]">
              <TabsTrigger value="todas">Todas</TabsTrigger>
              {chaves.map((c) => <TabsTrigger key={c} value={c} className="font-mono text-xs">{c}</TabsTrigger>)}
            </TabsList>
            {filtrado.map(([chave, linhas]) => (
              <TabsContent key={chave} value={chave} className="mt-3">
                <Card className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
                  <CardHeader className="pb-3">
                    <CardTitle className="flex flex-wrap items-center gap-2 text-base">{human(META[chave], chave)}<Badge variant="outline" className="border-[var(--cor-borda)] font-mono text-[10px]">{chave}</Badge></CardTitle>
                    <CardDescription>{META[chave]?.desc ?? "Valores por plano para esta chave."} {META[chave]?.referencia && <span className="font-medium text-[var(--cor-primaria)]"> — {META[chave].referencia}</span>}</CardDescription>
                  </CardHeader>
                  <CardContent className="overflow-x-auto">
                    <table className="w-full min-w-[520px] text-sm">
                      <thead><tr className="border-b border-[var(--cor-borda)] text-left text-xs text-[var(--cor-texto-suave)]"><th className="py-2 font-medium">Plano</th><th className="py-2 font-medium">Valor</th><th className="py-2 font-medium">Descrição</th><th className="py-2 font-medium">Atualizado</th><th className="py-2" /></tr></thead>
                      <tbody>
                        {linhas.map((l) => (
                          <tr key={l.id} className="border-b border-[var(--cor-borda)] last:border-0">
                            <td className="py-2"><Badge className={l.plano === "premium" ? "bg-[var(--cor-premium)] text-[var(--cor-texto-invertido)]" : "bg-[var(--cor-secundaria)] text-[var(--cor-texto-invertido)]"}>{l.plano}</Badge>{isRecente(l.atualizado_em) && <Badge variant="outline" className="ml-1 border-[var(--cor-sucesso)] text-[var(--cor-sucesso)]">recente</Badge>}</td>
                            <td className="py-2 font-mono font-medium text-[var(--cor-texto)]">{l.valor}</td>
                            <td className="max-w-[260px] truncate py-2 text-xs text-[var(--cor-texto-suave)]">{l.descricao || "—"}</td>
                            <td className="py-2 text-xs text-[var(--cor-texto-suave)]">{l.atualizado_em ? formatarDataHoraCompleta(l.atualizado_em) : "—"}</td>
                            <td className="py-2 text-right"><Button size="sm" variant="outline" className="h-8 border-[var(--cor-borda)]" onClick={() => abrirEdicao(l)}><Pencil className="mr-1 h-3.5 w-3.5" /> Editar</Button></td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </CardContent>
                </Card>
              </TabsContent>
            ))}
            <TabsContent value="todas" className="mt-3 space-y-3">
              {agrupado.map(([chave, linhas]) => (
                <Card key={chave} className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
                  <CardHeader className="pb-3"><CardTitle className="flex flex-wrap items-center gap-2 text-base">{human(META[chave], chave)}<Badge variant="outline" className="border-[var(--cor-borda)] font-mono text-[10px]">{chave}</Badge></CardTitle><CardDescription>{META[chave]?.referencia ?? ""}</CardDescription></CardHeader>
                  <CardContent className="overflow-x-auto">
                    <table className="w-full min-w-[520px] text-sm">
                      <thead><tr className="border-b border-[var(--cor-borda)] text-left text-xs text-[var(--cor-texto-suave)]"><th className="py-2 font-medium">Plano</th><th className="py-2 font-medium">Valor</th><th className="py-2 font-medium">Descrição</th><th className="py-2 font-medium">Atualizado</th><th className="py-2" /></tr></thead>
                      <tbody>
                        {linhas.map((l) => (
                          <tr key={l.id} className="border-b border-[var(--cor-borda)] last:border-0">
                            <td className="py-2"><Badge className={l.plano === "premium" ? "bg-[var(--cor-premium)] text-[var(--cor-texto-invertido)]" : "bg-[var(--cor-secundaria)] text-[var(--cor-texto-invertido)]"}>{l.plano}</Badge>{isRecente(l.atualizado_em) && <Badge variant="outline" className="ml-1 border-[var(--cor-sucesso)] text-[var(--cor-sucesso)]">recente</Badge>}</td>
                            <td className="py-2 font-mono font-medium text-[var(--cor-texto)]">{l.valor}</td>
                            <td className="max-w-[260px] truncate py-2 text-xs text-[var(--cor-texto-suave)]">{l.descricao || "—"}</td>
                            <td className="py-2 text-xs text-[var(--cor-texto-suave)]">{l.atualizado_em ? formatarDataHoraCompleta(l.atualizado_em) : "—"}</td>
                            <td className="py-2 text-right"><Button size="sm" variant="outline" className="h-8 border-[var(--cor-borda)]" onClick={() => abrirEdicao(l)}><Pencil className="mr-1 h-3.5 w-3.5" /> Editar</Button></td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </CardContent>
                </Card>
              ))}
            </TabsContent>
          </Tabs>

          {log.length > 0 && (
            <div className="rounded-[var(--raio-lg)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-3">
              <p className="text-xs font-semibold text-[var(--cor-texto)]">Log de alterações (visível nesta sessão)</p>
              <ul className="mt-2 space-y-1 text-xs font-mono text-[var(--cor-texto-suave)]">{log.map((l, i) => <li key={i}>• {l}</li>)}</ul>
            </div>
          )}
        </CardContent>
      </Card>

      <Dialog open={!!edit} onOpenChange={(o) => { if (!o) setEdit(null); }}>
        <DialogContent className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2"><Pencil className="h-4 w-4 text-[var(--cor-primaria)]" /> Editar limite</DialogTitle>
            <DialogDescription>{edit ? `${edit.chave} — plano ${edit.plano}` : ""} · Alteração registrada em log auditável.</DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div className="space-y-1"><Label htmlFor="valor">Valor</Label><Input id="valor" value={valor} onChange={(e) => setValor(e.target.value)} placeholder="ex: 20, 100, ilimitado" className="border-[var(--cor-borda)]" /></div>
            <div className="space-y-1"><Label htmlFor="desc">Descrição humana</Label><Input id="desc" value={desc} onChange={(e) => setDesc(e.target.value)} placeholder="O que esse limite significa para o usuário" className="border-[var(--cor-borda)]" /></div>
            <div className="rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-3">
              <p className="text-xs font-semibold text-[var(--cor-texto)]">Como fica para o usuário</p>
              <p className="mt-1 text-sm text-[var(--cor-texto-suave)]">{preview || "—"}</p>
              {edit && META[edit.chave]?.referencia && <p className="mt-1 text-xs text-[var(--cor-texto-suave)]">Referência: {META[edit.chave].referencia}</p>}
            </div>
            {erroVal && <p role="alert" className="rounded-md border border-[var(--cor-erro)] bg-[var(--cor-erro-suave)] px-3 py-2 text-sm text-[var(--cor-erro)]">{erroVal}</p>}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEdit(null)} className="min-h-[44px]">Cancelar</Button>
            <Button onClick={salvar} disabled={saving} className="min-h-[44px] bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]">{saving ? "Salvando..." : "Salvar"}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}