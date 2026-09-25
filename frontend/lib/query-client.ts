"use client";

import { QueryClient } from "@tanstack/react-query";

export const STALE_TIME_PUBLICO_MS = 60_000;
export const GC_TIME_MS = 5 * 60_000;

/**
 * Cria um cliente isolado por árvore cliente. Não há singleton de módulo: o
 * provider usa `useState`, portanto requisições SSR nunca compartilham cache.
 * O cache é somente em memória; não há dehydrate, hydrate nem persistência.
 */
export function criarQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: STALE_TIME_PUBLICO_MS,
        gcTime: GC_TIME_MS,
        retry: 1,
        refetchOnWindowFocus: false,
        refetchOnReconnect: true,
      },
    },
  });
}
