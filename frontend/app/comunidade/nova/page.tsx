"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { useAuth } from "@/lib/auth-context";
import * as api from "@/lib/api";
import { Link2, Send, CheckCircle2 } from "lucide-react";

type FormVals = { titulo: string; conteudo: string; categoria: string; tags: string; news_cluster: string };

export default function Page() {
  const { token } = useAuth();
  const r = useRouter();
  const [err, setErr] = useState<string | null>(null);
  const [tipo, setTipo] = useState<api.TipoPublicacao>("opiniao");
  const [okOpen, setOkOpen] = useState(false);
  const [createdId, setCreatedId] = useState<number | null>(null);
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<FormVals>({ defaultValues: { titulo: "", conteudo: "", categoria: "geral", tags: "", news_cluster: "" } });

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
      const pub = await api.criarRascunhoPublicacao(token, { titulo, conteudo, tipo, categoria: d.categoria.trim() || undefined, tags: tags.length ? tags : undefined });
      const enviado = await api.enviarPublicacao(token, pub.id);
      setCreatedId(enviado.id ?? pub.id);
      setOkOpen(true);
    } catch (e: unknown) { setErr(e instanceof Error ? e.message : "Falha ao publicar."); }
  };

  if (!token) return (
    <div className="mx-auto max-w-xl py-8 px-3"><Card className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]"><CardContent className="p-6 text-center"><p className="text-sm text-[var(--cor-texto-suave)]">Entre para publicar na comunidade.</p><Button onClick={() => r.push("/login")} className="mt-3 bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)] min-h-[44px]">Entrar</Button></CardContent></Card></div>
  );

  return (
    <div className="mx-auto max-w-2xl space-y-4 py-6 px-3 sm:px-0">
      <div className="hud-line" aria-hidden />
      <Card className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
        <CardHeader>
          <CardTitle className="text-[var(--cor-texto)]">Nova publicação</CardTitle>
          <CardDescription className="text-[var(--cor-texto-suave)]">Escolha o grupo (categoria), tipo e tags — opcionalmente vincule a um cluster de notícia.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-3" noValidate>
            <div className="space-y-2"><Label htmlFor="titulo">Título *</Label><Input id="titulo" placeholder="Ex: Por que a mobilidade importa" {...register("titulo", { required: "Informe o título" })} />{errors.titulo && <p className="text-xs text-[var(--cor-erro)]">{errors.titulo.message as string}</p>}</div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="space-y-2"><Label>Tipo *</Label><Select value={tipo} onValueChange={(v) => setTipo(v as api.TipoPublicacao)}><SelectTrigger className="bg-[var(--cor-fundo-card)]"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="opiniao">Opinião</SelectItem><SelectItem value="analise">Análise</SelectItem></SelectContent></Select></div>
              <div className="space-y-2"><Label htmlFor="categoria">Categoria (grupo)</Label><Select defaultValue="geral" onValueChange={() => {}}><SelectTrigger className="bg-[var(--cor-fundo-card)]"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="geral">Geral</SelectItem><SelectItem value="politica">Política</SelectItem><SelectItem value="economia">Economia</SelectItem><SelectItem value="tecnologia">Tecnologia</SelectItem><SelectItem value="esportes">Esportes</SelectItem><SelectItem value="cultura">Cultura</SelectItem><SelectItem value="saude">Saúde</SelectItem><SelectItem value="mundo">Mundo</SelectItem><SelectItem value="cidades">Cidades</SelectItem></SelectContent></Select>
                <Input id="categoria" placeholder="ou digite: politica" className="mt-1" {...register("categoria")} />
              </div>
            </div>
            <div className="space-y-2"><Label htmlFor="tags">Tags (vírgula)</Label><Input id="tags" placeholder="ex: cidades, mobilidade, opinião" {...register("tags")} /><p className="text-xs text-[var(--cor-texto-suave)]">Ajuda a agrupar no grupo certo.</p></div>
            <div className="space-y-2">
              <Label htmlFor="news_cluster" className="flex items-center gap-1.5"><Link2 className="h-3.5 w-3.5" /> Vincular a cluster (opcional)</Label>
              <Input id="news_cluster" placeholder="ID do agrupamento (opcional — deixe vazio se não houver)" {...register("news_cluster")} />
              <p className="text-xs text-[var(--cor-texto-suave)]">Opcional — deixe vazio se não houver agrupamento.</p>
            </div>
            <div className="space-y-2"><Label htmlFor="conteudo">Conteúdo *</Label><Textarea id="conteudo" rows={10} placeholder="Escreva com contexto, fontes e opinião fundamentada..." {...register("conteudo", { required: "Informe o conteúdo" })} />{errors.conteudo && <p className="text-xs text-[var(--cor-erro)]">{errors.conteudo.message as string}</p>}</div>
            <div className="flex flex-wrap gap-1.5"><Badge variant="outline" className="border-[var(--cor-borda)]">{tipo}</Badge><Badge className="bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]">comunidade</Badge></div>
            {err && <p role="alert" className="rounded-md border border-[var(--cor-erro)] bg-[var(--cor-erro-suave)] px-3 py-2 text-sm text-[var(--cor-erro)]">{err}</p>}
            <Button type="submit" disabled={isSubmitting} className="w-full bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)] min-h-[44px] gap-1.5">{isSubmitting ? "Enviando..." : <><Send className="h-4 w-4" />Publicar</>}</Button>
          </form>
        </CardContent>
      </Card>

      <Dialog open={okOpen} onOpenChange={setOkOpen}>
        <DialogContent className="bg-[var(--cor-fundo-card)] border-[var(--cor-borda)]">
          <DialogHeader><DialogTitle className="flex items-center gap-2 text-[var(--cor-sucesso)]"><CheckCircle2 className="h-5 w-5" />Publicação enviada!</DialogTitle><DialogDescription>Seu texto foi enviado para publicação e já aparece no feed.</DialogDescription></DialogHeader>
          <DialogFooter className="gap-2 sm:gap-0">
            <Button variant="outline" className="border-[var(--cor-borda)]" onClick={() => { setOkOpen(false); r.push("/comunidade"); }}>Voltar ao portal</Button>
            <Button className="bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]" onClick={() => { setOkOpen(false); if (createdId) r.push(`/comunidade/${createdId}`); else r.push("/comunidade"); }}>Ver publicação</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
