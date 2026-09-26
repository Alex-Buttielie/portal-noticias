"use client";

import { useState, type ReactNode } from "react";
import { QueryClientProvider } from "@tanstack/react-query";
import { ThemeProvider } from "next-themes";
import { TooltipProvider } from "@radix-ui/react-tooltip";
import { AuthProvider } from "@/lib/auth-context";
import { criarQueryClient } from "@/lib/query-client";
import { QuerySessionBoundary } from "@/lib/query-session";
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
  const [queryClient] = useState(() => criarQueryClient());

  return (
    <ThemeProvider attribute="data-theme" enableSystem={false} defaultTheme="light">
      <QueryClientProvider client={queryClient}>
        <TooltipProvider>
          <ToastProvider>
            <DeviceProvider perfilInicial={perfilInicial}>
              <AuthProvider>
                <QuerySessionBoundary>{children}</QuerySessionBoundary>
              </AuthProvider>
            </DeviceProvider>
          </ToastProvider>
        </TooltipProvider>
      </QueryClientProvider>
    </ThemeProvider>
  );
}
