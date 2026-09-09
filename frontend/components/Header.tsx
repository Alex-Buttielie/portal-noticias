"use client";

import { Suspense, useEffect, useId, useRef, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import ThemeToggle from "@/components/ThemeToggle";
import CommandPalette from "@/components/CommandPalette";

const EDITORIAS = [
  { label: "Política", slug: "política" },
  { label: "Economia", slug: "economia" },
  { label: "Esportes", slug: "esportes" },
  { label: "Tecnologia", slug: "tecnologia" },
  { label: "Saúde", slug: "saúde" },
  { label: "Cultura", slug: "cultura" },
  { label: "Mundo", slug: "mundo" },
  { label: "Ciência", slug: "ciência" },
];

const NAV_SECUNDARIA = [
  { href: "/", rotulo: "Últimas" },
  { href: "/comunidade", rotulo: "Comunidade" },
  { href: "/radar", rotulo: "Radar" },
  { href: "/planos", rotulo: "Premium", destaque: true },
];

export default function Header() {
  const { usuario, carregando, fazerLogout } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const [menuAberto, setMenuAberto] = useState(false);
  const [busca, setBusca] = useState("");
  const [buscaAberta, setBuscaAberta] = useState(false);
  const [paletteAberto, setPaletteAberto] = useState(false);
  const navId = useId();
  const buscaId = useId();
  const campoBuscaRef = useRef<HTMLInputElement>(null);

  // Ao abrir a busca colapsável, mover o foco para o input.
  useEffect(() => {
    if (buscaAberta) campoBuscaRef.current?.focus();
  }, [buscaAberta]);

  // Fechar o nav mobile com Escape.
  useEffect(() => {
    if (!menuAberto) return;
    function onEscape(e: KeyboardEvent) {
      if (e.key === "Escape") setMenuAberto(false);
    }
    window.addEventListener("keydown", onEscape);
    return () => window.removeEventListener("keydown", onEscape);
  }, [menuAberto]);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteAberto((v) => !v);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // Fecha o menu mobile ao trocar de rota
  useEffect(() => {
    setMenuAberto(false);
  }, [pathname]);

  function onSubmitBusca(e: React.FormEvent) {
    e.preventDefault();
    const q = busca.trim();
    router.push(q ? `/?busca=${encodeURIComponent(q)}` : "/");
    setMenuAberto(false);
    setBuscaAberta(false);
  }

  const inicial = (usuario?.nome || usuario?.email || "?").trim().charAt(0).toUpperCase();

  return (
    <header className="cabecalho">
      <div className="container cabecalho-topo">
        <button
          type="button"
          className="botao-menu-mobile"
          aria-expanded={menuAberto}
          aria-controls={navId}
          aria-label={menuAberto ? "Fechar menu" : "Abrir menu"}
          onClick={() => setMenuAberto((v) => !v)}
        >
          <span aria-hidden="true">{menuAberto ? "✕" : "☰"}</span>
        </button>

        <Link href="/" className="cabecalho-logo" aria-label="Portal de Notícias — início">
          <span className="cabecalho-logo-mark" aria-hidden="true">PN</span>
          <span>
            Portal<em>·</em>
          </span>
        </Link>

        {/* Busca colapsável: ícone sempre visível; campo expande sob demanda */}
        <div className={`cabecalho-busca cabecalho-busca--colapsada${buscaAberta ? " cabecalho-busca--aberta" : ""}`}>
          <button
            type="button"
            className="cabecalho-busca-alternar"
            aria-expanded={buscaAberta}
            aria-controls={buscaId}
            aria-label={buscaAberta ? "Fechar busca" : "Abrir busca"}
            onClick={() => setBuscaAberta((v) => !v)}
          >
            <span aria-hidden="true">⌕</span>
          </button>
          <form
            id={buscaId}
            className="cabecalho-busca-form"
            onSubmit={onSubmitBusca}
            role="search"
            aria-label="Buscar notícias"
          >
            <label className="sr-only" htmlFor={`${buscaId}-campo`}>
              Buscar notícias
            </label>
            <input
              id={`${buscaId}-campo`}
              ref={campoBuscaRef}
              type="search"
              placeholder="Buscar notícias…"
              value={busca}
              onChange={(e) => setBusca(e.target.value)}
            />
            <button type="submit" className="cabecalho-busca-enviar" aria-label="Buscar">
              <span aria-hidden="true">→</span>
            </button>
          </form>
        </div>

        <div className="cabecalho-acoes">
          <button
            type="button"
            className="busca-atalho"
            onClick={() => setPaletteAberto(true)}
            aria-label="Busca rápida (Ctrl K)"
            title="Busca rápida (Ctrl K)"
          >
            Buscar <kbd>Ctrl K</kbd>
          </button>
          <ThemeToggle />
          {!carregando &&
            (usuario ? (
              <>
                <Link href="/minha-conta" className="topo__avatar" aria-label="Minha conta">
                  {inicial}
                </Link>
                <button type="button" className="cabecalho-botao-sair" onClick={() => fazerLogout()}>
                  Sair
                </button>
              </>
            ) : (
              <>
                <Link href="/login" className="cabecalho-link-entrar">
                  Entrar
                </Link>
                <Link href="/cadastro" className="botao botao--primaria botao--pequeno cabecalho-botao-cadastro">
                  Assine
                </Link>
              </>
            ))}
        </div>
      </div>

      <div className="cabecalho-faixa-nav">
        <div className="container">
          <Suspense fallback={null}>
            <Navegacao navId={navId} menuAberto={menuAberto} pathname={pathname} papel={usuario?.papel} />
          </Suspense>
        </div>
      </div>
      <CommandPalette aberto={paletteAberto} aoFechar={() => setPaletteAberto(false)} />
    </header>
  );
}

function Navegacao({
  navId,
  menuAberto,
  pathname,
  papel,
}: {
  navId: string;
  menuAberto: boolean;
  pathname: string | null;
  papel?: string;
}) {
  const searchParams = useSearchParams();
  const categoriaAtiva = pathname === "/" ? searchParams.get("categoria") || "" : null;

  function ehAtual(href: string): boolean {
    return href === "/" ? pathname === "/" : (pathname?.startsWith(href) ?? false);
  }

  return (
    <nav id={navId} className={`cabecalho-nav${menuAberto ? " aberto" : ""}`} aria-label="Editorias e áreas">
      <div className="cabecalho-nav-editorias" role="group" aria-label="Filtrar por editoria">
        <Link
          href="/"
          className="nav-editoria"
          aria-current={categoriaAtiva === "" ? "page" : undefined}
        >
          Todas
        </Link>
        {EDITORIAS.map((c) => (
          <Link
            key={c.slug}
            href={`/?categoria=${encodeURIComponent(c.slug)}`}
            className="nav-editoria"
            aria-current={categoriaAtiva === c.slug ? "page" : undefined}
          >
            {c.label}
          </Link>
        ))}
      </div>
      <span className="cabecalho-nav-separador" aria-hidden="true" />
      <div className="cabecalho-nav-secundaria">
        {NAV_SECUNDARIA.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            aria-current={ehAtual(item.href) ? "page" : undefined}
            className={item.destaque ? "nav-premium" : undefined}
          >
            {item.rotulo}
          </Link>
        ))}
        {papel && (
          <>
            <Link href="/jornalista/status" aria-current={ehAtual("/jornalista") ? "page" : undefined}>
              Jornalista
            </Link>
            <Link href="/empresa" aria-current={ehAtual("/empresa") ? "page" : undefined}>
              Empresa
            </Link>
            {papel === "admin" && (
              <Link href="/admin" aria-current={ehAtual("/admin") ? "page" : undefined}>
                Admin
              </Link>
            )}
          </>
        )}
      </div>
    </nav>
  );
}
