"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { useAuth } from "@/lib/auth-context";
import * as api from "@/lib/api";
import { Newspaper, Plus, Pencil, Trash2, Power, ArrowRight, Loader2 } from "lucide-react";

type Fonte = api.FonteRobo;

export function FontesIsland() {
  const { token } = useAuth();
  const tk = token || "";
  const [fontes, setFontes] = useState<Fonte[]>([]);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [nome, setNome] = useState("");
  const [url, setUrl] = useState("");
  const [cat, setCat] = useState("");
  const [editId, setEditId] = useState<number | null>(null);
  const [editNome, setEditNome] = useState("");
  const [editUrl, setEditUrl] = useState("");
  const [editCat, setEditCat] = useState("");
  const [editAtivo, setEditAtivo] = useState(true);
  const [removeId, setRemoveId] = useState<number | null>(null);

  const carregar = async () => {
    if (!tk) return;
    setLoading(true);
    setErr(null);
    try {
      setFontes(await api.robosListarFontes(tk));
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Falha ao listar fontes.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (tk) void carregar();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tk]);

  const criar = async () => {
    setErr(null);
    setOk(null);
    if (!nome.trim() || !url.trim()) {
      setErr("Informe nome e URL da fonte.");
      return;
    }
    try {
      await api.robosCriarFonte(tk, { nome: nome.trim(), url: url.trim(), ativo: true, categoria_padrao: cat.trim() });
      setNome("");
      setUrl("");
      setCat("");
      setOk("Fonte adicionada.");
      await carregar();
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Falha ao criar fonte.");
    }
  };

  const toggleAtivo = async (f: Fonte) => {
    try {
      await api.robosAtualizarFonte(tk, f.id, { ativo: !f.ativo });
      await carregar();
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Falha ao alternar fonte.");
    }
  };

  const salvarEdicao = async () => {
    if (editId == null) return;
    try {
      await api.robosAtualizarFonte(tk, editId, { nome: editNome.trim(), url: editUrl.trim(), categoria_padrao: editCat.trim(), ativo: editAtivo });
      setEditId(null);
      setOk("Fonte atualizada.");
      await carregar();
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Falha ao atualizar fonte.");
    }
  };

  const remover = async () => {
    if (removeId == null) return;
    try {
      await api.robosRemoverFonte(tk, removeId);
      setRemoveId(null);
      setOk("Fonte removida.");
      await carregar();
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Falha ao remover fonte.");
    }
  };

  if (!tk) {
    return <p className="text-sm text-[var(--cor-texto-suave)]">Entre como admin para gerenciar as fontes.</p>;
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <p className="flex items-center gap-1.5 text-sm font-semibold text-[var(--cor-texto)]"><Newspaper className="h-4 w-4 text-[var(--cor-primaria)]" /> Minhas fontes — ingestão</p>
        <Badge variant="outline" className="border-[var(--cor-borda)]">{fontes.filter((f) => f.ativo).length} ativas / {fontes.length}</Badge>
        <Button size="sm" variant="outline" onClick={carregar} disabled={loading} className="ml-auto min-h-[36px] gap-1 border-[var(--cor-borda)]">{loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null} Atualizar</Button>
        <Button asChild size="sm" variant="ghost" className="min-h-[36px] gap-1"><Link href="/admin/robos">Controle completo <ArrowRight className="h-3.5 w-3.5" /></Link></Button>
      </div>
      <p className="text-xs leading-relaxed text-[var(--cor-texto-suave)]">De onde os robôs buscam notícias (RSS). Ative, pause, edite ou adicione — vale na próxima ingestão. Para intervalo, deduplicação e IA, use <Link href="/admin/robos" className="font-medium text-[var(--cor-primaria)] underline">Robôs → Configuração</Link>.</p>
      {err && <p role="alert" className="rounded-md border border-[var(--cor-erro)] bg-[var(--cor-erro-suave)] px-3 py-2 text-sm text-[var(--cor-erro)]">{err}</p>}
      {ok && <p role="status" className="rounded-md border border-[var(--cor-sucesso)] bg-[var(--cor-sucesso-suave)] px-3 py-2 text-sm text-[var(--cor-sucesso)]">{ok}</p>}

      <div className="grid gap-2">
        {fontes.map((f) =>
          editId === f.id ? (
            <div key={f.id} className="space-y-2 rounded-[var(--raio-md)] border border-[var(--cor-primaria)] bg-[var(--cor-fundo-card)] p-3">
              <div className="grid gap-2 md:grid-cols-2">
                <div className="space-y-1"><Label>Nome</Label><Input value={editNome} onChange={(e) => setEditNome(e.target.value)} /></div>
                <div className="space-y-1"><Label>URL (RSS)</Label><Input value={editUrl} onChange={(e) => setEditUrl(e.target.value)} /></div>
              </div>
              <div className="grid gap-2 md:grid-cols-[1fr_auto] md:items-end">
                <div className="space-y-1"><Label>Categoria padrão</Label><Input value={editCat} onChange={(e) => setEditCat(e.target.value)} placeholder="geral" /></div>
                <label className="flex items-center gap-2 pb-2 text-sm"><Switch checked={editAtivo} onCheckedChange={setEditAtivo} /> Ativa</label>
              </div>
              <div className="flex gap-2">
                <Button size="sm" onClick={salvarEdicao} className="bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]">Salvar</Button>
                <Button size="sm" variant="ghost" onClick={() => setEditId(null)}>Cancelar</Button>
              </div>
            </div>
          ) : (
            <div key={f.id} className="flex flex-col gap-2 rounded-[var(--raio-md)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] p-3 md:flex-row md:items-center md:justify-between">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="truncate font-medium text-[var(--cor-texto)]">{f.nome}</p>
                  <Badge variant={f.ativo ? "default" : "outline"} className={f.ativo ? "bg-[var(--cor-sucesso)] text-[var(--cor-texto-invertido)]" : "border-[var(--cor-borda)]"}>{f.ativo ? "ativa" : "pausada"}</Badge>
                  {f.categoria_padrao && <Badge variant="outline" className="border-[var(--cor-borda)]">{f.categoria_padrao}</Badge>}
                </div>
                <p className="truncate text-xs text-[var(--cor-texto-suave)]">{f.url}</p>
              </div>
              <div className="flex shrink-0 flex-wrap gap-1">
                <Button size="sm" variant="outline" onClick={() => toggleAtivo(f)} className="gap-1" title={f.ativo ? "Pausar" : "Ativar"}><Power className="h-3.5 w-3.5" /> {f.ativo ? "Pausar" : "Ativar"}</Button>
                <Button size="sm" variant="outline" onClick={() => { setEditId(f.id); setEditNome(f.nome); setEditUrl(f.url); setEditCat(f.categoria_padrao || ""); setEditAtivo(f.ativo); }} className="gap-1"><Pencil className="h-3.5 w-3.5" /> Editar</Button>
                <Button size="sm" variant="destructive" onClick={() => setRemoveId(f.id)} className="gap-1"><Trash2 className="h-3.5 w-3.5" /> Remover</Button>
              </div>
            </div>
          )
        )}
        {!fontes.length && !loading && <p className="text-sm text-[var(--cor-texto-suave)]">Nenhuma fonte — adicione a primeira abaixo.</p>}
      </div>

      <div className="rounded-[var(--raio-md)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] p-3">
        <p className="flex items-center gap-1.5 text-sm font-medium text-[var(--cor-texto)]"><Plus className="h-4 w-4" /> Nova fonte</p>
        <div className="mt-2 grid gap-2 md:grid-cols-2">
          <div className="space-y-1"><Label>Nome *</Label><Input value={nome} onChange={(e) => setNome(e.target.value)} placeholder="Ex: G1" /></div>
          <div className="space-y-1"><Label>URL do RSS *</Label><Input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://…" /></div>
        </div>
        <div className="mt-2 space-y-1"><Label>Categoria padrão</Label><Input value={cat} onChange={(e) => setCat(e.target.value)} placeholder="geral" /></div>
        <Button onClick={criar} disabled={!nome.trim() || !url.trim()} className="mt-3 min-h-[44px] bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]">Adicionar fonte</Button>
      </div>

      <Dialog open={removeId != null} onOpenChange={(o) => { if (!o) setRemoveId(null); }}>
        <DialogContent className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
          <DialogHeader>
            <DialogTitle>Remover fonte?</DialogTitle>
            <DialogDescription>Os robôs deixarão de buscar notícias desta fonte. O histórico já ingerido continua no ar.</DialogDescription>
          </DialogHeader>
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setRemoveId(null)}>Cancelar</Button>
            <Button variant="destructive" onClick={remover}>Remover</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
