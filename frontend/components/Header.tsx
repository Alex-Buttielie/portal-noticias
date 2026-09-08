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

const NAV_PRINCIPAL = [
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

  const inicial = (usuario?.nome || usuario?.email || "?").trim().charAt(0).toUpperCase();

  return (
    <header className="topo">
      <div className="container topo__barra">
        <button
          type="button"
          className="topo__menu"
          aria-expanded={menuAberto}
          aria-controls={navId}
          aria-label={menuAberto ? "Fechar menu" : "Abrir menu"}
          onClick={() => setMenuAberto((v) => !v)}
        >
          <span aria-hidden="true">{menuAberto ? "✕" : "☰"}</span>
        </button>

        <Link href="/" className="topo__marca" aria-label="Portal de Notícias — início">
          <span className="topo__orbe" aria-hidden="true" />
          <span className="topo__nome">
            Portal<em>·</em>
          </span>
        </Link>

        <nav className="topo__nav" aria-label="Navegação principal">
          {NAV_PRINCIPAL.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              aria-current={ehAtual(item.href) ? "page" : undefined}
              className={`topo__link${item.destaque ? " topo__link--destaque" : ""}`}
            >
              {item.rotulo}
            </Link>
          ))}
        </nav>

        <div className="topo__acoes">
          <form className="topo__busca" onSubmit={onSubmitBusca} role="search">
            <input
              type="search"
              placeholder="Buscar…"
              aria-label="Buscar notícias"
              value={busca}
              onChange={(e) => setBusca(e.target.value)}
            />
          </form>
          <button
            type="button"
            className="topo__icone"
            onClick={() => setPaletteAberto(true)}
            aria-label="Busca rápida (Ctrl K)"
            title="Busca rápida (Ctrl K)"
          >
            <span aria-hidden="true">⌕</span>
          </button>
          <ThemeToggle />
          {!carregando &&
            (usuario ? (
              <>
                <Link href="/minha-conta" className="topo__avatar" aria-label="Minha conta">
                  {inicial}
                </Link>
                <button type="button" className="topo__sair" onClick={() => fazerLogout()}>
                  Sair
                </button>
              </>
            ) : (
              <>
                <Link href="/login" className="topo__link">
                  Entrar
                </Link>
                <Link href="/cadastro" className="botao botao--primaria botao--pequeno">
                  Assine
                </Link>
              </>
            ))}
        </div>
      </div>

      <div className="container">
        <nav id={navId} className={`topo__trilhas${menuAberto ? " aberto" : ""}`} aria-label="Editorias e áreas">
          <div className="topo__pills" role="group" aria-label="Filtrar por editoria">
            <Link href="/" className="topo__pill">
              Todas
            </Link>
            {CATEGORIAS_NAV.map((c) => (
              <Link key={c.slug} href={`/?categoria=${encodeURIComponent(c.slug)}`} className="topo__pill">
                {c.label}
              </Link>
            ))}
          </div>
          <div className="topo__areas">
            <Link href="/comunidade" aria-current={ehAtual("/comunidade") ? "page" : undefined}>
              Comunidade
            </Link>
            <Link href="/radar" aria-current={ehAtual("/radar") ? "page" : undefined}>
              Radar
            </Link>
            <Link href="/planos" aria-current={ehAtual("/planos") ? "page" : undefined} className="topo__link--destaque">
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
      <CommandPalette aberto={paletteAberto} aoFechar={() => setPaletteAberto(false)} />
    </header>
  );
}
