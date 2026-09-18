"use client";

import type { ReactNode } from "react";
import { QueryClientProvider } from "@tanstack/react-query";
import { ThemeProvider } from "next-themes";
import { TooltipProvider } from "@radix-ui/react-tooltip";
import { obterQueryClient } from "@/lib/query-client";
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
      <QueryClientProvider client={obterQueryClient()}>
        <TooltipProvider>
          <ToastProvider>
            <DeviceProvider perfilInicial={perfilInicial}>
              <AuthProvider>{children}</AuthProvider>
            </DeviceProvider>
          </ToastProvider>
        </TooltipProvider>
      </QueryClientProvider>
    </ThemeProvider>
  );
}
