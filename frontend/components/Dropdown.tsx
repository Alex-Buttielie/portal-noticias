"use client";

import * as React from "react";
import * as DropdownMenuPrimitive from "@radix-ui/react-dropdown-menu";
import { MoreHorizontal } from "lucide-react";
import { cn } from "@/lib/utils";

export interface ItemDropdown {
  chave: string;
  rotulo: React.ReactNode;
  aoSelecionar?: () => void;
  disabled?: boolean;
}

const DropdownMenu = DropdownMenuPrimitive.Root;
const DropdownMenuTrigger = DropdownMenuPrimitive.Trigger;
const DropdownMenuGroup = DropdownMenuPrimitive.Group;
const DropdownMenuPortal = DropdownMenuPrimitive.Portal;

const DropdownMenuContent = React.forwardRef<
  React.ElementRef<typeof DropdownMenuPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof DropdownMenuPrimitive.Content>
>(({ className, sideOffset = 4, ...props }, ref) => (
  <DropdownMenuPrimitive.Portal>
    <DropdownMenuPrimitive.Content
      ref={ref}
      sideOffset={sideOffset}
      className={cn(
        "z-50 min-w-[12rem] overflow-hidden rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-1 shadow-md [overscroll-behavior:contain]",
        "data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 data-[side=bottom]:slide-in-from-top-2",
        "motion-reduce:animate-none",
        className
      )}
      {...props}
    />
  </DropdownMenuPrimitive.Portal>
));
DropdownMenuContent.displayName = DropdownMenuPrimitive.Content.displayName;

const DropdownMenuItem = React.forwardRef<
  React.ElementRef<typeof DropdownMenuPrimitive.Item>,
  React.ComponentPropsWithoutRef<typeof DropdownMenuPrimitive.Item> & { inset?: boolean }
>(({ className, inset, ...props }, ref) => (
  <DropdownMenuPrimitive.Item
    ref={ref}
    className={cn(
      "relative flex min-h-[44px] touch-manipulation cursor-default select-none items-center gap-2 rounded-sm px-2 py-2 text-sm break-words outline-none transition-colors motion-reduce:transition-none",
      "focus:bg-[var(--cor-primaria-suave)] focus:text-[var(--cor-primaria)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]",
      "data-[disabled]:pointer-events-none data-[disabled]:opacity-50",
      inset && "pl-8",
      className
    )}
    {...props}
  />
));
DropdownMenuItem.displayName = DropdownMenuPrimitive.Item.displayName;

const DropdownMenuSeparator = React.forwardRef<
  React.ElementRef<typeof DropdownMenuPrimitive.Separator>,
  React.ComponentPropsWithoutRef<typeof DropdownMenuPrimitive.Separator>
>(({ className, ...props }, ref) => (
  <DropdownMenuPrimitive.Separator ref={ref} className={cn("-mx-1 my-1 h-px bg-[var(--cor-borda)]", className)} {...props} />
));
DropdownMenuSeparator.displayName = DropdownMenuPrimitive.Separator.displayName;

export default function Dropdown({
  rotuloGatilho,
  itens,
  carregando = false,
  disabled = false,
  alinhamento = "esquerda",
}: {
  rotuloGatilho: React.ReactNode;
  itens: ItemDropdown[];
  carregando?: boolean;
  disabled?: boolean;
  alinhamento?: "esquerda" | "direita";
}) {
  return (
<DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          disabled={disabled}
          className={cn(
            "inline-flex min-h-[44px] touch-manipulation items-center justify-center gap-2 rounded-md border border-[var(--cor-borda)] bg-white px-4 text-sm font-medium",
            "hover:bg-[var(--cor-primaria-suave)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] focus-visible:ring-offset-2",
            "disabled:opacity-50 motion-reduce:transition-none transition-colors"
          )}
        >
          <MoreHorizontal className="h-4 w-4 opacity-50 botao--secundaria botao--medio" aria-hidden="true" />
          {rotuloGatilho}
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align={alinhamento === "direita" ? "end" : "start"}>
        {carregando && <div className="px-2 py-2 text-sm text-[var(--cor-texto-suave)]">Carregando…</div>}
        {!carregando &&
          itens.map((item) => (
            <DropdownMenuItem key={item.chave} disabled={item.disabled} onSelect={() => item.aoSelecionar?.()}>
              {item.rotulo}
            </DropdownMenuItem>
          ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

export {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuGroup,
  DropdownMenuPortal,
  DropdownMenuSeparator,
};
