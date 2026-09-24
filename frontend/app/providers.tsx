"use client";

import type { ReactNode } from "react";
import { ThemeProvider } from "next-themes";
import { TooltipProvider } from "@radix-ui/react-tooltip";
import { AuthProvider } from "@/lib/auth-context";
import { ToastProvider } from "@/components/ToastProvider";
import { DeviceProvider } from "@/lib/dispositivos/DeviceProvider";
import type { PerfilDispositivo } from "@/lib/dispositivos/tipos";

export function Providers({
  children,
  perfilInicial,
}: {
  children: ReactNode;
  perfilInicial?: PerfilDispositivo;
}) {
  return (
    <ThemeProvider attribute="data-theme" enableSystem={false} defaultTheme="light">
      <TooltipProvider>
        <ToastProvider>
          <DeviceProvider perfilInicial={perfilInicial}>
            <AuthProvider>{children}</AuthProvider>
          </DeviceProvider>
        </ToastProvider>
      </TooltipProvider>
    </ThemeProvider>
  );
}
