"use client";

// Navegação com aparência nativa por dispositivo.
// - Mobile: bottom tab bar (iOS translúcida / Android Material 3 com pill).
// - Tablet em paisagem: rail lateral compacto; em retrato: bottom bar.
// - Desktop/TV: null (o Header superior cobre).
// Reaproveita NAV_ITENS + regra de admin do BottomNav.

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useDispositivo } from "@/lib/dispositivos/DeviceProvider";
import { useAuth } from "@/lib/auth-context";
import { NAV_ITENS, NAV_ITEM_ADMIN, NAV_ITEM_CONTA } from "@/lib/nav-itens";
import { cn } from "@/lib/utils";

function rotaAtiva(pathname: string, href: string) {
  if (href === "/admin") return pathname.startsWith("/admin");
  return pathname === href;
}

function useItensNavegacao() {
  const { usuario } = useAuth();
  const isAdmin = usuario?.papel === "admin";
  return isAdmin
    ? [NAV_ITENS[0], NAV_ITENS[1], NAV_ITENS[2], NAV_ITEM_ADMIN, NAV_ITEM_CONTA]
    : [NAV_ITENS[0], NAV_ITENS[1], NAV_ITENS[2], NAV_ITEM_CONTA];
}

function BarraInferiorNativa() {
  const pathname = usePathname();
  const { so } = useDispositivo();
  const itens = useItensNavegacao();
  const ehIOS = so === "ios";

  return (
    <nav
      aria-label="Navegação principal"
      data-nav-nativa
      data-so={so}
      className={cn(
        "fixed inset-x-0 bottom-0 z-[var(--z-banner)] md:hidden",
        // iOS: translúcida com blur; Android: superfície sólida Material
        ehIOS
          ? "border-t border-[var(--cor-borda)] bg-[var(--vidro)] backdrop-blur-xl [-webkit-backdrop-filter:blur(20px)]"
          : "border-t border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] shadow-[0_-1px_8px_rgba(var(--cor-sombra),0.08)]"
      )}
      style={{ paddingBottom: "env(safe-area-inset-bottom)" }}
    >
      <ul className="mx-auto flex max-w-[560px] items-stretch justify-around px-1">
        {itens.map((item) => {
          const Icon = item.icon;
          const ativo = rotaAtiva(pathname, item.href);
          return (
            <li key={item.href} className="min-w-0 flex-1">
              <Link
                href={item.href}
                aria-current={ativo ? "page" : undefined}
                className={cn(
                  "relative flex min-h-[56px] flex-col items-center justify-center gap-1 px-1 py-2 outline-none transition-transform duration-100 active:scale-95",
                  "focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] focus-visible:ring-inset",
                  ativo ? "text-[var(--cor-primaria)]" : "text-[var(--cor-texto-suave)]"
                )}
              >
                {ehIOS ? (
                  <>
                    {ativo && (
                      <span
                        aria-hidden
                        className="absolute inset-x-6 top-0 h-0.5 rounded-full bg-[var(--cor-primaria)]"
                      />
                    )}
                    <Icon className="h-[22px] w-[22px]" strokeWidth={ativo ? 2.4 : 1.8} aria-hidden />
                    <span className="text-[10px] font-medium leading-none">{item.label}</span>
                  </>
                ) : (
                  <>
                    <span
                      aria-hidden
                      className={cn(
                        "flex h-8 w-16 items-center justify-center rounded-full transition-colors",
                        ativo ? "bg-[var(--cor-primaria-suave)]" : "bg-transparent"
                      )}
                    >
                      <Icon className="h-5 w-5" strokeWidth={ativo ? 2.4 : 2} aria-hidden />
                    </span>
                    <span className={cn("text-[11px] leading-none", ativo ? "font-semibold" : "font-medium")}>
                      {item.label}
                    </span>
                  </>
                )}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

function TrilhoTablet() {
  const pathname = usePathname();
  const itens = useItensNavegacao();
  return (
    <nav
      aria-label="Navegação principal"
      data-nav-trilho
      className="fixed bottom-0 left-0 top-14 z-[var(--z-banner)] hidden w-[76px] flex-col items-stretch border-r border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] py-2 min-[640px]:max-lg:flex"
      style={{ top: "var(--altura-cabecalho, 3.5rem)" }}
    >
      <ul className="flex flex-col gap-1 px-2">
        {itens.map((item) => {
          const Icon = item.icon;
          const ativo = rotaAtiva(pathname, item.href);
          return (
            <li key={item.href}>
              <Link
                href={item.href}
                aria-current={ativo ? "page" : undefined}
                className={cn(
                  "flex min-h-[60px] flex-col items-center justify-center gap-1 rounded-xl px-1 py-2 text-[10px] font-medium leading-none outline-none transition-colors active:scale-95",
                  "focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]",
                  ativo
                    ? "bg-[var(--cor-primaria-suave)] text-[var(--cor-primaria)]"
                    : "text-[var(--cor-texto-suave)] hover:bg-[var(--cor-fundo-elevado)]"
                )}
              >
                <Icon className="h-5 w-5" aria-hidden />
                <span className="max-w-full truncate">{item.label}</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

export function NavegacaoAdaptativa() {
  const { classe, orientacao } = useDispositivo();
  if (classe === "desktop" || classe === "tv") return null;
  if (classe === "tablet" && orientacao === "landscape") return <TrilhoTablet />;
  return <BarraInferiorNativa />;
}

export default NavegacaoAdaptativa;
