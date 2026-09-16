"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/auth-context";
import { useIsMobile } from "@/lib/hooks/useIsMobile";
import { NAV_ITENS, NAV_ITEM_CONTA, NAV_ITEM_LOGIN } from "@/lib/nav-itens";

export const BOTTOM_NAV_HEIGHT = "4rem";

export default function BottomNav() {
  const pathname = usePathname();
  const { usuario, carregando } = useAuth();
  const isMobile = useIsMobile();

  // evita flicker Entrar→Conta entre SSR e hidratação; preserve aria-current após carregar
  if (carregando) {
    return (
      <nav aria-hidden="true" className="fixed bottom-0 inset-x-0 z-[var(--z-cabecalho)] sm:hidden border-t border-[var(--cor-borda)] bg-[var(--cor-fundo)]/95 pb-[env(safe-area-inset-bottom)] pt-1 overscroll-contain touch-manipulation" />
    );
  }

  // hook mantido para cumprir contrato M1; render é CSS-first (sm:hidden), mas leitura evita código morto
  void isMobile;

  const itemConta = usuario ? NAV_ITEM_CONTA : NAV_ITEM_LOGIN;
  const itens = [...NAV_ITENS, itemConta];

  function isActive(href: string): boolean {
    if (href === "/") return pathname === "/";
    return pathname?.startsWith(href) ?? false;
  }

  return (
    <nav
      aria-label="Navegação principal móvel"
      className={cn(
        "fixed bottom-0 inset-x-0 z-[var(--z-cabecalho)] sm:hidden",
        "border-t border-[var(--cor-borda)] bg-[var(--cor-fundo)]/95 backdrop-blur supports-[backdrop-filter]:bg-[var(--vidro)]",
        "pb-[env(safe-area-inset-bottom)] pt-1",
        "overscroll-contain",
        "touch-manipulation"
      )}
    >
      <ul className="flex items-stretch justify-around gap-1 px-1">
        {itens.map((item) => {
          const Icon = item.icon;
          const ativo = isActive(item.href);
          return (
            <li key={item.href} className="flex-1">
              <Link
                href={item.href}
                aria-current={ativo ? "page" : undefined}
                data-active={ativo ? "true" : undefined}
                className={cn(
                  "flex flex-col items-center justify-center gap-1 rounded-md",
                  "min-h-[44px] py-1.5 px-1",
                  "touch-manipulation",
                  "text-[10px] leading-none font-medium",
                  "transition-colors motion-reduce:transition-none",
                  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] focus-visible:ring-offset-0",
                  ativo ? "text-[var(--cor-primaria)]" : "text-[var(--cor-texto-suave)] hover:text-[var(--cor-texto)]"
                )}
              >
                <Icon
                  className={cn("h-5 w-5 shrink-0", ativo && "text-[var(--cor-primaria)]")}
                  aria-hidden="true"
                />
                <span className="text-[10px] leading-none">{item.label}</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

// Re-export para fonte única do Sheet
export { NAV_ITENS, NAV_ITEM_CONTA, NAV_ITEM_LOGIN } from "@/lib/nav-itens";
