"use client";

import type { ReactNode } from "react";
import { QueryClientProvider } from "@tanstack/react-query";
import { ThemeProvider } from "next-themes";
import { TooltipProvider } from "@radix-ui/react-tooltip";
import { obterQueryClient } from "@/lib/query-client";
import { AuthProvider } from "@/lib/auth-context";
import { ToastProvider } from "@/components/ToastProvider";

export function Providers({ children }: { children: ReactNode }) {
  return (
    <ThemeProvider attribute="data-theme" enableSystem={false} defaultTheme="light">
      <QueryClientProvider client={obterQueryClient()}>
        <TooltipProvider>
          <ToastProvider>
            <AuthProvider>{children}</AuthProvider>
          </ToastProvider>
        </TooltipProvider>
      </QueryClientProvider>
    </ThemeProvider>
  );
}
