"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { NAV_ITENS, NAV_ITEM_CONTA } from "@/lib/nav-itens";
export function BottomNav() {
  const pathname = usePathname();
  const itens = [...NAV_ITENS.slice(0, 4), NAV_ITEM_CONTA].slice(0, 5);
  return (
    <nav aria-label="Navegação inferior" className="fixed inset-x-0 bottom-0 z-[var(--z-banner)] border-t border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] pb-[env(safe-area-inset-bottom)] md:hidden">
      <ul className="mx-auto flex max-w-[1280px] items-center justify-around px-2 py-1">
        {itens.map((item) => {
          const Icon = item.icon;
          const ativo = pathname === item.href;
          return (
            <li key={item.href} className="flex-1">
              <Link href={item.href} className={cn("flex flex-col items-center gap-0.5 rounded-md px-2 py-2 text-[10px] font-medium leading-none", ativo ? "text-[var(--cor-primaria)]" : "text-[var(--cor-texto-suave)]")}>
                <Icon className={cn("h-5 w-5", ativo && "text-[var(--cor-primaria)]")} aria-hidden />
                <span className="text-balance">{item.label}</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
