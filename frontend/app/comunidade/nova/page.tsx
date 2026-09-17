"use client";
import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { SeloFormato, formatoDaPublicacao } from "@/components/comunidade/TipoSelo";
import { useAuth } from "@/lib/auth-context";
import * as api from "@/lib/api";
import { registrarEventoComunidade } from "@/lib/interacoes-comunidade";
import { Link2, Send, CheckCircle2, Eye } from "lucide-react";

const CATEGORIAS = ["geral", "politica", "economia", "tecnologia", "esportes", "cultura", "saude", "mundo", "cidades"];

type FormVals = { titulo: string; conteudo: string; tags: string; news_cluster: string };

export default function Page() {
  const { token } = useAuth();
  const r = useRouter();
  const [err, setErr] = useState<string | null>(null);
  const [tipo, setTipo] = useState<api.TipoPublicacao>("opiniao");
  const [categoria, setCategoria] = useState("geral");
  const [okOpen, setOkOpen] = useState(false);
  const [createdId, setCreatedId] = useState<number | null>(null);
  const { register, handleSubmit, watch, formState: { errors, isSubmitting } } = useForm<FormVals>({ defaultValues: { titulo: "", conteudo: "", tags: "", news_cluster: "" } });

  const aoVivo = watch();
  const formato = formatoDaPublicacao(tipo, 0);
  const contagem = useMemo(() => aoVivo.conteudo.trim().length, [aoVivo.conteudo]);

  const onSubmit = async (d: FormVals) => {
    setErr(null);
    if (!token) { setErr("Entre para publicar."); return; }
    const titulo = d.titulo.trim();
    const conteudo = d.conteudo.trim();
    if (titulo.length < 3) { setErr("Título deve ter ao menos 3 caracteres."); return; }
    if (conteudo.length < 10) { setErr("Conteúdo deve ter ao menos 10 caracteres."); return; }
    const tags = d.tags.split(",").map((t) => t.trim()).filter(Boolean);
    const clusterRaw = d.news_cluster.trim();
    const news_cluster = clusterRaw ? Number(clusterRaw) : undefined;
    if (clusterRaw && !Number.isFinite(news_cluster)) { setErr("Cluster deve ser número ou vazio."); return; }
    try {
      const pub = await api.criarRascunhoPublicacao(token, { titulo, conteudo, tipo, categoria: categoria || undefined, tags: tags.length ? tags : undefined });
      const enviado = await api.enviarPublicacao(token, pub.id);
      setCreatedId(enviado.id ?? pub.id);
      registrarEventoComunidade("publicar", { categoria });
      setOkOpen(true);
    } catch (e: unknown) { setErr(e instanceof Error ? e.message : "Falha ao publicar."); }
  };

  if (!token) return (
    <div className="mx-auto max-w-xl py-8 px-3"><Card className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]"><CardContent className="p-6 text-center"><p className="text-sm text-[var(--cor-texto-suave)]">Entre para publicar na comunidade.</p><Button onClick={() => r.push("/login")} className="mt-3 bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)] min-h-[44px]">Entrar</Button></CardContent></Card></div>
  );

  return (
    <div className="mx-auto max-w-6xl space-y-4 py-6 px-3 sm:px-0">
      <div className="hud-line" aria-hidden />
      <div>
        <p className="text-xs font-semibold uppercase tracking-widest text-[var(--cor-primaria)]">Participação</p>
        <h1 className="text-2xl font-bold tracking-tight text-[var(--cor-texto)]">Nova publicação</h1>
        <p className="text-sm text-[var(--cor-texto-suave)]">Opinião e coluna ligadas à cobertura: escolha o formato, a editoria e — se houver — a notícia que originou o debate.</p>
      </div>

      <div className="grid gap-4 lg:grid-cols-[1fr_320px]">
        <Card className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
          <CardHeader>
            <CardTitle className="text-[var(--cor-texto)]">Escrever</CardTitle>
            <CardDescription className="text-[var(--cor-texto-suave)]">Texto com contexto e opinião fundamentada rende debate melhor.</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit(onSubmit)} className="space-y-3" noValidate>
              <div className="space-y-2"><Label htmlFor="titulo">Título *</Label><Input id="titulo" placeholder="Ex: Por que a mobilidade importa" {...register("titulo", { required: "Informe o título" })} />{errors.titulo && <p className="text-xs text-[var(--cor-erro)]">{errors.titulo.message as string}</p>}</div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="space-y-2">
                  <Label id="lb-tipo">Formato *</Label>
                  <Select value={tipo} onValueChange={(v) => setTipo(v as api.TipoPublicacao)}>
                    <SelectTrigger className="bg-[var(--cor-fundo-card)]" aria-labelledby="lb-tipo"><SelectValue /></SelectTrigger>
                    <SelectContent><SelectItem value="opiniao">Opinião</SelectItem><SelectItem value="analise">Coluna / Análise</SelectItem></SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label id="lb-cat">Editoria (grupo) *</Label>
                  <Select value={categoria} onValueChange={setCategoria}>
                    <SelectTrigger className="bg-[var(--cor-fundo-card)]" aria-labelledby="lb-cat"><SelectValue /></SelectTrigger>
                    <SelectContent>{CATEGORIAS.map((c) => <SelectItem key={c} value={c}>{c[0].toUpperCase() + c.slice(1)}</SelectItem>)}</SelectContent>
                  </Select>
                </div>
              </div>
              <div className="space-y-2"><Label htmlFor="tags">Tags (vírgula)</Label><Input id="tags" placeholder="ex: cidades, mobilidade, opinião" {...register("tags")} /><p className="text-xs text-[var(--cor-texto-suave)]">Ajuda a agrupar no grupo certo e nos assuntos em alta.</p></div>
              <div className="space-y-2">
                <Label htmlFor="news_cluster" className="flex items-center gap-1.5"><Link2 className="h-3.5 w-3.5" aria-hidden /> Vincular à notícia (opcional)</Label>
                <Input id="news_cluster" inputMode="numeric" placeholder="ID do agrupamento (opcional — deixe vazio se não houver)" {...register("news_cluster")} />
                <p className="text-xs text-[var(--cor-texto-suave)]">
                  Encontre o ID em <Link href="/" className="underline">últimas notícias</Link>,{" "}
                  <Link href="/buscar" className="underline">busca</Link> ou{" "}
                  <Link href={`/categoria/${categoria}`} className="underline">editoria {categoria}</Link> — a discussão aparece ligada à cobertura.
                </p>
              </div>
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label htmlFor="conteudo">Conteúdo *</Label>
                  <span className="text-xs text-[var(--cor-texto-suave)]" aria-live="polite">{contagem} caracteres {contagem < 10 ? "(mín. 10)" : ""}</span>
                </div>
                <Textarea id="conteudo" rows={10} placeholder="Escreva com contexto, fontes e opinião fundamentada..." {...register("conteudo", { required: "Informe o conteúdo" })} />{errors.conteudo && <p className="text-xs text-[var(--cor-erro)]">{errors.conteudo.message as string}</p>}
              </div>
              <div className="flex flex-wrap gap-1.5" aria-label="Prévia do formato">
                <SeloFormato formato={formato} />
              </div>
              {err && <p role="alert" className="rounded-md border border-[var(--cor-erro)] bg-[var(--cor-erro-suave)] px-3 py-2 text-sm text-[var(--cor-erro)]">{err}</p>}
              <Button type="submit" disabled={isSubmitting} className="w-full bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)] min-h-[44px] gap-1.5">{isSubmitting ? "Enviando..." : <><Send className="h-4 w-4" aria-hidden />Publicar</>}</Button>
            </form>
          </CardContent>
        </Card>

        {/* Prévia ao vivo — como vai aparecer no feed */}
        <aside aria-label="Prévia da publicação">
          <Card className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] lg:sticky lg:top-4">
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center gap-1.5 text-sm text-[var(--cor-texto)]"><Eye className="h-4 w-4 text-[var(--cor-primaria)]" aria-hidden />Como vai aparecer</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <div className="flex flex-wrap gap-1.5">
                <SeloFormato formato={formato} />
                <span className="rounded-md bg-[var(--cor-primaria)] px-2 py-0.5 text-[11px] text-[var(--cor-texto-invertido)]">{categoria}</span>
              </div>
              <p className="text-[15px] font-semibold leading-tight text-[var(--cor-texto)]">{aoVivo.titulo.trim() || "Seu título aparece aqui"}</p>
              <p className="line-clamp-6 whitespace-pre-wrap text-sm text-[var(--cor-texto-suave)]">{aoVivo.conteudo.trim() || "O começo do seu texto aparece aqui, com a mesma hierarquia do feed."}</p>
              {aoVivo.tags.trim() && (
                <div className="flex flex-wrap gap-1">
                  {aoVivo.tags.split(",").map((t) => t.trim()).filter(Boolean).slice(0, 3).map((t) => (
                    <span key={t} className="rounded-full border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] px-2 py-0.5 text-[11px] text-[var(--cor-texto-suave)]">#{t}</span>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </aside>
      </div>

      <Dialog open={okOpen} onOpenChange={setOkOpen}>
        <DialogContent className="bg-[var(--cor-fundo-card)] border-[var(--cor-borda)]">
          <DialogHeader><DialogTitle className="flex items-center gap-2 text-[var(--cor-sucesso)]"><CheckCircle2 className="h-5 w-5" aria-hidden />Publicação enviada!</DialogTitle><DialogDescription>Seu texto foi enviado para publicação e já aparece no feed.</DialogDescription></DialogHeader>
          <DialogFooter className="gap-2 sm:gap-0">
            <Button variant="outline" className="border-[var(--cor-borda)]" onClick={() => { setOkOpen(false); r.push("/comunidade"); }}>Voltar ao feed</Button>
            <Button className="bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]" onClick={() => { setOkOpen(false); if (createdId) r.push(`/comunidade/${createdId}`); else r.push("/comunidade"); }}>Ver publicação</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
