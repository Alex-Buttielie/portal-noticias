"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { useAuth } from "@/lib/auth-context";
import * as api from "@/lib/api";
import { AdsSlot } from "@/components/AdsSlot";
import { Users, MessageSquare, Shield, Flag, Send, Trash2, Pencil, UserPlus, UserMinus, Eye, ArrowLeft } from "lucide-react";

const LS_SEGUINDO = "brd_autores_seguindo";
function readLS(k: string): string[] { try { const v = localStorage.getItem(k); return v ? JSON.parse(v) as string[] : []; } catch { return []; } }
function writeLS(k: string, v: string[]) { try { localStorage.setItem(k, JSON.stringify(v)); } catch { } }

export default function Page({ params }: { params: { id: string } }) {
  const id = Number(params.id);
  const safeId = Number.isFinite(id) ? id : 1;
  const { token, usuario } = useAuth();
  const router = useRouter();
  const [pub, setPub] = useState<api.Publicacao | null>(null);
  const [loading, setLoading] = useState(true);
  const [comentarios, setComentarios] = useState<api.Comentario[]>([]);
  const [seguindo, setSeguindo] = useState<string[]>([]);
  const [perfil, setPerfil] = useState<api.PerfilAutorPublico | null>(null);
  const [openPerfil, setOpenPerfil] = useState(false);
  const [openDenuncia, setOpenDenuncia] = useState<{ open: boolean; comentarioId?: number }>({ open: false });
  const [openEditar, setOpenEditar] = useState(false);
  const [motivo, setMotivo] = useState("");
  const [comentTxt, setComentTxt] = useState("");
  const [editVals, setEditVals] = useState({ titulo: "", conteudo: "" });
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => { setSeguindo(readLS(LS_SEGUINDO)); }, []);
  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const p = await api.obterPublicacao(token, safeId);
        const resolved: api.Publicacao = p ?? { id: safeId, titulo: `Publicação #${params.id} (mock — API offline)`, conteudo: "Conteúdo mock para não quebrar build. API offline ou publicação não encontrada.", tipo: "opiniao", status: "publicado", categoria: "geral", autor: 1, autor_nome: "Autor Mock", tags: ["mock"], news_cluster: null, news_item: null, destaque: false, criado_em: new Date().toISOString(), publicado_em: new Date().toISOString() };
        if (alive) { setPub(resolved); setEditVals({ titulo: resolved.titulo, conteudo: resolved.conteudo }); }
      } catch {
        if (alive) {
          const m: api.Publicacao = { id: safeId, titulo: `Publicação #${params.id} (mock — API offline)`, conteudo: "Conteúdo mock — falha ao buscar.", tipo: "opiniao", status: "publicado", categoria: "geral", autor: 1, autor_nome: "Autor Mock", tags: ["mock"], news_cluster: null, news_item: null, destaque: false, criado_em: new Date().toISOString(), publicado_em: new Date().toISOString() };
          setPub(m); setEditVals({ titulo: m.titulo, conteudo: m.conteudo });
        }
      } finally { if (alive) setLoading(false); }
    })();
    return () => { alive = false; };
  }, [safeId, token, params.id]);

  useEffect(() => {
    let alive = true;
    (async () => {
      try { const cs = await api.obterComentarios({ publicacao: safeId }); if (alive) setComentarios(cs ?? []); } catch { if (alive) setComentarios([]); }
    })();
    return () => { alive = false; };
  }, [safeId]);

  const isAutor = !!usuario && !!pub && usuario.id === pub.autor;
  const isSeguindo = pub ? seguindo.includes(String(pub.autor)) : false;

  const toggleSeguir = async () => {
    if (!pub) return;
    const key = String(pub.autor);
    const seg = seguindo.includes(key);
    if (!token) { const n = seg ? seguindo.filter((k) => k !== key) : [...seguindo, key]; setSeguindo(n); writeLS(LS_SEGUINDO, n); setMsg(seg ? `Deixou de seguir ${pub.autor_nome}` : `Seguindo ${pub.autor_nome} (local)`); return; }
    try { if (seg) await api.deixarDeSeguirAutor(token, pub.autor); else await api.seguirAutor(token, pub.autor); const n = seg ? seguindo.filter((k) => k !== key) : [...seguindo, key]; setSeguindo(n); writeLS(LS_SEGUINDO, n); setMsg(seg ? `Deixou de seguir` : `Seguindo ${pub.autor_nome}`); } catch (e: unknown) { setErr(e instanceof Error ? e.message : "Falha ao seguir"); }
  };

  const verPerfil = async () => {
    if (!pub) return;
    try { const p = await api.obterPerfilAutor(pub.autor); setPerfil(p); } catch { setPerfil({ id: pub.autor, nome: pub.autor_nome, credenciado: false, numero_seguidores: seguindo.includes(String(pub.autor)) ? 1 : 0, publicacoes: [] }); }
    setOpenPerfil(true);
  };

  const handleComentar = async () => {
    setErr(null);
    if (!token) { setErr("Entre para comentar."); return; }
    if (comentTxt.trim().length < 2) { setErr("Comentário muito curto."); return; }
    try { const c = await api.comentar(token, { conteudo: comentTxt.trim(), publicacao: safeId }); setComentarios((prev) => [...prev, c]); setComentTxt(""); setMsg("Comentário enviado!"); } catch (e: unknown) { setErr(e instanceof Error ? e.message : "Falha ao comentar"); }
  };

  const handleExcluirComent = async (cid: number) => {
    if (!token) return;
    try { await api.excluirComentario(token, cid); setComentarios((prev) => prev.filter((c) => c.id !== cid)); setMsg("Comentário excluído."); } catch (e: unknown) { setErr(e instanceof Error ? e.message : "Falha ao excluir"); }
  };

  const handleDenunciar = async () => {
    setErr(null);
    if (!token) { setErr("Entre para denunciar."); return; }
    if (motivo.trim().length < 5) { setErr("Motivo ≥5 caracteres."); return; }
    try {
      const payload: { motivo: string; publicacao?: number; comentario?: number } = { motivo: motivo.trim() };
      if (openDenuncia.comentarioId) payload.comentario = openDenuncia.comentarioId; else payload.publicacao = safeId;
      await api.denunciar(token, payload);
      setOpenDenuncia({ open: false }); setMotivo(""); setMsg("Denúncia enviada.");
    } catch (e: unknown) { setErr(e instanceof Error ? e.message : "Falha ao denunciar"); }
  };

  const handleEditar = async () => {
    if (!token || !pub) return;
    if (editVals.titulo.trim().length < 3 || editVals.conteudo.trim().length < 10) { setErr("Título ≥3 e conteúdo ≥10."); return; }
    try { const upd = await api.editarPublicacao(token, safeId, { titulo: editVals.titulo.trim(), conteudo: editVals.conteudo.trim() }); setPub(upd); setOpenEditar(false); setMsg("Publicação atualizada."); } catch (e: unknown) { setErr(e instanceof Error ? e.message : "Falha ao editar"); }
  };

  const handleExcluirPub = async () => {
    if (!token || !pub) return;
    if (!confirm("Excluir esta publicação?")) return;
    try { await api.excluirPublicacao(token, safeId); setMsg("Publicação excluída."); router.push("/comunidade"); } catch (e: unknown) { setErr(e instanceof Error ? e.message : "Falha ao excluir"); }
  };

  if (loading || !pub) return <div className="mx-auto max-w-2xl py-6 px-3"><Card className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]"><CardContent className="p-6 text-sm text-[var(--cor-texto-suave)]">Carregando...</CardContent></Card></div>;

  return (
    <div className="mx-auto max-w-2xl space-y-4 py-6 px-3 sm:px-0">
      <div className="hud-line" aria-hidden />
      <Link href="/comunidade" className="inline-flex items-center gap-1 text-sm text-[var(--cor-texto-suave)] hover:text-[var(--cor-texto)] hover:underline"><ArrowLeft className="h-4 w-4" />Comunidade</Link>

      {(msg || err) && <div className={`rounded-md border px-3 py-2 text-sm ${err ? "border-[var(--cor-erro)] bg-[var(--cor-erro-suave)] text-[var(--cor-erro)]" : "border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] text-[var(--cor-texto)]"}`} role="alert">{err || msg} <button onClick={() => { setMsg(null); setErr(null); }} className="ml-2 underline text-xs">fechar</button></div>}

      <div className="space-y-2">
        <div className="flex flex-wrap gap-2">
          <Badge variant="outline" className="border-[var(--cor-borda)]">{pub.tipo}</Badge>
          <Badge className="bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]">{pub.categoria}</Badge>
          {pub.destaque && <Badge variant="secondary">Destaque</Badge>}
          <span className="text-xs text-[var(--cor-texto-suave)]">#{pub.id} · {new Date(pub.criado_em).toLocaleString("pt-BR")}</span>
        </div>
        <h1 className="text-2xl font-bold leading-tight text-[var(--cor-texto)]">{pub.titulo}</h1>
        <div className="flex flex-wrap items-center gap-2 rounded-[var(--raio-lg)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] p-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-[var(--cor-primaria-suave)] border border-[var(--cor-borda)]"><Users className="h-5 w-5 text-[var(--cor-primaria)]" /></div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-[var(--cor-texto)]">{pub.autor_nome}</p>
            <p className="text-xs text-[var(--cor-texto-suave)]">Autor · comunidade {pub.categoria}</p>
          </div>
          <div className="flex gap-1.5">
            <Button size="sm" variant={isSeguindo ? "secondary" : "outline"} className="h-8 gap-1 border-[var(--cor-borda)]" onClick={toggleSeguir}>{isSeguindo ? <><UserMinus className="h-3.5 w-3.5" />Seguindo</> : <><UserPlus className="h-3.5 w-3.5" />Seguir</>}</Button>
            <Button size="sm" variant="outline" className="h-8 gap-1 border-[var(--cor-borda)]" onClick={verPerfil}><Eye className="h-3.5 w-3.5" />Perfil</Button>
          </div>
        </div>
        {!!pub.tags.length && <div className="flex flex-wrap gap-1">{pub.tags.map((t) => <span key={t} className="rounded-full border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] px-2 py-0.5 text-xs text-[var(--cor-texto-suave)]">#{t}</span>)}</div>}
      </div>

      <Card className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
        <CardContent className="p-5"><p className="whitespace-pre-wrap leading-relaxed text-[var(--cor-texto)]">{pub.conteudo}</p></CardContent>
      </Card>

      <div className="flex flex-wrap gap-2">
        <Button size="sm" variant="outline" className="gap-1 border-[var(--cor-borda)]" onClick={() => setOpenDenuncia({ open: true })}><Flag className="h-4 w-4" />Denunciar</Button>
        {isAutor && <>
          <Button size="sm" variant="outline" className="gap-1 border-[var(--cor-borda)]" onClick={() => setOpenEditar(true)}><Pencil className="h-4 w-4" />Editar</Button>
          <Button size="sm" variant="destructive" className="gap-1" onClick={handleExcluirPub}><Trash2 className="h-4 w-4" />Excluir</Button>
        </>}
      </div>

      <AdsSlot id={`comunidade-detalhe-${safeId}`} formato="in-feed" />

      <Card className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
        <CardHeader className="pb-2"><CardTitle className="flex items-center gap-2 text-base text-[var(--cor-texto)]"><MessageSquare className="h-4 w-4" />Comentários ({comentarios.length})</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <div className="flex gap-2">
            <Textarea rows={3} placeholder={token ? "Escreva um comentário..." : "Entre para comentar"} value={comentTxt} onChange={(e) => setComentTxt(e.target.value)} disabled={!token} className="flex-1" />
            <Button onClick={handleComentar} disabled={!token} className="self-end bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)] gap-1 min-h-[44px]"><Send className="h-4 w-4" />Enviar</Button>
          </div>
          {!token && <p className="text-xs text-[var(--cor-texto-suave)]">Você precisa estar logado para comentar.</p>}
          <div className="space-y-2">
            {comentarios.length === 0 ? <p className="text-sm text-[var(--cor-texto-suave)]">Seja o primeiro a comentar.</p> : comentarios.map((c) => (
              <div key={c.id} className="rounded-[var(--raio-md)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-3">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-medium text-[var(--cor-texto)]">{c.autor_nome}</span>
                  <span className="text-xs text-[var(--cor-texto-suave)]">{new Date(c.criado_em).toLocaleString("pt-BR")}</span>
                </div>
                <p className="mt-1 text-sm text-[var(--cor-texto)] whitespace-pre-wrap">{c.conteudo}</p>
                <div className="mt-2 flex gap-1.5">
                  <Button size="sm" variant="ghost" className="h-7 text-xs gap-1" onClick={() => setOpenDenuncia({ open: true, comentarioId: c.id })}><Shield className="h-3 w-3" />Denunciar</Button>
                  {usuario && usuario.id === c.autor && <Button size="sm" variant="ghost" className="h-7 text-xs gap-1 text-[var(--cor-erro)]" onClick={() => handleExcluirComent(c.id)}><Trash2 className="h-3 w-3" />Excluir</Button>}
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <Dialog open={openPerfil} onOpenChange={setOpenPerfil}>
        <DialogContent className="bg-[var(--cor-fundo-card)] border-[var(--cor-borda)]">
          <DialogHeader><DialogTitle>{perfil?.nome ?? pub.autor_nome}</DialogTitle><DialogDescription>Perfil público do autor</DialogDescription></DialogHeader>
          {perfil ? (
            <div className="space-y-2 text-sm">
              <p className="text-[var(--cor-texto)]">Seguidores: <strong>{perfil.numero_seguidores}</strong> {perfil.credenciado && <Badge className="ml-2 bg-[var(--cor-sucesso)] text-white">Credenciado</Badge>}</p>
              {perfil.publicacoes.length > 0 && <div className="space-y-1"><p className="font-medium text-[var(--cor-texto)]">Publicações recentes</p>{perfil.publicacoes.slice(0, 3).map((p) => <Link key={p.id} href={`/comunidade/${p.id}`} className="block rounded-md border border-[var(--cor-borda)] p-2 hover:bg-[var(--cor-primaria-suave)] text-[var(--cor-texto)] text-sm">{p.titulo}</Link>)}</div>}
            </div>
          ) : <p className="text-sm text-[var(--cor-texto-suave)]">Carregando...</p>}
          <DialogFooter><Button variant="outline" onClick={() => setOpenPerfil(false)} className="border-[var(--cor-borda)]">Fechar</Button><Button onClick={toggleSeguir} className="bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)] gap-1">{isSeguindo ? <><UserMinus className="h-4 w-4" />Deixar de seguir</> : <><UserPlus className="h-4 w-4" />Seguir autor</>}</Button></DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={openDenuncia.open} onOpenChange={(o) => setOpenDenuncia((s) => ({ ...s, open: o }))}>
        <DialogContent className="bg-[var(--cor-fundo-card)] border-[var(--cor-borda)]">
          <DialogHeader><DialogTitle className="flex items-center gap-2"><Shield className="h-4 w-4" />Denunciar {openDenuncia.comentarioId ? "comentário" : "publicação"}</DialogTitle><DialogDescription>Informe o motivo — a moderação irá avaliar.</DialogDescription></DialogHeader>
          <div className="space-y-1.5"><Label htmlFor="motivo-d">Motivo</Label><Textarea id="motivo-d" rows={3} value={motivo} onChange={(e) => setMotivo(e.target.value)} placeholder="Descreva a violação..." /></div>
          <DialogFooter><Button variant="outline" onClick={() => setOpenDenuncia({ open: false })} className="border-[var(--cor-borda)]">Cancelar</Button><Button variant="destructive" onClick={handleDenunciar} className="gap-1"><Flag className="h-4 w-4" />Enviar</Button></DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={openEditar} onOpenChange={setOpenEditar}>
        <DialogContent className="bg-[var(--cor-fundo-card)] border-[var(--cor-borda)]">
          <DialogHeader><DialogTitle>Editar publicação</DialogTitle><DialogDescription>Apenas o autor pode editar.</DialogDescription></DialogHeader>
          <div className="space-y-3">
            <div className="space-y-1.5"><Label htmlFor="ed-titulo">Título</Label><Input id="ed-titulo" value={editVals.titulo} onChange={(e) => setEditVals((s) => ({ ...s, titulo: e.target.value }))} /></div>
            <div className="space-y-1.5"><Label htmlFor="ed-conteudo">Conteúdo</Label><Textarea id="ed-conteudo" rows={8} value={editVals.conteudo} onChange={(e) => setEditVals((s) => ({ ...s, conteudo: e.target.value }))} /></div>
          </div>
          <DialogFooter><Button variant="outline" onClick={() => setOpenEditar(false)} className="border-[var(--cor-borda)]">Cancelar</Button><Button onClick={handleEditar} className="bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)] gap-1"><Pencil className="h-4 w-4" />Salvar</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
