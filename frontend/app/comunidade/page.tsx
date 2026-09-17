"use client";
import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { AdsSlot } from "@/components/AdsSlot";
import { useAuth } from "@/lib/auth-context";
import * as api from "@/lib/api";
import { cn } from "@/lib/utils";
import { Users, MessageSquare, Shield, Newspaper, Star, Search, Filter, LogIn, Plus, Eye, UserPlus, UserMinus, Send, Flag } from "lucide-react";

type Grupo = { slug: string; nome: string; desc: string };
const GRUPOS: Grupo[] = [
  { slug: "politica", nome: "Política", desc: "Análises e opiniões sobre poder e decisões." },
  { slug: "economia", nome: "Economia", desc: "Mercado, inflação e bolso no dia a dia." },
  { slug: "tecnologia", nome: "Tecnologia", desc: "IA, plataformas e impacto digital." },
  { slug: "esportes", nome: "Esportes", desc: "Bastidores, opinião e análise tática." },
  { slug: "cultura", nome: "Cultura", desc: "Livros, cinema, música e cena local." },
  { slug: "saude", nome: "Saúde", desc: "Ciência, bem-estar e serviço." },
  { slug: "mundo", nome: "Mundo", desc: "Geopolítica e correspondência." },
  { slug: "cidades", nome: "Cidades", desc: "Mobilidade, bairros e vida urbana." },
  { slug: "geral", nome: "Geral", desc: "Pautas transversais e comunidade aberta." },
];
const LS_GRUPOS = "brd_comunidades_membros";
const LS_SEGUINDO = "brd_autores_seguindo";

function readLS(key: string): string[] { try { const v = localStorage.getItem(key); return v ? JSON.parse(v) as string[] : []; } catch { return []; } }
function writeLS(key: string, v: string[]) { try { localStorage.setItem(key, JSON.stringify(v)); } catch { } }

const MOCK_PUBS: api.Publicacao[] = [
  { id: 901, autor: 1, autor_nome: "Ana Política", titulo: "Opinião: reforma e cidades", conteudo: "Análise curta sobre impacto urbano.", tipo: "opiniao", status: "publicado", categoria: "politica", tags: ["exemplo", "cidades"], news_cluster: null, news_item: null, destaque: true, criado_em: new Date().toISOString(), publicado_em: new Date().toISOString() },
  { id: 902, autor: 2, autor_nome: "Bruno Tech", titulo: "Análise: IA no jornalismo", conteudo: "Como IA reorganiza redação e checagem.", tipo: "analise", status: "publicado", categoria: "tecnologia", tags: ["ia", "exemplo"], news_cluster: null, news_item: null, destaque: false, criado_em: new Date().toISOString(), publicado_em: new Date().toISOString() },
];

export default function Page() {
  const { token } = useAuth();
  const [pubs, setPubs] = useState<api.Publicacao[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState("feed");
  const [tipoFiltro, setTipoFiltro] = useState<string>("todos");
  const [catFiltro, setCatFiltro] = useState<string>("todas");
  const [destaqueOnly, setDestaqueOnly] = useState(false);
  const [busca, setBusca] = useState("");
  const [grupoFiltro, setGrupoFiltro] = useState<string | null>(null);
  const [membros, setMembros] = useState<string[]>([]);
  const [seguindo, setSeguindo] = useState<string[]>([]);
  const [openCriar, setOpenCriar] = useState(false);
  const [openDenuncia, setOpenDenuncia] = useState<{ open: boolean; pubId?: number; comentarioId?: number }>({ open: false });
  const [openComentar, setOpenComentar] = useState<{ open: boolean; pubId?: number }>({ open: false });
  const [motivo, setMotivo] = useState("");
  const [comentarioTxt, setComentarioTxt] = useState("");
  const [criar, setCriar] = useState({ titulo: "", conteudo: "", tipo: "opiniao" as api.TipoPublicacao, categoria: "geral", tags: "" });
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => { setMembros(readLS(LS_GRUPOS)); setSeguindo(readLS(LS_SEGUINDO)); }, []);
  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const r = await api.obterPublicacoes({});
        const list = r?.length ? r : MOCK_PUBS;
        if (alive) setPubs(list);
      } catch {
        if (alive) setPubs(MOCK_PUBS);
      } finally { if (alive) setLoading(false); }
    })();
    return () => { alive = false; };
  }, []);

  const toggleGrupo = (slug: string) => {
    const next = membros.includes(slug) ? membros.filter((s) => s !== slug) : [...membros, slug];
    setMembros(next); writeLS(LS_GRUPOS, next);
    setMsg(membros.includes(slug) ? `Saiu de ${slug}` : `Entrou em ${slug} — feed filtrado`);
    if (!membros.includes(slug)) { setGrupoFiltro(slug); setTab("feed"); setCatFiltro(slug); }
  };
  const verGrupo = (slug: string) => { setGrupoFiltro(slug); setCatFiltro(slug); setTab("feed"); };

  const toggleSeguir = async (autorId: number, autorNome: string) => {
    const key = String(autorId);
    const isSeg = seguindo.includes(key);
    if (!token) { const n = isSeg ? seguindo.filter((k) => k !== key) : [...seguindo, key]; setSeguindo(n); writeLS(LS_SEGUINDO, n); setMsg(isSeg ? `Deixou de seguir ${autorNome}` : `Seguindo ${autorNome} (local)`); return; }
    try { if (isSeg) await api.deixarDeSeguirAutor(token, autorId); else await api.seguirAutor(token, autorId); const n = isSeg ? seguindo.filter((k) => k !== key) : [...seguindo, key]; setSeguindo(n); writeLS(LS_SEGUINDO, n); setMsg(isSeg ? `Deixou de seguir ${autorNome}` : `Seguindo ${autorNome}`); } catch (e: unknown) { const m = e instanceof Error ? e.message : "Falha ao seguir"; setErr(m); }
  };

  const filtradas = useMemo(() => {
    return pubs.filter((p) => {
      if (tipoFiltro !== "todos" && p.tipo !== tipoFiltro) return false;
      const cat = grupoFiltro || (catFiltro !== "todas" ? catFiltro : null);
      if (cat && p.categoria !== cat) return false;
      if (destaqueOnly && !p.destaque) return false;
      if (busca && !(`${p.titulo} ${p.autor_nome} ${p.tags.join(" ")}`.toLowerCase().includes(busca.toLowerCase()))) return false;
      return true;
    });
  }, [pubs, tipoFiltro, catFiltro, destaqueOnly, busca, grupoFiltro]);

  const handleCriar = async () => {
    setErr(null);
    if (!token) { setErr("Entre para publicar."); return; }
    if (criar.titulo.trim().length < 3 || criar.conteudo.trim().length < 10) { setErr("Título ≥3 e conteúdo ≥10 caracteres."); return; }
    try {
      const tags = criar.tags.split(",").map((t) => t.trim()).filter(Boolean);
      const rasc = await api.criarRascunhoPublicacao(token, { titulo: criar.titulo.trim(), conteudo: criar.conteudo.trim(), tipo: criar.tipo, categoria: criar.categoria || undefined, tags: tags.length ? tags : undefined });
      await api.enviarPublicacao(token, rasc.id);
      setPubs((prev) => [{ ...rasc, status: "publicado", publicado_em: new Date().toISOString() }, ...prev]);
      setOpenCriar(false); setCriar({ titulo: "", conteudo: "", tipo: "opiniao", categoria: "geral", tags: "" }); setMsg("Publicação enviada!");
    } catch (e: unknown) { setErr(e instanceof Error ? e.message : "Falha ao publicar"); }
  };
  const handleComentar = async () => {
    if (!token || !openComentar.pubId) { setErr("Entre para comentar."); return; }
    if (comentarioTxt.trim().length < 2) { setErr("Comentário muito curto."); return; }
    try { await api.comentar(token, { conteudo: comentarioTxt.trim(), publicacao: openComentar.pubId }); setOpenComentar({ open: false }); setComentarioTxt(""); setMsg("Comentário enviado!"); } catch (e: unknown) { setErr(e instanceof Error ? e.message : "Falha ao comentar"); }
  };
  const handleDenunciar = async () => {
    if (!token) { setErr("Entre para denunciar."); return; }
    if (motivo.trim().length < 5) { setErr("Informe o motivo (≥5)."); return; }
    try { await api.denunciar(token, { motivo: motivo.trim(), publicacao: openDenuncia.pubId, comentario: openDenuncia.comentarioId }); setOpenDenuncia({ open: false }); setMotivo(""); setMsg("Denúncia enviada. Obrigado."); } catch (e: unknown) { setErr(e instanceof Error ? e.message : "Falha ao denunciar"); }
  };

  return (
    <div className="mx-auto max-w-6xl space-y-4 py-6 px-3 sm:px-0">
      <div className="hud-line" aria-hidden />
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-[var(--cor-texto)]">Comunidade</h1>
          <p className="text-sm text-[var(--cor-texto-suave)]">Grupos por editoria — siga, entre e acompanhe notícias com contexto.</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" className="min-h-[44px] border-[var(--cor-borda)]" onClick={() => setOpenCriar(true)}><Plus className="mr-1.5 h-4 w-4" />Publicar</Button>
          <Button asChild className="min-h-[44px] bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]"><Link href="/comunidade/nova">Nova página</Link></Button>
        </div>
      </div>

      {(msg || err) && (
        <div className={cn("rounded-md border px-3 py-2 text-sm", err ? "border-[var(--cor-erro)] bg-[var(--cor-erro-suave)] text-[var(--cor-erro)]" : "border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] text-[var(--cor-texto)]")} role="alert">
          {err || msg} <button onClick={() => { setMsg(null); setErr(null); }} className="ml-2 underline text-xs">fechar</button>
        </div>
      )}

      {grupoFiltro && (
        <div className="flex items-center gap-2 rounded-full border border-[var(--cor-borda)] bg-[var(--cor-primaria-suave)] px-3 py-1.5 text-sm text-[var(--cor-texto)] w-fit">
          <Filter className="h-3.5 w-3.5" /> Filtrando: <strong>{grupoFiltro}</strong>
          <button onClick={() => { setGrupoFiltro(null); setCatFiltro("todas"); }} className="ml-1 rounded-full bg-[var(--cor-fundo-card)] px-2 py-0.5 text-xs border border-[var(--cor-borda)]">Limpar</button>
        </div>
      )}

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList className="w-full justify-start overflow-x-auto">
          <TabsTrigger value="feed" className="gap-1.5"><Newspaper className="h-4 w-4" />Feed</TabsTrigger>
          <TabsTrigger value="grupos" className="gap-1.5"><Users className="h-4 w-4" />Grupos</TabsTrigger>
          <TabsTrigger value="minhas" className="gap-1.5"><Star className="h-4 w-4" />Minhas comunidades</TabsTrigger>
        </TabsList>

        <TabsContent value="feed" className="space-y-3">
          <Card className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
            <CardContent className="flex flex-wrap gap-2 p-3">
              <div className="flex items-center gap-1.5">
                <Select value={tipoFiltro} onValueChange={setTipoFiltro}>
                  <SelectTrigger className="h-9 w-[150px] bg-[var(--cor-fundo-card)]"><SelectValue placeholder="Tipo" /></SelectTrigger>
                  <SelectContent><SelectItem value="todos">Todos tipos</SelectItem><SelectItem value="opiniao">Opinião</SelectItem><SelectItem value="analise">Análise</SelectItem></SelectContent>
                </Select>
                <Select value={catFiltro} onValueChange={(v) => { setCatFiltro(v); setGrupoFiltro(null); }}>
                  <SelectTrigger className="h-9 w-[150px] bg-[var(--cor-fundo-card)]"><SelectValue placeholder="Categoria" /></SelectTrigger>
                  <SelectContent><SelectItem value="todas">Todas</SelectItem>{GRUPOS.map((g) => <SelectItem key={g.slug} value={g.slug}>{g.nome}</SelectItem>)}</SelectContent>
                </Select>
                <Button variant={destaqueOnly ? "default" : "outline"} size="sm" className={cn("h-9", destaqueOnly ? "bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]" : "border-[var(--cor-borda)]")} onClick={() => setDestaqueOnly((v) => !v)}><Star className="mr-1 h-3.5 w-3.5" />Destaque</Button>
              </div>
              <div className="relative flex-1 min-w-[180px]">
                <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-[var(--cor-texto-suave)]" />
                <Input placeholder="Buscar por autor, título ou tag" value={busca} onChange={(e) => setBusca(e.target.value)} className="pl-8 h-9 bg-[var(--cor-fundo-card)]" />
              </div>
            </CardContent>
          </Card>

          {loading ? <Card className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]"><CardContent className="p-6 text-sm text-[var(--cor-texto-suave)]">Carregando...</CardContent></Card>
            : filtradas.length === 0 ? <Card className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]"><CardContent className="p-6 text-sm text-[var(--cor-texto-suave)]">Nenhuma publicação para este filtro.</CardContent></Card>
              : (
                <div className="grid gap-3">
                  {filtradas.map((p, idx) => (
                    <div key={p.id}>
                      <Link href={`/comunidade/${p.id}`} className="flex gap-3 rounded-[var(--raio-lg)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] p-3 hover:bg-[var(--cor-primaria-suave)] transition-colors">
                        <div className="hidden sm:flex h-[84px] w-[112px] shrink-0 items-center justify-center rounded-[var(--raio-md)] bg-[var(--cor-fundo-elevado)] border border-[var(--cor-borda)]">
                          <Newspaper className="h-6 w-6 text-[var(--cor-texto-suave)]" />
                        </div>
                        <div className="min-w-0 flex-1">
                          <div className="flex flex-wrap items-center gap-1.5">
                            <Badge variant="outline" className="border-[var(--cor-borda)] text-xs">{p.tipo}</Badge>
                            <Badge className="bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)] text-xs">{p.categoria}</Badge>
                            {p.destaque && <Badge variant="secondary" className="gap-1 text-xs"><Star className="h-3 w-3" />Destaque</Badge>}
                            <span className="text-xs text-[var(--cor-texto-suave)]">por {p.autor_nome} · {new Date(p.criado_em).toLocaleDateString("pt-BR")}</span>
                          </div>
                          <p className="mt-1 line-clamp-2 text-[15px] font-semibold leading-tight text-[var(--cor-texto)]">{p.titulo}</p>
                          <p className="line-clamp-2 text-sm text-[var(--cor-texto-suave)]">{p.conteudo.slice(0, 160)}</p>
                          {!!p.tags.length && <div className="mt-1 flex flex-wrap gap-1">{p.tags.slice(0, 3).map((t) => <span key={t} className="rounded-full border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] px-2 py-0.5 text-[11px] text-[var(--cor-texto-suave)]">#{t}</span>)}</div>}
                        </div>
                      </Link>
                      <div className="mt-1 flex flex-wrap gap-1.5 px-1">
                        <Button size="sm" variant="ghost" className="h-7 text-xs gap-1" onClick={() => toggleSeguir(p.autor, p.autor_nome)}>{seguindo.includes(String(p.autor)) ? <><UserMinus className="h-3.5 w-3.5" />Seguindo</> : <><UserPlus className="h-3.5 w-3.5" />Seguir autor</>}</Button>
                        <Button size="sm" variant="ghost" className="h-7 text-xs gap-1" onClick={() => setOpenComentar({ open: true, pubId: p.id })}><MessageSquare className="h-3.5 w-3.5" />Comentar</Button>
                        <Button size="sm" variant="ghost" className="h-7 text-xs gap-1" onClick={() => setOpenDenuncia({ open: true, pubId: p.id })}><Flag className="h-3.5 w-3.5" />Denunciar</Button>
                      </div>
                      {(idx + 1) % 4 === 0 && <AdsSlot id={`comunidade-feed-${idx}`} formato="in-feed" className="my-3" />}
                    </div>
                  ))}
                </div>
              )}
        </TabsContent>

        <TabsContent value="grupos">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {GRUPOS.map((g) => {
              const countPubs = pubs.filter((p) => p.categoria === g.slug).length;
              const membrosMock = 80 + g.slug.length * 37 + countPubs * 7;
              const isMembro = membros.includes(g.slug);
              return (
                <Card key={g.slug} className={cn("border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] flex flex-col", isMembro && "ring-1 ring-[var(--cor-primaria)]")}>
                  <CardHeader className="pb-2">
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex h-9 w-9 items-center justify-center rounded-[var(--raio-md)] bg-[var(--cor-primaria-suave)] border border-[var(--cor-borda)]"><Users className="h-5 w-5 text-[var(--cor-primaria)]" /></div>
                      {isMembro && <Badge className="bg-[var(--cor-sucesso)] text-white text-[11px]">Membro</Badge>}
                    </div>
                    <CardTitle className="text-base text-[var(--cor-texto)]">{g.nome}</CardTitle>
                    <CardDescription className="text-xs text-[var(--cor-texto-suave)] line-clamp-2">{g.desc}</CardDescription>
                  </CardHeader>
                  <CardContent className="mt-auto space-y-3">
                    <div className="flex gap-3 text-xs text-[var(--cor-texto-suave)]">
                      <span className="flex items-center gap-1"><Users className="h-3.5 w-3.5" />{membrosMock} membros</span>
                      <span className="flex items-center gap-1"><Newspaper className="h-3.5 w-3.5" />{countPubs} pubs</span>
                    </div>
                    <div className="flex gap-2">
                      <Button size="sm" className={cn("flex-1 min-h-[36px] gap-1", isMembro ? "bg-[var(--cor-fundo-elevado)] text-[var(--cor-texto)] border border-[var(--cor-borda)] hover:bg-[var(--cor-borda)]" : "bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]")} onClick={() => toggleGrupo(g.slug)}>
                        {isMembro ? <><UserMinus className="h-4 w-4" />Sair</> : <><UserPlus className="h-4 w-4" />Entrar</>}
                      </Button>
                      <Button size="sm" variant="outline" className="min-h-[36px] border-[var(--cor-borda)] gap-1" onClick={() => verGrupo(g.slug)}><Eye className="h-4 w-4" />Ver</Button>
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </TabsContent>

        <TabsContent value="minhas" className="space-y-3">
          {membros.length === 0 ? (
            <Card className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]"><CardContent className="p-6 text-center text-sm text-[var(--cor-texto-suave)]">Você ainda não entrou em nenhuma comunidade. Vá em <strong>Grupos</strong> e clique em Entrar.<Button variant="outline" className="mt-3 border-[var(--cor-borda)]" onClick={() => setTab("grupos")}><Users className="mr-1.5 h-4 w-4" />Explorar grupos</Button></CardContent></Card>
          ) : (
            <div className="grid gap-3 sm:grid-cols-2">
              {GRUPOS.filter((g) => membros.includes(g.slug)).map((g) => {
                const pubsGrupo = pubs.filter((p) => p.categoria === g.slug).slice(0, 2);
                return (
                  <Card key={g.slug} className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
                    <CardHeader className="pb-2">
                      <CardTitle className="text-base flex items-center gap-2 text-[var(--cor-texto)]"><Users className="h-4 w-4 text-[var(--cor-primaria)]" />{g.nome}</CardTitle>
                      <CardDescription className="text-xs">{g.desc}</CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-2">
                      {pubsGrupo.length ? pubsGrupo.map((p) => <Link key={p.id} href={`/comunidade/${p.id}`} className="block rounded-md border border-[var(--cor-borda)] p-2 hover:bg-[var(--cor-primaria-suave)]"><p className="text-sm font-medium text-[var(--cor-texto)] line-clamp-1">{p.titulo}</p><p className="text-xs text-[var(--cor-texto-suave)]">{p.tipo} · {p.autor_nome}</p></Link>) : <p className="text-xs text-[var(--cor-texto-suave)]">Sem publicações ainda.</p>}
                      <div className="flex gap-2 pt-1">
                        <Button size="sm" variant="outline" className="flex-1 border-[var(--cor-borda)]" onClick={() => verGrupo(g.slug)}><Eye className="mr-1 h-3.5 w-3.5" />Ver feed</Button>
                        <Button size="sm" variant="ghost" onClick={() => toggleGrupo(g.slug)}>Sair</Button>
                      </div>
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          )}
          {!token && <Card className="border-dashed border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)]"><CardContent className="p-4 flex items-center justify-between gap-3"><p className="text-sm text-[var(--cor-texto-suave)]">Entre para seguir autores de verdade (via API).</p><Button size="sm" variant="outline" className="border-[var(--cor-borda)]" onClick={() => window.location.href = "/login"}><LogIn className="mr-1 h-4 w-4" />Entrar</Button></CardContent></Card>}
        </TabsContent>
      </Tabs>

      <Dialog open={openCriar} onOpenChange={setOpenCriar}>
        <DialogContent className="bg-[var(--cor-fundo-card)] border-[var(--cor-borda)] max-h-[90vh] overflow-y-auto">
          <DialogHeader><DialogTitle>Nova publicação rápida</DialogTitle><DialogDescription>Cria rascunho e envia em seguida. Use a página completa para mais campos.</DialogDescription></DialogHeader>
          <div className="space-y-3">
            <div className="space-y-1.5"><Label htmlFor="qc-titulo">Título</Label><Input id="qc-titulo" value={criar.titulo} onChange={(e) => setCriar((s) => ({ ...s, titulo: e.target.value }))} placeholder="Título..." /></div>
            <div className="grid grid-cols-2 gap-2">
              <div className="space-y-1.5"><Label>Tipo</Label><Select value={criar.tipo} onValueChange={(v) => setCriar((s) => ({ ...s, tipo: v as api.TipoPublicacao }))}><SelectTrigger className="bg-[var(--cor-fundo-card)]"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="opiniao">Opinião</SelectItem><SelectItem value="analise">Análise</SelectItem></SelectContent></Select></div>
              <div className="space-y-1.5"><Label>Categoria (grupo)</Label><Select value={criar.categoria} onValueChange={(v) => setCriar((s) => ({ ...s, categoria: v }))}><SelectTrigger className="bg-[var(--cor-fundo-card)]"><SelectValue /></SelectTrigger><SelectContent>{GRUPOS.map((g) => <SelectItem key={g.slug} value={g.slug}>{g.nome}</SelectItem>)}</SelectContent></Select></div>
            </div>
            <div className="space-y-1.5"><Label htmlFor="qc-tags">Tags (vírgula)</Label><Input id="qc-tags" value={criar.tags} onChange={(e) => setCriar((s) => ({ ...s, tags: e.target.value }))} placeholder="ex: política, cidades" /></div>
            <div className="space-y-1.5"><Label htmlFor="qc-conteudo">Conteúdo</Label><Textarea id="qc-conteudo" rows={5} value={criar.conteudo} onChange={(e) => setCriar((s) => ({ ...s, conteudo: e.target.value }))} placeholder="Escreva..." /></div>
          </div>
          <DialogFooter><Button variant="outline" onClick={() => setOpenCriar(false)} className="border-[var(--cor-borda)]">Cancelar</Button><Button onClick={handleCriar} className="bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)] gap-1"><Send className="h-4 w-4" />Publicar</Button></DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={openComentar.open} onOpenChange={(o) => setOpenComentar((s) => ({ ...s, open: o }))}>
        <DialogContent className="bg-[var(--cor-fundo-card)] border-[var(--cor-borda)]">
          <DialogHeader><DialogTitle>Comentar</DialogTitle><DialogDescription>Seu comentário na publicação #{openComentar.pubId}</DialogDescription></DialogHeader>
          <Textarea rows={4} value={comentarioTxt} onChange={(e) => setComentarioTxt(e.target.value)} placeholder="Escreva seu comentário..." />
          <DialogFooter><Button variant="outline" onClick={() => setOpenComentar({ open: false })} className="border-[var(--cor-borda)]">Cancelar</Button><Button onClick={handleComentar} className="bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]"><Send className="mr-1 h-4 w-4" />Enviar</Button></DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={openDenuncia.open} onOpenChange={(o) => setOpenDenuncia((s) => ({ ...s, open: o }))}>
        <DialogContent className="bg-[var(--cor-fundo-card)] border-[var(--cor-borda)]">
          <DialogHeader><DialogTitle className="flex items-center gap-2"><Shield className="h-4 w-4" />Denunciar</DialogTitle><DialogDescription>Conteúdo #{openDenuncia.pubId ?? openDenuncia.comentarioId}</DialogDescription></DialogHeader>
          <div className="space-y-1.5"><Label htmlFor="motivo">Motivo</Label><Textarea id="motivo" rows={3} value={motivo} onChange={(e) => setMotivo(e.target.value)} placeholder="Descreva a violação..." /></div>
          <DialogFooter><Button variant="outline" onClick={() => setOpenDenuncia({ open: false })} className="border-[var(--cor-borda)]">Cancelar</Button><Button onClick={handleDenunciar} variant="destructive"><Flag className="mr-1 h-4 w-4" />Enviar denúncia</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
