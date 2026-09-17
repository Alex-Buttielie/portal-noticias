"use client";

import { QueryClient } from "@tanstack/react-query";

let cliente: QueryClient | null = null;

export function obterQueryClient(): QueryClient {
  if (!cliente) {
    cliente = new QueryClient({
      defaultOptions: {
        queries: {
          staleTime: 60 * 1000,
          gcTime: 5 * 60 * 1000,
          retry: 1,
          refetchOnWindowFocus: false,
        },
      },
    });
  }
  return cliente;
}
