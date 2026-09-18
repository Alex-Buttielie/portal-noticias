"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { Menu, X, Search, LogOut, Compass, ChevronDown, LayoutGrid } from "lucide-react";
import { cn } from "@/lib/utils";
import { NAV_ITENS, NAV_ITEM_CONTA, NAV_ITEM_LOGIN, NAV_ITEM_ADMIN } from "@/lib/nav-itens";
import { CATEGORIAS, SLUGS_CATEGORIAS, hrefSubcategoria } from "@/lib/categorias";
import { useAuth } from "@/lib/auth-context";
import { ThemeToggle } from "./ThemeToggle";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
const CATS=SLUGS_CATEGORIAS;
const SUGESTOES=["eleições","juros","clima","tecnologia","saúde"];
export function Header() {
  const pathname = usePathname();
  const router = useRouter();
  const { usuario, fazerLogout } = useAuth();
  const isAdmin = usuario?.papel === "admin";
  const [aberto, setAberto] = useState(false);
  const [busca, setBusca] = useState("");
  const [sugestOpen,setSugestOpen]=useState(false);
  const [foco,setFoco]=useState(false);
  const [menuEd,setMenuEd]=useState(false);
  const [catMobile,setCatMobile]=useState<string | null>(null);
  const menuEdRef=useRef<HTMLDivElement>(null);
  useEffect(()=>{
    if(!menuEd) return;
    function onKey(e: KeyboardEvent){ if(e.key==="Escape") setMenuEd(false); }
    function onClick(e: MouseEvent){ if(menuEdRef.current && !menuEdRef.current.contains(e.target as Node)) setMenuEd(false); }
    document.addEventListener("keydown",onKey);
    document.addEventListener("mousedown",onClick);
    return ()=>{ document.removeEventListener("keydown",onKey); document.removeEventListener("mousedown",onClick); };
  },[menuEd]);
  useEffect(()=>{ setMenuEd(false); setCatMobile(null); },[pathname]);
  const edAtivo = pathname==="/editorias" || pathname.startsWith("/categoria/") || pathname.startsWith("/buscar");
  function onBusca(e: React.FormEvent) {
    e.preventDefault();
    const q = busca.trim();
    if(!q){ setSugestOpen(true); return; }
    router.push(`/buscar?q=${encodeURIComponent(q)}`);
    setAberto(false);
    setFoco(false);
  }
  const qLower=busca.trim().toLowerCase();
  const catsFiltradas=CATS.filter(c=>!qLower||c.includes(qLower));
  const sugFiltradas=SUGESTOES.filter(s=>!qLower||s.includes(qLower));
  return (
    <>
    <header className="sticky top-0 z-[var(--z-cabecalho)] glass border-b border-[var(--cor-borda)]">
      <div className="hud-line" />
      <div className="mx-auto flex h-14 max-w-[1280px] items-center gap-3 px-4 md:h-16 md:px-6">
        <Link href="/" className="flex items-center gap-2 shrink-0">
          <span className="flex h-8 w-8 items-center justify-center rounded-md text-sm font-bold text-[var(--cor-texto-invertido)]" style={{ background: "var(--gradiente-marca)", boxShadow: "0 0 12px var(--cor-neon-ciano)" }} aria-hidden>
            ◈
          </span>
          <span className="hidden text-sm font-bold tracking-tight text-[var(--cor-texto)] sm:block">Portal</span>
        </Link>
        <nav className="hidden items-center gap-1 md:flex" aria-label="Principal">
          {[...NAV_ITENS, ...(isAdmin ? [NAV_ITEM_ADMIN] : [])].map((item) => {
            const ativo = pathname === item.href || (item.href === "/admin" && pathname.startsWith("/admin"));
            const isCentral=item.label==="Central";
            return (
              <Link key={item.href} href={item.href} className={cn("rounded-full px-3 py-2 text-sm font-medium transition-colors", ativo ? "bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]" : isCentral ? "border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] text-[var(--cor-primaria)] hover:bg-[var(--cor-primaria-suave)]" : "text-[var(--cor-texto-suave)] hover:bg-[var(--cor-borda)] hover:text-[var(--cor-texto)]")}>
                {item.label}
              </Link>
            );
          })}
          <div ref={menuEdRef} className="relative">
            <button type="button" onClick={()=>setMenuEd(v=>!v)} aria-expanded={menuEd} aria-haspopup="true" className={cn("inline-flex items-center gap-1 rounded-full px-3 py-2 text-sm font-medium transition-colors", menuEd||edAtivo ? "bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]" : "text-[var(--cor-texto-suave)] hover:bg-[var(--cor-borda)] hover:text-[var(--cor-texto)]")}>
              <LayoutGrid className="h-4 w-4" /> Editorias <ChevronDown className={cn("h-3.5 w-3.5 transition-transform", menuEd && "rotate-180")} />
            </button>
            {menuEd && (
              <div className="absolute left-1/2 top-11 z-50 w-[min(92vw,640px)] -translate-x-1/2 rounded-[var(--raio-lg)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] p-4 shadow-[var(--sombra-2)]">
                <div className="mb-3 flex items-center justify-between">
                  <p className="text-xs font-semibold tracking-widest text-[var(--cor-texto-suave)]">NAVEGUE POR ASSUNTO</p>
                  <Link href="/editorias" onClick={()=>setMenuEd(false)} className="text-xs font-medium text-[var(--cor-primaria)] hover:underline">Ver todas →</Link>
                </div>
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                  {CATEGORIAS.map((c)=>(
                    <div key={c.slug} className="min-w-0">
                      <Link href={`/categoria/${encodeURIComponent(c.slug)}`} onClick={()=>setMenuEd(false)} className="text-sm font-bold capitalize text-[var(--cor-texto)] hover:text-[var(--cor-primaria)] hover:underline">{c.nome}</Link>
                      <ul className="mt-1.5 space-y-1">
                        {c.subcategorias.slice(0,4).map((s)=>(
                          <li key={s.termo}><Link href={hrefSubcategoria(s)} onClick={()=>setMenuEd(false)} className="text-[13px] text-[var(--cor-texto-suave)] hover:text-[var(--cor-primaria)] hover:underline">{s.nome}</Link></li>
                        ))}
                      </ul>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </nav>
        <form onSubmit={onBusca} className="ml-auto hidden items-center gap-2 md:flex" role="search">
          <div className="relative">
            <Search className="pointer-events-none absolute left-2.5 top-2.5 h-4 w-4 text-[var(--cor-texto-suave)]" />
            <input value={busca} onChange={(e) => setBusca(e.target.value)} onFocus={()=>setFoco(true)} onBlur={()=>setTimeout(()=>setFoco(false),150)} placeholder="Buscar…" aria-label="Buscar notícias" className="h-9 w-44 rounded-full border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] pl-8 pr-3 text-sm text-[var(--cor-texto)] placeholder:text-[var(--cor-texto-suave)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] lg:w-64" />
            {foco && (
              <div className="absolute left-0 top-10 z-50 w-72 rounded-[var(--raio-lg)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] p-3 shadow-[var(--sombra-2)]">
                <p className="mb-2 text-xs font-medium text-[var(--cor-texto-suave)]">Sugestões</p>
                <div className="flex flex-wrap gap-1.5">
                  {sugFiltradas.map(s=>(
                    <button key={s} type="button" onMouseDown={()=>{setBusca(s);router.push(`/buscar?q=${encodeURIComponent(s)}`);}} className="rounded-full border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] px-2.5 py-1 text-xs capitalize text-[var(--cor-texto)] hover:bg-[var(--cor-borda)]">{s}</button>
                  ))}
                </div>
                <p className="mb-2 mt-3 text-xs font-medium text-[var(--cor-texto-suave)]">Editorias</p>
                <div className="flex flex-wrap gap-1.5">
                  {catsFiltradas.map(c=>(
                    <Link key={c} href={`/categoria/${encodeURIComponent(c)}`} onMouseDown={()=>setFoco(false)} className="rounded-full border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] px-2.5 py-1 text-xs capitalize text-[var(--cor-texto)] hover:bg-[var(--cor-borda)]">{c}</Link>
                  ))}
                </div>
              </div>
            )}
          </div>
          <Button type="submit" className="h-9 rounded-full bg-[var(--cor-primaria)] px-4 text-sm font-medium text-[var(--cor-texto-invertido)] hover:bg-[var(--cor-primaria-hover)]">Buscar</Button>
        </form>
        <div className="hidden items-center gap-2 md:flex">
          <ThemeToggle />
          {usuario ? (
            <>
              <Link href={NAV_ITEM_CONTA.href} className="inline-flex h-9 items-center rounded-full border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] px-3 text-sm font-medium text-[var(--cor-texto)] hover:bg-[var(--cor-borda)]">{usuario.nome?.split(" ")[0] ?? "Conta"}</Link>
              <button type="button" onClick={() => void fazerLogout()} aria-label="Sair" className="inline-flex h-9 w-9 items-center justify-center rounded-full border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] text-[var(--cor-texto-suave)] hover:text-[var(--cor-texto)]"><LogOut className="h-4 w-4" /></button>
            </>
          ) : (
            <Link href={NAV_ITEM_LOGIN.href} className="inline-flex h-9 items-center rounded-full bg-[var(--cor-primaria)] px-4 text-sm font-medium text-[var(--cor-texto-invertido)] hover:bg-[var(--cor-primaria-hover)]">Entrar</Link>
          )}
        </div>
        <button type="button" aria-label={aberto ? "Fechar menu" : "Abrir menu"} aria-expanded={aberto} onClick={() => setAberto((v) => !v)} className="ml-auto inline-flex h-9 w-9 items-center justify-center rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] md:hidden">
          {aberto ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
        </button>
      </div>
      {aberto && (
        <div className="max-h-[calc(100dvh-3.5rem)] overflow-y-auto border-t border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] px-4 py-4 md:hidden">
          <form onSubmit={onBusca} className="mb-3 flex gap-2" role="search">
            <input value={busca} onChange={(e) => setBusca(e.target.value)} placeholder="Buscar…" aria-label="Buscar notícias" className="h-10 flex-1 rounded-full border border-[var(--cor-borda)] bg-[var(--cor-fundo)] px-3 text-sm" />
            <button type="submit" className="inline-flex h-10 items-center rounded-full bg-[var(--cor-primaria)] px-4 text-sm font-medium text-[var(--cor-texto-invertido)]"><Search className="h-4 w-4" /></button>
          </form>
          <nav className="grid gap-1" aria-label="Principal mobile">
            {[...NAV_ITENS, ...(isAdmin ? [NAV_ITEM_ADMIN] : [])].map((item) => {
              const ativo = pathname === item.href || (item.href === "/admin" && pathname.startsWith("/admin"));
              const isCentral=item.label==="Central";
              return (
                <Link key={item.href} href={item.href} onClick={() => setAberto(false)} className={cn("rounded-full px-3 py-2.5 text-sm font-medium", ativo ? "bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]" : isCentral ? "border border-[var(--cor-borda)] text-[var(--cor-primaria)]" : "text-[var(--cor-texto)] hover:bg-[var(--cor-borda)]")}>
                  {item.label}
                </Link>
              );
            })}
            <div className="mt-2 rounded-[var(--raio-md)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)]">
              <button type="button" onClick={()=>setCatMobile(v=>v==="__eds"?"__x": "__eds")} aria-expanded={catMobile==="__eds"} className="flex w-full items-center justify-between px-3 py-2.5 text-sm font-bold text-[var(--cor-texto)]">
                <span className="inline-flex items-center gap-2"><LayoutGrid className="h-4 w-4 text-[var(--cor-primaria)]" /> Editorias</span>
                <ChevronDown className={cn("h-4 w-4 transition-transform", catMobile==="__eds" && "rotate-180")} />
              </button>
              {catMobile==="__eds" && (
                <div className="space-y-1 border-t border-[var(--cor-borda)] px-2 py-2">
                  {CATEGORIAS.map((c)=>(
                    <div key={c.slug} className="rounded-md">
                      <div className="flex items-center gap-1">
                        <Link href={`/categoria/${encodeURIComponent(c.slug)}`} onClick={() => setAberto(false)} className="flex-1 rounded-md px-2 py-2 text-sm font-semibold capitalize text-[var(--cor-texto)] hover:bg-[var(--cor-borda)]">{c.nome}</Link>
                        <button type="button" onClick={()=>setCatMobile(v=>v===c.slug? "__eds": c.slug)} aria-expanded={catMobile===c.slug} aria-label={`Subcategorias de ${c.nome}`} className="inline-flex h-8 w-8 items-center justify-center rounded-md text-[var(--cor-texto-suave)] hover:bg-[var(--cor-borda)]">
                          <ChevronDown className={cn("h-4 w-4 transition-transform", catMobile===c.slug && "rotate-180")} />
                        </button>
                      </div>
                      {catMobile===c.slug && (
                        <div className="mb-1 ml-2 flex flex-wrap gap-1.5 border-l-2 border-[var(--cor-borda)] py-1 pl-3">
                          {c.subcategorias.map((s)=>(
                            <Link key={s.termo} href={hrefSubcategoria(s)} onClick={() => setAberto(false)} className="rounded-full border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] px-2.5 py-1 text-xs text-[var(--cor-texto)]">{s.nome}</Link>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                  <Link href="/editorias" onClick={() => setAberto(false)} className="block rounded-md px-2 py-2 text-xs font-medium text-[var(--cor-primaria)] hover:underline">Ver todas as editorias →</Link>
                </div>
              )}
            </div>
            <div className="mt-2 flex items-center justify-between border-t border-[var(--cor-borda)] pt-3">
              <ThemeToggle />
              {usuario ? (
                <button type="button" onClick={() => void fazerLogout()} className="text-sm text-[var(--cor-texto-suave)]">Sair</button>
              ) : (
                <Link href={NAV_ITEM_LOGIN.href} onClick={() => setAberto(false)} className="rounded-full bg-[var(--cor-primaria)] px-4 py-2 text-sm font-medium text-[var(--cor-texto-invertido)]">Entrar</Link>
              )}
            </div>
          </nav>
        </div>
      )}
    </header>
    <Dialog open={sugestOpen} onOpenChange={setSugestOpen}>
      <DialogContent className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2"><Compass className="h-5 w-5 text-[var(--cor-primaria)]" /> Que tal explorar por categoria?</DialogTitle>
          <DialogDescription>Digite um termo ou escolha uma editoria abaixo para começar.</DialogDescription>
        </DialogHeader>
        <div className="flex flex-wrap gap-2">
          {CATS.map(c=>(
            <Link key={c} href={`/categoria/${encodeURIComponent(c)}`} onClick={()=>setSugestOpen(false)} className="inline-flex min-h-[36px] items-center rounded-full border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] px-3 text-sm capitalize text-[var(--cor-texto)] hover:bg-[var(--cor-borda)]">{c}</Link>
          ))}
        </div>
        <div className="flex gap-2">
          <Button asChild className="flex-1 bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)] min-h-[44px]"><Link href="/" onClick={()=>setSugestOpen(false)}>Ver últimas notícias</Link></Button>
          <Button variant="outline" onClick={()=>setSugestOpen(false)} className="min-h-[44px]">Fechar</Button>
        </div>
      </DialogContent>
    </Dialog>
    </>
  );
}
