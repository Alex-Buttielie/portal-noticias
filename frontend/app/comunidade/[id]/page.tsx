"use client";
import { useEffect, useMemo, useState } from "react";
import * as api from "@/lib/api";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { SeloFormato, formatoDaPublicacao } from "@/components/comunidade/TipoSelo";
import { useAuth } from "@/lib/auth-context";
import { useQueryPublicacaoComunidade } from "@/lib/queries";
import { registrarEventoComunidade } from "@/lib/interacoes-comunidade";
import { formatarDataHoraCompleta } from "@/lib/datas";
import { AdsSlot } from "@/components/AdsSlot";
import {
  Users, MessageSquare, MessagesSquare, Shield, Flag, Send, Trash2, Pencil,
  UserPlus, UserMinus, Eye, ArrowLeft, Link2, Flame, CornerDownRight, RotateCcw,
} from "lucide-react";

const LS_SEGUINDO = "brd_autores_seguindo";
function readLS(k: string): string[] { try { const v = localStorage.getItem(k); return v ? JSON.parse(v) as string[] : []; } catch { return []; } }
function writeLS(k: string, v: string[]) { try { localStorage.setItem(k, JSON.stringify(v)); } catch { } }

function fallbackPub(id: number, rawId: string): any {
  return { id, titulo: `Publicação #${rawId}`, conteudo: "Conteúdo indisponível no momento.", tipo: "opiniao", status: "publicado", categoria: "geral", autor: 1, autor_nome: "Autor Exemplo", tags: ["exemplo"], news_cluster: null, news_item: null, destaque: false, numero_comentarios: 0, criado_em: new Date().toISOString(), publicado_em: new Date().toISOString() };
}

export default function Page({ params }: { params: { id: string } }) {
  const id = Number(params.id);
  const safeId = Number.isFinite(id) ? id : 1;
  const { token, usuario } = useAuth();
  const router = useRouter();

  const [pub, setPub] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [erroPub, setErroPub] = useState<string | null>(null);
  const [comentarios, setComentarios] = useState<any[]>([]);
  const [relacionadas, setRelacionadas] = useState<any[]>([]);
  const [noticiasRel, setNoticiasRel] = useState<any[]>([]);
  const [seguindo, setSeguindo] = useState<string[]>([]);
  const [perfil, setPerfil] = useState<any>(null);
  const [openPerfil, setOpenPerfil] = useState(false);
  const [openDenuncia, setOpenDenuncia] = useState<{ open: boolean; comentarioId?: number }>({ open: false });
  const [openEditar, setOpenEditar] = useState(false);
  const [responderA, setResponderA] = useState<any>(null);
  const [motivo, setMotivo] = useState("");
  const [comentTxt, setComentTxt] = useState("");
  const [editVals, setEditVals] = useState({ titulo: "", conteudo: "" });
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  // --- MIGRATION: useQueryPublicacaoComunidade para dados da publicação ---
  const pubQuery = useQueryPublicacaoComunidade({
    id: safeId,
    token,
    usuarioId: usuario?.id ?? null,
  });

  useEffect(() => {
    // Sincronizar dados da query ao mudar de usuário ou fazer login
    if (pubQuery.data) {
      setPub(pubQuery.data);
      setEditVals({ titulo: pubQuery.data.titulo, conteudo: pubQuery.data.conteudo });
    }
    if (pubQuery.isError && !pub) {
      setErroPub("Publicação indisponível — mostrando cópia local.");
    }
    // `pub` entrou nas dependências: a condição `!pub` LÊ o estado, e sem ele a
    // lista continuava incompleta (react-hooks/exhaustive-deps). Nenhum ciclo:
    // `setPub(pubQuery.data)` recebe a MESMA referência do cache a cada render,
    // e `setEditVals` só roda quando `pubQuery.data` muda de fato.
  }, [pubQuery.data, pubQuery.isError, usuario?.id, pub]);

  // Preservar LS de grupos ao mudar de página
  useEffect(() => { setSeguindo(readLS(LS_SEGUINDO)); }, []);

  // Substituir o recarregar manual pela query
  const recarregar = async () => {
    setLoading(true);
    setErroPub(null);
    try {
      // refetch da query da publicação (a key crua ["publicacao", safeId]
      // não prefixa a key real e seria um no-op).
      await pubQuery.refetch();
    } catch {
      // fallback silencioso
    } finally {
      setLoading(false);
    }
  };

  // Efeitos que continuam usando API manual (comentários, feed, perfil) —
  // mantidos para não quebrar o fluxo existente de mutations/localStorage.
  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const cs = await api.obterComentarios({ publicacao: safeId });
        if (alive) setComentarios(cs ?? []);
      } catch {
        if (alive) setComentarios([]);
      }
    })();
    return () => { alive = false; };
  }, [safeId]);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const pl = await api.obterPublicacoes({ categoria: pub?.categoria || undefined, ordenar: "discutidos" });
        if (alive) setRelacionadas((pl ?? []).filter((p) => p.id !== safeId).slice(0, 4));
      } catch { if (alive) setRelacionadas([]); }
      try {
        const feed = await api.obterFeed({ categoria: pub?.categoria || undefined });
        if (alive) setNoticiasRel((feed.results ?? []).slice(0, 3));
      } catch { if (alive) setNoticiasRel([]); }
    })();
    return () => { alive = false; };
  }, [pub?.categoria, safeId]);

  useEffect(() => {
    let vivo = true;
    (async () => {
      try {
        const p = await api.obterPerfilAutor(pub?.autor);
        if (vivo) setPerfil(p);
      } catch { vivo = false; }
    })();
    return () => { vivo = false; };
  }, [pub?.autor]);

  // Thread 1 nível: topo + respostas agrupadas.
  const { tops, respostasPor } = useMemo(() => {
    const tops = comentarios.filter((c) => !c.resposta_de);
    const respostasPor: Record<number, any[]> = {};
    for (const c of comentarios) {
      if (c.resposta_de) {
        (respostasPor[c.resposta_de] ||= []).push(c);
      }
    }
    return { tops, respostasPor };
  }, [comentarios]);

  const isAutor = !!usuario && !!pub && usuario.id === pub?.autor;
  const isSeguindo = pub ? seguindo.includes(String(pub.autor)) : false;
  const formato = formatoDaPublicacao(pub?.tipo ?? "opiniao", comentarios.length);

  const toggleSeguir = async () => {
    if (!pub) return;
    const key = String(pub.autor);
    const seg = seguindo.includes(key);
    if (!token) { const n = seg ? seguindo.filter((k) => k !== key) : [...seguindo, key]; setSeguindo(n); writeLS(LS_SEGUINDO, n); setMsg(seg ? `Deixou de seguir ${pub.autor_nome}` : `Seguindo ${pub.autor_nome} (local)`); return; }
    try {
      if (seg) { await api.deixarDeSeguirAutor(token, pub.autor); registrarEventoComunidade("deixar_seguir", { publicacaoId: pub.id }); }
      else { await api.seguirAutor(token, pub.autor); registrarEventoComunidade("seguir_autor", { publicacaoId: pub.id }); }
      const n = seg ? seguindo.filter((k) => k !== key) : [...seguindo, key]; setSeguindo(n); writeLS(LS_SEGUINDO, n);
      setMsg(seg ? `Deixou de seguir` : `Seguindo ${pub.autor_nome}`);
    } catch (e: unknown) { setErr(e instanceof Error ? e.message : "Falha ao seguir"); }
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
    try {
      const payload: { conteudo: string; publicacao: number; resposta_de?: number } = { conteudo: comentTxt.trim(), publicacao: safeId };
      if (responderA) payload.resposta_de = responderA.id;
      const c = await api.comentar(token, payload);
      setComentarios((prev) => [...prev, c]);
      setComentTxt(""); setResponderA(null); setMsg(responderA ? "Resposta enviada!" : "Comentário enviado!");
      registrarEventoComunidade(responderA ? "responder" : "comentar", { publicacaoId: safeId });
    } catch (e: unknown) { setErr(e instanceof Error ? e.message : "Falha ao comentar"); }
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
      registrarEventoComunidade("denunciar", { publicacaoId: safeId });
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

  if (loading || !pub) {
    return (
      <div className="mx-auto max-w-6xl py-6 px-3" aria-busy="true" aria-label="Carregando discussão">
        <div className="animate-pulse space-y-3">
          <div className="h-4 w-32 rounded bg-[var(--cor-fundo-elevado)]" />
          <div className="h-8 w-2/3 rounded bg-[var(--cor-fundo-elevado)]" />
          <div className="h-40 rounded-[var(--raio-lg)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]" />
        </div>
      </div>
    );
  }

  const noticiaVinculada = pub.news_cluster
    ? { href: `/noticia/cluster/${pub.news_cluster}`, rotulo: `Notícia relacionada (agrupamento #${pub.news_cluster})` }
    : pub.news_item
      ? { href: `/noticia/item/${pub.news_item}`, rotulo: `Notícia relacionada (#${pub.news_item})` }
      : null;

  const BlocoComentario = ({ c, ehResposta = false }: { c: any; ehResposta?: boolean }) => (
    <div className={ehResposta ? "ml-6 border-l-2 border-[var(--cor-borda)] pl-3" : ""}>
      <div className="rounded-[var(--raio-md)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-3">
        <div className="flex items-center justify-between gap-2">
          <span className="inline-flex items-center gap-1.5 text-sm font-medium text-[var(--cor-texto)]">
            {ehResposta && <CornerDownRight className="h-3.5 w-3.5 text-[var(--cor-texto-suave)]" aria-hidden />}
            {c.autor_nome}
            <Badge variant="outline" className="border-[var(--cor-borda)] text-[10px]">Comentário</Badge>
          </span>
          <span className="text-xs text-[var(--cor-texto-suave)]">{formatarDataHoraCompleta(c.criado_em)}</span>
        </div>
        <p className="mt-1 text-sm text-[var(--cor-texto)] whitespace-pre-wrap">{c.conteudo}</p>
        <div className="mt-2 flex flex-wrap gap-1.5">
          {!ehResposta && (
            <Button size="sm" variant="ghost" className="h-7 text-xs gap-1" onClick={() => setResponderA(c)} aria-label={`Responder ${c.autor_nome}`}>
              <CornerDownRight className="h-3 w-3" aria-hidden />Responder
            </Button>
          )}
          <Button size="sm" variant="ghost" className="h-7 text-xs gap-1" onClick={() => setOpenDenuncia({ open: true, comentarioId: c.id })}><Shield className="h-3 w-3" aria-hidden />Denunciar</Button>
          {usuario && usuario.id === c.autor && <Button size="sm" variant="ghost" className="h-7 text-xs gap-1 text-[var(--cor-erro)]" onClick={() => handleExcluirComent(c.id)}><Trash2 className="h-3 w-3" aria-hidden />Excluir</Button>}
        </div>
      </div>
      {!ehResposta && (respostasPor[c.id] ?? []).map((r) => <div key={r.id} className="mt-2"><BlocoComentario c={r} ehResposta /></div>)}
    </div>
  );

  return (
    <div className="mx-auto max-w-6xl space-y-4 py-6 px-3 sm:px-0">
      <div className="hud-line" aria-hidden />
      <Link href="/comunidade" className="inline-flex min-h-[44px] items-center gap-1 text-sm text-[var(--cor-texto-suave)] hover:text-[var(--cor-texto)] hover:underline"><ArrowLeft className="h-4 w-4" aria-hidden />Comunidade</Link>

      {(msg || err) && <div className={`rounded-md border px-3 py-2 text-sm ${err ? "border-[var(--cor-erro)] bg-[var(--cor-erro-suave)] text-[var(--cor-erro)]" : "border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] text-[var(--cor-texto)]"}`} role="alert">{err || msg} <button onClick={() => { setMsg(null); setErr(null); }} className="ml-2 underline text-xs">fechar</button></div>}
      {erroPub && (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900" role="alert">
          <span>{erroPub}</span>
          <Button size="sm" variant="outline" className="gap-1" onClick={recarregar}><RotateCcw className="h-3.5 w-3.5" aria-hidden />Tentar de novo</Button>
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-[1fr_320px]">
        <article className="min-w-0 space-y-3">
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <SeloFormato formato={formato} />
              <Badge className="bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]">{pub.categoria || "geral"}</Badge>
              {pub.destaque && <Badge variant="secondary">Destaque</Badge>}
              <span className="inline-flex items-center gap-1 text-xs text-[var(--cor-texto-suave)]">
                <MessagesSquare className="h-3.5 w-3.5" aria-hidden />{comentarios.length} {comentarios.length === 1 ? "comentário" : "comentários"}
              </span>
              <span className="text-xs text-[var(--cor-texto-suave)]">#{pub.id} · {formatarDataHoraCompleta(pub.criado_em)}</span>
            </div>
            <h1 className="text-2xl font-bold leading-tight text-[var(--cor-texto)]">{pub.titulo}</h1>
            <div className="flex flex-wrap items-center gap-2 rounded-[var(--raio-lg)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] p-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-full bg-[var(--cor-primaria-suave)] border border-[var(--cor-borda)]"><Users className="h-5 w-5 text-[var(--cor-primaria)]" aria-hidden /></div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-[var(--cor-texto)]">{pub.autor_nome}</p>
                <p className="text-xs text-[var(--cor-texto-suave)]">Autor · comunidade {pub.categoria}</p>
              </div>
              <div className="flex gap-1.5">
                <Button size="sm" variant={isSeguindo ? "secondary" : "outline"} className="h-8 gap-1 border-[var(--cor-borda)]" onClick={toggleSeguir} aria-pressed={isSeguindo}>{isSeguindo ? <><UserMinus className="h-3.5 w-3.5" aria-hidden />Seguindo</> : <><UserPlus className="h-3.5 w-3.5" aria-hidden />Seguir</>}</Button>
                <Button size="sm" variant="outline" className="h-8 gap-1 border-[var(--cor-borda)]" onClick={verPerfil}><Eye className="h-3.5 w-3.5" aria-hidden />Perfil</Button>
              </div>
            </div>
            {!!pub.tags.length && <div className="flex flex-wrap gap-1">{pub.tags.map((t: string) => <span key={t} className="rounded-full border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] px-2 py-0.5 text-xs text-[var(--cor-texto-suave)]">#{t}</span>)}</div>}
          </div>

          <Card className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
            <CardContent className="p-5"><p className="whitespace-pre-wrap text-[var(--cor-texto)]">{pub.conteudo}</p></CardContent>
          </Card>

          {/* Notícia relacionada — ponte com o ecossistema */}
          {noticiaVinculada && (
            <Link
              href={noticiaVinculada.href}
              onClick={() => registrarEventoComunidade("clicar_noticia_relacionada", { publicacaoId: pub.id, destino: noticiaVinculada.href })}
              className="flex items-center gap-2 rounded-[var(--raio-lg)] border border-sky-300 bg-sky-50 p-3 text-sm text-sky-900 hover:underline dark:border-sky-800 dark:bg-sky-950 dark:text-sky-200"
            >
              <Link2 className="h-4 w-4 shrink-0" aria-hidden />{noticiaVinculada.rotulo} — ler a cobertura completa
            </Link>
          )}

          <div className="flex flex-wrap gap-2">
            <Button size="sm" variant="outline" className="gap-1 border-[var(--cor-borda)]" onClick={() => setOpenDenuncia({ open: true })}><Flag className="h-4 w-4" aria-hidden />Denunciar</Button>
            {isAutor && <>
              <Button size="sm" variant="outline" className="gap-1 border-[var(--cor-borda)]" onClick={() => setOpenEditar(true)}><Pencil className="h-4 w-4" aria-hidden />Editar</Button>
              <Button size="sm" variant="destructive" className="gap-1" onClick={handleExcluirPub}><Trash2 className="h-4 w-4" aria-hidden />Excluir</Button>
            </>}
          </div>

          <AdsSlot id={`comunidade-detalhe-${safeId}`} formato="in-feed" />

          <Card className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
            <CardHeader className="pb-2"><CardTitle className="flex items-center gap-2 text-base text-[var(--cor-texto)]"><MessageSquare className="h-4 w-4" aria-hidden />Comentários e respostas ({comentarios.length})</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              {responderA && (
                <div className="flex items-center justify-between gap-2 rounded-md border border-[var(--cor-borda)] bg-[var(--cor-primaria-suave)] px-3 py-2 text-sm text-[var(--cor-texto)]">
                  <span className="inline-flex items-center gap-1"><CornerDownRight className="h-3.5 w-3.5" aria-hidden />Respondendo a <strong>{responderA.autor_nome}</strong></span>
                  <button onClick={() => setResponderA(null)} className="text-xs underline">cancelar</button>
                </div>
              )}
              <div className="flex gap-2">
                <Textarea rows={3} placeholder={token ? (responderA ? `Responder a ${responderA.autor_nome}...` : "Escreva um comentário...") : "Entre para comentar"} value={comentTxt} onChange={(e) => setComentTxt(e.target.value)} disabled={!token} className="flex-1" aria-label="Escrever comentário" />
                <Button onClick={handleComentar} disabled={!token} className="self-end bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)] gap-1 min-h-[44px]"><Send className="h-4 w-4" aria-hidden />Enviar</Button>
              </div>
              {!token && <p className="text-xs text-[var(--cor-texto-suave)]">Você precisa estar logado para comentar.</p>}
              <div className="space-y-2" aria-live="polite">
                {tops.length === 0 ? <p className="text-sm text-[var(--cor-texto-suave)]">Seja o primeiro a comentar.</p> : tops.map((c) => <BlocoComentario key={c.id} c={c} />)}
              </div>
            </CardContent>
          </Card>
        </article>

        {/* Lateral: contexto do ecossistema */}
        <aside className="min-w-0 space-y-3" aria-label="Contexto da discussão">
          {(noticiaVinculada || noticiasRel.length > 0) && (
            <Card className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
              <CardHeader className="pb-2"><CardTitle className="flex items-center gap-1.5 text-sm text-[var(--cor-texto)]"><Link2 className="h-4 w-4 text-[var(--cor-primaria)]" aria-hidden />Na cobertura</CardTitle></CardHeader>
              <CardContent className="space-y-1.5">
                {noticiasRel.map((n) => (
                  <Link
                    key={`${n.tipo}-${n.id}`}
                    href={n.tipo === "cluster" ? `/noticia/cluster/${n.id}` : `/noticia/item/${n.id}`}
                    onClick={() => registrarEventoComunidade("clicar_noticia_relacionada", { publicacaoId: pub.id, destino: `${n.tipo}/${n.id}` })}
                    className="block rounded-md border border-[var(--cor-borda)] p-2 hover:bg-[var(--cor-primaria-suave)]"
                  >
                    <Badge variant="outline" className="border-[var(--cor-borda)] text-[10px]">Notícia · {n.categoria}</Badge>
                    <p className="mt-1 text-sm font-medium text-[var(--cor-texto)] line-clamp-2">{n.titulo}</p>
                  </Link>
                ))}
                {noticiasRel.length === 0 && noticiaVinculada && (
                  <Link href={noticiaVinculada.href} className="block rounded-md border border-[var(--cor-borda)] p-2 text-sm text-[var(--cor-texto)] hover:bg-[var(--cor-primaria-suave)]">{noticiaVinculada.rotulo}</Link>
                )}
              </CardContent>
            </Card>
          )}
          <Card className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
            <CardHeader className="pb-2"><CardTitle className="flex items-center gap-1.5 text-sm text-[var(--cor-texto)]"><Flame className="h-4 w-4 text-[var(--cor-primaria)]" aria-hidden />Nesta editoria</CardTitle></CardHeader>
            <CardContent className="space-y-1.5">
              {relacionadas.length === 0 && <p className="text-xs text-[var(--cor-texto-suave)]">Nenhuma outra discussão em {pub.categoria} ainda.</p>}
              {relacionadas.map((r) => (
                <Link key={r.id} href={`/comunidade/${r.id}`} className="block rounded-md p-1.5 hover:bg-[var(--cor-primaria-suive)]">
                  <p className="truncate text-sm font-medium text-[var(--cor-texto)]">{r.titulo}</p>
                  <p className="text-xs text-[var(--cor-texto-suave)]">{r.numero_comentarios ?? 0} comentários · {r.autor_nome}</p>
                </Link>
              ))}
              <Button size="sm" variant="outline" className="w-full border-[var(--cor-borda)]" asChild>
                <Link href="/comunidade">Ver toda a comunidade</Link>
              </Button>
            </CardContent>
          </Card>
        </aside>
      </div>

      <Dialog open={openPerfil} onOpenChange={setOpenPerfil}>
        <DialogContent className="bg-[var(--cor-fundo-card)] border-[var(--cor-borda)]">
          <DialogHeader><DialogTitle>{perfil?.nome ?? pub.autor_nome}</DialogTitle><DialogDescription>Perfil público do autor</DialogDescription></DialogHeader>
          {perfil ? (
            <div className="space-y-2 text-sm">
              <p className="text-[var(--cor-texto)]">Seguidores: <strong>{perfil.numero_seguidores}</strong> {perfil.credenciado && <Badge className="ml-2 bg-[var(--cor-sucesso)] text-white">Credenciado</Badge>}</p>
              {perfil.publicacoes.length > 0 && <div className="space-y-1"><p className="font-medium text-[var(--cor-texto)]">Publicações recentes</p>{perfil.publicacoes.slice(0, 3).map((p: { id: number; titulo: string }) => <Link key={p.id} href={`/comunidade/${p.id}`} className="block rounded-md border border-[var(--cor-borda)] p-2 hover:bg-[var(--cor-primaria-suave)] text-[var(--cor-texto)] text-sm">{p.titulo}</Link>)}</div>}
            </div>
          ) : <p className="text-sm text-[var(--cor-texto-suave)]">Carregando...</p>}
          <DialogFooter><Button variant="outline" onClick={() => setOpenPerfil(false)} className="border-[var(--cor-borda)]">Fechar</Button><Button onClick={toggleSeguir} className="bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)] gap-1">{isSeguindo ? <><UserMinus className="h-4 w-4" aria-hidden />Deixar de seguir</> : <><UserPlus className="h-4 w-4" aria-hidden />Seguir autor</>}</Button></DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={openDenuncia.open} onOpenChange={(o) => setOpenDenuncia((s) => ({ ...s, open: o }))}>
        <DialogContent className="bg-[var(--cor-fundo-card)] border-[var(--cor-borda)]">
          <DialogHeader><DialogTitle className="flex items-center gap-2"><Shield className="h-4 w-4" aria-hidden />Denunciar {openDenuncia.comentarioId ? "comentário" : "publicação"}</DialogTitle><DialogDescription>Informe o motivo — a moderação irá avaliar.</DialogDescription></DialogHeader>
          <div className="space-y-1.5"><Label htmlFor="motivo-d">Motivo</Label><Textarea id="motivo-d" rows={3} value={motivo} onChange={(e) => setMotivo(e.target.value)} placeholder="Descreva a violação..." /></div>
          <DialogFooter><Button variant="outline" onClick={() => setOpenDenuncia({ open: false })} className="border-[var(--cor-borda)]">Cancelar</Button><Button variant="destructive" onClick={handleDenunciar} className="gap-1"><Flag className="h-4 w-4" aria-hidden />Enviar</Button></DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={openEditar} onOpenChange={setOpenEditar}>
        <DialogContent className="bg-[var(--cor-fundo-card)] border-[var(--cor-borda)]">
          <DialogHeader><DialogTitle>Editar publicação</DialogTitle><DialogDescription>Apenas o autor pode editar.</DialogDescription></DialogHeader>
          <div className="space-y-3">
            <div className="space-y-1.5"><Label htmlFor="ed-titulo">Título</Label><Input id="ed-titulo" value={editVals.titulo} onChange={(e) => setEditVals((s) => ({ ...s, titulo: e.target.value }))} /></div>
            <div className="space-y-1.5"><Label htmlFor="ed-conteudo">Conteúdo</Label><Textarea id="ed-conteudo" rows={8} value={editVals.conteudo} onChange={(e) => setEditVals((s) => ({ ...s, conteudo: e.target.value }))} /></div>
          </div>
          <DialogFooter><Button variant="outline" onClick={() => setOpenEditar(false)} className="border-[var(--cor-borda)]">Cancelar</Button><Button onClick={handleEditar} className="bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)] gap-1"><Pencil className="h-4 w-4" aria-hidden />Salvar</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}