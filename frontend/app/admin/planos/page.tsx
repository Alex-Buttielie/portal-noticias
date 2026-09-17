"use client";
import { useCallback, useEffect, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Separator } from "@/components/ui/separator";
import { Switch } from "@/components/ui/switch";
import { toast } from "sonner";
import { useAuth } from "@/lib/auth-context";
import * as api from "@/lib/api";
import { BadgeCheck, Crown, Pencil, Plus, RefreshCw, ShieldAlert, Trash2 } from "lucide-react";

type Plano = api.Plano;

const MOCK: Plano[] = [
  { id: 1, nome: "Free", preco: "0.00", duracao_dias: 0, ativo: true },
  { id: 2, nome: "Premium", preco: "29.90", duracao_dias: 30, ativo: true },
];

function precoValido(v: string) { return /^\d+(\.\d{1,2})?$/.test(v.trim()); }

export default function Page() {
  const { token } = useAuth();
  const [planos, setPlanos] = useState<Plano[]>([]);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [log, setLog] = useState<string[]>([]);

  const [nome, setNome] = useState("");
  const [preco, setPreco] = useState("");
  const [dias, setDias] = useState("30");
  const [ativo, setAtivo] = useState(true);
  const [criando, setCriando] = useState(false);
  const [errForm, setErrForm] = useState<string | null>(null);

  const [edit, setEdit] = useState<Plano | null>(null);
  const [eNome, setENome] = useState("");
  const [ePreco, setEPreco] = useState("");
  const [eDias, setEDias] = useState("");
  const [eAtivo, setEAtivo] = useState(true);
  const [eErr, setEErr] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const [excluir, setExcluir] = useState<Plano | null>(null);
  const [excluindo, setExcluindo] = useState(false);

  const carregar = useCallback(async () => {
    setErr(null); setLoading(true);
    try {
      const r = await api.adminListarPlanos(token || "");
      const arr = (r as unknown as { results?: Plano[] })?.results ?? (r as unknown as Plano[]);
      const lista = Array.isArray(arr) ? arr : [];
      if (!lista.length) { setPlanos(MOCK); setErr("API offline — exibindo dados de exemplo."); }
      else setPlanos(lista);
    } catch (e: unknown) {
      const m = e instanceof Error ? e.message : "API offline — mock";
      setErr(m + " — exibindo dados de exemplo."); setPlanos(MOCK);
    } finally { setLoading(false); }
  }, [token]);

  useEffect(() => { void carregar(); }, [carregar]);

  function validar(nomeV: string, precoV: string, diasV: string): string | null {
    if (!nomeV.trim()) return "Nome é obrigatório.";
    if (nomeV.trim().length < 2) return "Nome muito curto.";
    if (!precoValido(precoV)) return "Preço inválido. Use formato 29.90";
    const d = Number(diasV);
    if (!Number.isInteger(d) || d < 0 || d > 3650) return "Duração deve ser inteiro entre 0 e 3650 dias.";
    return null;
  }

  async function criar() {
    const v = validar(nome, preco, dias);
    if (v) { setErrForm(v); return; }
    setErrForm(null); setCriando(true);
    try {
      await api.adminCriarPlano(token || "", { nome: nome.trim(), preco: preco.trim(), duracao_dias: Number(dias), ativo });
      toast.success("Plano criado");
      setLog((p) => [`${new Date().toLocaleString("pt-BR")} — criar ${nome.trim()} R$ ${preco.trim()} ${dias}d ativo=${ativo}`].concat(p).slice(0, 20));
      setNome(""); setPreco(""); setDias("30"); setAtivo(true);
      await carregar();
    } catch (e: unknown) { const m = e instanceof Error ? e.message : "Falha ao criar"; setErrForm(m); toast.error(m); }
    finally { setCriando(false); }
  }

  function abrirEdicao(p: Plano) {
    setEdit(p); setENome(p.nome); setEPreco(p.preco); setEDias(String(p.duracao_dias)); setEAtivo(p.ativo ?? true); setEErr(null);
  }

  async function salvarEdicao() {
    if (!edit) return;
    const v = validar(eNome, ePreco, eDias);
    if (v) { setEErr(v); return; }
    setSaving(true); setEErr(null);
    try {
      await api.adminAtualizarPlano(token || "", edit.id, { nome: eNome.trim(), preco: ePreco.trim(), duracao_dias: Number(eDias), ativo: eAtivo });
      toast.success("Plano atualizado");
      setLog((p) => [`${new Date().toLocaleString("pt-BR")} — editar #${edit.id} → ${eNome.trim()} R$ ${ePreco.trim()} ${eDias}d ativo=${eAtivo}`].concat(p).slice(0, 20));
      setEdit(null); await carregar();
    } catch (e: unknown) { const m = e instanceof Error ? e.message : "Falha ao atualizar"; setEErr(m); toast.error(m); }
    finally { setSaving(false); }
  }

  async function confirmarExcluir() {
    if (!excluir) return;
    setExcluindo(true);
    try {
      await api.adminExcluirPlano(token || "", excluir.id);
      toast.success("Plano excluído");
      setLog((p) => [`${new Date().toLocaleString("pt-BR")} — excluir #${excluir.id} ${excluir.nome}`].concat(p).slice(0, 20));
      setExcluir(null); await carregar();
    } catch (e: unknown) {
      const err = e as { status?: number; message?: string };
      const msg = err?.status === 409 ? "Exclusão protegida: existem assinaturas vinculadas a este plano (409)." : (err?.message || "Falha ao excluir.");
      toast.error(msg); setErr(msg);
    } finally { setExcluindo(false); }
  }

  return (
    <div className="space-y-4">
      <Card className="bento border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
        <CardHeader>
          <CardTitle className="flex items-center gap-2"><Crown className="h-5 w-5 text-[var(--cor-premium)]" /> Planos</CardTitle>
          <CardDescription className="text-[var(--cor-texto-suave)]">Gerencie preço, duração e disponibilidade. Planos inativos não aparecem para novos assinantes. Exclusão é bloqueada quando há assinaturas (409).</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap gap-2">
            <Button onClick={carregar} disabled={loading} className="min-h-[44px] bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]"><RefreshCw className="mr-2 h-4 w-4" />{loading ? "Carregando..." : "Recarregar"}</Button>
            <Badge variant="outline" className="border-[var(--cor-borda)] self-center">{planos.length} planos</Badge>
          </div>
          {err && <p role="alert" className="rounded-md border border-[var(--cor-alerta)] bg-[var(--cor-alerta-suave)] px-3 py-2 text-sm text-[var(--cor-texto)]">{err}</p>}

          <div className="rounded-md border border-[var(--cor-alerta)] bg-[var(--cor-alerta-suave)] px-3 py-2 flex gap-2 text-xs text-[var(--cor-texto)]"><ShieldAlert className="h-4 w-4 shrink-0 text-[var(--cor-alerta)]" /> Exclusão protegida se houver assinaturas vinculadas — o servidor retorna 409 e a ação é bloqueada.</div>

          <div className="grid gap-2">
            {planos.map((p) => (
              <div key={p.id} className="flex flex-wrap items-center justify-between gap-2 rounded-[var(--raio-md)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-3">
                <div className="min-w-0">
                  <p className="flex items-center gap-2 font-medium text-[var(--cor-texto)]">{p.nome} {p.ativo === false ? <Badge variant="outline" className="border-[var(--cor-borda)] text-[var(--cor-texto-suave)]">inativo</Badge> : <Badge className="bg-[var(--cor-sucesso)] text-[var(--cor-texto-invertido)]"><BadgeCheck className="mr-1 h-3 w-3" /> ativo</Badge>}</p>
                  <p className="text-xs text-[var(--cor-texto-suave)]">R$ {p.preco} · {p.duracao_dias ? `${p.duracao_dias} dias` : "grátis"} {p.ativo === false && "· oculto para novos assinantes"}</p>
                </div>
                <div className="flex gap-2">
                  <Button size="sm" variant="outline" className="h-8 border-[var(--cor-borda)]" onClick={() => abrirEdicao(p)}><Pencil className="mr-1 h-3.5 w-3.5" /> Editar</Button>
                  <Button size="sm" variant="outline" className="h-8 border-[var(--cor-borda)] text-[var(--cor-erro)] hover:bg-[var(--cor-erro-suave)]" onClick={() => setExcluir(p)}><Trash2 className="mr-1 h-3.5 w-3.5" /> Excluir</Button>
                </div>
              </div>
            ))}
            {!planos.length && !loading && <p className="text-sm text-[var(--cor-texto-suave)]">Nenhum plano.</p>}
          </div>

          <Separator className="bg-[var(--cor-borda)]" />

          <div className="rounded-[var(--raio-lg)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-4 space-y-3">
            <p className="flex items-center gap-2 text-sm font-semibold text-[var(--cor-texto)]"><Plus className="h-4 w-4 text-[var(--cor-primaria)]" /> Criar plano</p>
            <div className="grid gap-3 md:grid-cols-3">
              <div className="space-y-1"><Label htmlFor="nome">Nome</Label><Input id="nome" value={nome} onChange={(e) => setNome(e.target.value)} placeholder="Ex: Premium" className="border-[var(--cor-borda)]" /></div>
              <div className="space-y-1"><Label htmlFor="preco">Preço (R$)</Label><Input id="preco" value={preco} onChange={(e) => setPreco(e.target.value)} placeholder="29.90" inputMode="decimal" className="border-[var(--cor-borda)]" /></div>
              <div className="space-y-1"><Label htmlFor="dias">Duração (dias)</Label><Input id="dias" value={dias} onChange={(e) => setDias(e.target.value)} placeholder="30" inputMode="numeric" className="border-[var(--cor-borda)]" /></div>
            </div>
            <div className="flex items-center gap-2"><Switch checked={ativo} onCheckedChange={setAtivo} id="ativo" /><Label htmlFor="ativo" className="text-sm">Ativo — visível para assinatura</Label>{!ativo && <Badge variant="outline" className="border-[var(--cor-borda)]">inativo</Badge>}</div>
            {errForm && <p role="alert" className="rounded-md border border-[var(--cor-erro)] bg-[var(--cor-erro-suave)] px-3 py-2 text-sm text-[var(--cor-erro)]">{errForm}</p>}
            <Button onClick={criar} disabled={criando} className="min-h-[44px] bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]">{criando ? "Criando..." : "Criar plano"}</Button>
          </div>

          {log.length > 0 && (
            <div className="rounded-[var(--raio-lg)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-3">
              <p className="text-xs font-semibold text-[var(--cor-texto)]">Log de auditoria (sessão)</p>
              <ul className="mt-2 space-y-1 text-xs font-mono text-[var(--cor-texto-suave)]">{log.map((l, i) => <li key={i}>• {l}</li>)}</ul>
            </div>
          )}
        </CardContent>
      </Card>

      <Dialog open={!!edit} onOpenChange={(o) => { if (!o) setEdit(null); }}>
        <DialogContent className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
          <DialogHeader><DialogTitle className="flex items-center gap-2"><Pencil className="h-4 w-4 text-[var(--cor-primaria)]" /> Editar plano</DialogTitle><DialogDescription>Preço, duração e ativo. Validação antes de salvar.</DialogDescription></DialogHeader>
          <div className="space-y-3">
            <div className="space-y-1"><Label>Nome</Label><Input value={eNome} onChange={(e) => setENome(e.target.value)} className="border-[var(--cor-borda)]" /></div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1"><Label>Preço</Label><Input value={ePreco} onChange={(e) => setEPreco(e.target.value)} inputMode="decimal" className="border-[var(--cor-borda)]" /></div>
              <div className="space-y-1"><Label>Dias</Label><Input value={eDias} onChange={(e) => setEDias(e.target.value)} inputMode="numeric" className="border-[var(--cor-borda)]" /></div>
            </div>
            <div className="flex items-center gap-2"><Switch checked={eAtivo} onCheckedChange={setEAtivo} id="e-ativo" /><Label htmlFor="e-ativo" className="text-sm">Ativo</Label>{!eAtivo && <span className="text-xs text-[var(--cor-texto-suave)]">plano oculto para novas assinaturas</span>}</div>
            {eErr && <p role="alert" className="rounded-md border border-[var(--cor-erro)] bg-[var(--cor-erro-suave)] px-3 py-2 text-sm text-[var(--cor-erro)]">{eErr}</p>}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEdit(null)} className="min-h-[44px] border-[var(--cor-borda)]">Cancelar</Button>
            <Button onClick={salvarEdicao} disabled={saving} className="min-h-[44px] bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]">{saving ? "Salvando..." : "Salvar"}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!excluir} onOpenChange={(o) => { if (!o) setExcluir(null); }}>
        <DialogContent className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
          <DialogHeader><DialogTitle className="flex items-center gap-2"><Trash2 className="h-4 w-4 text-[var(--cor-erro)]" /> Excluir plano?</DialogTitle><DialogDescription>Essa ação não pode ser desfeita. Se houver assinaturas vinculadas o servidor bloqueia (409).</DialogDescription></DialogHeader>
          {excluir && <div className="rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-3 text-sm"><p className="font-medium text-[var(--cor-texto)]">{excluir.nome}</p><p className="text-xs text-[var(--cor-texto-suave)]">R$ {excluir.preco} · {excluir.duracao_dias}d</p></div>}
          <DialogFooter>
            <Button variant="outline" onClick={() => setExcluir(null)} className="min-h-[44px] border-[var(--cor-borda)]">Cancelar</Button>
            <Button onClick={confirmarExcluir} disabled={excluindo} className="min-h-[44px] bg-[var(--cor-erro)] text-[var(--cor-texto-invertido)] hover:bg-[var(--cor-erro-hover)]">{excluindo ? "Excluindo..." : "Excluir"}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
