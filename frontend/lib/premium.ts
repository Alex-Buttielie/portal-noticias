import { useCallback } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { obterStatusSistema } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";

const STALE_TIME_PUBLICO_MS = 60_000;

/**
 * Compatibilidade temporária para a tela Admin da etapa 2. O antigo cache em
 * módulo/localStorage foi removido; a tela Admin deve chamar
 * `invalidateQueries(queryKeys.premium.status())` pelo `QueryClient` da árvore.
 */
export function invalidarCachePremium(): void {
  // Não há cache global nem storage para invalidar neste módulo.
}

/**
 * M-08 (run 20261012-1806-monetizacao-sprint1) — mesma regra de "é Premium
 * ou o status ainda não é conhecido?" que `AdsSlot.tsx` usa para decidir se
 * mostra anúncio (`premiumGeral`), extraída aqui como função pura para ser
 * testável sem DOM/hooks: usuário com papel Premium/admin, OU o status
 * global do Premium ainda não carregou (`ativo === null`) — fail-open, nunca
 * trata "desconhecido" como Free. Usada pelo CTA de assinatura dentro da
 * leitura (`LeituraPremium.tsx`): o CTA só aparece quando isto é `false`
 * (Free confirmado).
 */
export function premiumOuStatusDesconhecido(isPremium: boolean, ativo: boolean | null): boolean {
  return isPremium || ativo === null;
}

/** Flag global Premium. `null` é o estado inicial; erro mantém fail-open. */
export function usePremiumAtivo(): {
  ativo: boolean | null;
  liberado: boolean;
  recarregar(): void;
} {
  const cliente = useQueryClient();
  const consulta = useQuery({
    queryKey: queryKeys.premium.status(),
    queryFn: async () => (await obterStatusSistema()).premium_ativo === true,
    enabled: typeof window !== "undefined",
    staleTime: STALE_TIME_PUBLICO_MS,
  });

  const ativo: boolean | null = consulta.data ?? null;
  const recarregar = useCallback(() => {
    void cliente.invalidateQueries({ queryKey: queryKeys.premium.status() });
  }, [cliente]);

  return { ativo, liberado: ativo !== true, recarregar };
}
