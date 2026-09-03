"use client";

import { useId, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import ThemeToggle from "@/components/ThemeToggle";

export default function Header() {
  const { usuario, carregando, fazerLogout } = useAuth();
  const pathname = usePathname();
  const [menuAberto, setMenuAberto] = useState(false);
  const navId = useId();

  function ehAtual(href: string): boolean {
    return href === "/" ? pathname === "/" : pathname?.startsWith(href) ?? false;
  }

  function ariaAtual(href: string): "page" | undefined {
    return ehAtual(href) ? "page" : undefined;
  }

  return (
    <header className="cabecalho">
      <div className="container cabecalho-conteudo">
        <Link href="/" className="cabecalho-logo">
          Portal de Notícias
        </Link>

        <button
          type="button"
          className="botao-menu-mobile"
          aria-expanded={menuAberto}
          aria-controls={navId}
          onClick={() => setMenuAberto((valor) => !valor)}
        >
          <span aria-hidden="true">{menuAberto ? "✕" : "☰"}</span>
          <span className="sr-only">{menuAberto ? "Fechar menu" : "Abrir menu"}</span>
          Menu
        </button>

        <nav
          id={navId}
          className={`cabecalho-nav${menuAberto ? " aberto" : ""}`}
          aria-label="Navegação principal"
        >
          <Link href="/" aria-current={ariaAtual("/")}>
            Feed
          </Link>
          <Link href="/comunidade" aria-current={ariaAtual("/comunidade")}>
            Comunidade
          </Link>
          <Link href="/radar" aria-current={ariaAtual("/radar")}>
            Radar
          </Link>
          <Link href="/planos" aria-current={ariaAtual("/planos")}>
            Premium
          </Link>
          {!carregando && usuario && (
            <>
              <Link href="/jornalista/status" aria-current={ariaAtual("/jornalista")}>
                Jornalista
              </Link>
              <Link href="/empresa" aria-current={ariaAtual("/empresa")}>
                Empresa
              </Link>
              {usuario.papel === "admin" && (
                <Link href="/admin/metricas" aria-current={ariaAtual("/admin")}>
                  Métricas
                </Link>
              )}
              <Link href="/minha-conta" aria-current={ariaAtual("/minha-conta")}>
                Minha conta
              </Link>
              <span
                className={
                  usuario.papel === "premium"
                    ? "selo-premium"
                    : usuario.papel === "admin"
                      ? "selo-premium"
                      : "selo-free"
                }
              >
                {usuario.papel === "premium" ? "Premium" : usuario.papel === "admin" ? "Admin" : "Free"}
              </span>
              <button
                type="button"
                className="botao botao-secundario"
                onClick={() => {
                  fazerLogout();
                }}
              >
                Sair
              </button>
            </>
          )}
          {!carregando && !usuario && (
            <>
              <Link href="/login" aria-current={ariaAtual("/login")}>
                Entrar
              </Link>
              <Link href="/cadastro" className="botao">
                Cadastrar
              </Link>
            </>
          )}
          <ThemeToggle />
        </nav>
      </div>
    </header>
  );
}
