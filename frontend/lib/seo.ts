import type { Metadata } from "next";

/**
 * M-03: notícia sem resumo próprio é uma página fina (sem texto autoral) —
 * prejudica a qualidade do site para o Google e para o AdSense. Não
 * indexamos ("index: false"), mas continuamos permitindo que o crawler
 * siga o link ("follow: true") e que o leitor abra a página normalmente.
 *
 * Função pura para ser testável sem precisar de rede/servidor Next.
 */
export function robotsNoticiaSemResumo(resumo: string | null | undefined): Metadata["robots"] | undefined {
  if (resumo && resumo.trim().length > 0) return undefined;
  return { index: false, follow: true };
}
