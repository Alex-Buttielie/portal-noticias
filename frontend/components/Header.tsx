"use client";

import { useEffect, useId, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import ThemeToggle from "@/components/ThemeToggle";
import CommandPalette from "@/components/CommandPalette";

const CATEGORIAS_NAV = [
  { label: "Política", slug: "política" },
  { label: "Economia", slug: "economia" },
  { label: "Esportes", slug: "esportes" },
  { label: "Tecnologia", slug: "tecnologia" },
  { label: "Saúde", slug: "saúde" },
  { label: "Cultura", slug: "cultura" },
  { label: "Mundo", slug: "mundo" },
  { label: "Ciência", slug: "ciência" },
];

export default function Header() {
  const { usuario, carregando, fazerLogout } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const [menuAberto, setMenuAberto] = useState(false);
  const [busca, setBusca] = useState("");
  const [paletteAberto, setPaletteAberto] = useState(false);
  const navId = useId();

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

  function ehAtual(href: string): boolean {
    return href === "/" ? pathname === "/" : pathname?.startsWith(href) ?? false;
  }

  function onSubmitBusca(e: React.FormEvent) {
    e.preventDefault();
    const q = busca.trim();
    router.push(q ? `/?busca=${encodeURIComponent(q)}` : "/");
    setMenuAberto(false);
  }

  return (
    <header className="cabecalho">
      <div className="cabecalho-faixa-topo">
        <div className="container cabecalho-topo">
          <Link href="/" className="cabecalho-logo">
            <span className="cabecalho-logo-mark">BRD</span> Portal de Notícias
          </Link>

          <form className="cabecalho-busca" onSubmit={onSubmitBusca} role="search">
            <input
              type="search"
              placeholder="Buscar notícias, temas…"
              aria-label="Buscar notícias"
              value={busca}
              onChange={(e) => setBusca(e.target.value)}
            />
            <button type="submit" aria-label="Buscar">
              ⌕
            </button>
          </form>

          <div className="cabecalho-acoes">
            <button type="button" className="busca-atalho" onClick={() => setPaletteAberto(true)} aria-label="Busca rápida">
              <span aria-hidden>⌕</span> Buscar <kbd>⌘K</kbd>
            </button>

            {!carregando && usuario ? (
              <>
                <Link href="/minha-conta" className="cabecalho-usuario">
                  {usuario.nome || usuario.email}
                  <span className={usuario.papel === "free" ? "selo-free" : "selo-premium"} style={{ marginLeft: 6 }}>
                    {usuario.papel === "premium" ? "Premium" : usuario.papel === "admin" ? "Admin" : "Free"}
                  </span>
                </Link>
                <button type="button" className="botao botao-secundario cabecalho-botao-sair" onClick={() => fazerLogout()}>
                  Sair
                </button>
              </>
            ) : !carregando ? (
              <>
                <Link href="/login" className="cabecalho-link-entrar">
                  Entrar
                </Link>
                <Link href="/cadastro" className="botao cabecalho-botao-cadastro">
                  Assine
                </Link>
              </>
            ) : null}

            <ThemeToggle />

            <button
              type="button"
              className="botao-menu-mobile"
              aria-expanded={menuAberto}
              aria-controls={navId}
              onClick={() => setMenuAberto((v) => !v)}
            >
              <span aria-hidden="true">{menuAberto ? "✕" : "☰"}</span> Menu
            </button>
          </div>
        </div>
      </div>

      <div className="cabecalho-faixa-nav">
        <div className="container">
          <nav id={navId} className={`cabecalho-nav${menuAberto ? " aberto" : ""}`} aria-label="Navegação principal">
            <div className="cabecalho-nav-editorias">
              <Link href="/" aria-current={ehAtual("/") && !pathname.includes("categoria") ? "page" : undefined} className="nav-editoria nav-editoria--todas">
                Últimas
              </Link>
              {CATEGORIAS_NAV.map((c) => (
                <Link key={c.slug} href={`/?categoria=${encodeURIComponent(c.slug)}`} className="nav-editoria">
                  {c.label}
                </Link>
              ))}
            </div>
            <div className="cabecalho-nav-separador" aria-hidden="true" />
            <div className="cabecalho-nav-secundaria">
              <Link href="/comunidade" aria-current={ehAtual("/comunidade") ? "page" : undefined}>
                Comunidade
              </Link>
              <Link href="/radar" aria-current={ehAtual("/radar") ? "page" : undefined}>
                Radar
              </Link>
              <Link href="/planos" aria-current={ehAtual("/planos") ? "page" : undefined} className="nav-premium">
                Premium
              </Link>
              {usuario && (
                <>
                  <Link href="/jornalista/status" aria-current={ehAtual("/jornalista") ? "page" : undefined}>
                    Jornalista
                  </Link>
                  <Link href="/empresa" aria-current={ehAtual("/empresa") ? "page" : undefined}>
                    Empresa
                  </Link>
                  {usuario.papel === "admin" && (
                    <Link href="/admin" aria-current={ehAtual("/admin") ? "page" : undefined}>
                      Admin
                    </Link>
                  )}
                </>
              )}
            </div>
          </nav>
        </div>
      </div>
      <CommandPalette aberto={paletteAberto} aoFechar={() => setPaletteAberto(false)} />
    </header>
  );
}
