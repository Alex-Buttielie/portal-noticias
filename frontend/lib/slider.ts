/**
 * Avanço circular de índice — lógica pura do autoplay/navegação do
 * `ManchetePrincipalSlider` (run 20261013-1048-home-radar-central-ux,
 * Bloco H / H-01), extraída para ser testável sem montar nenhum componente
 * React nem depender de `setInterval`/DOM.
 */

/**
 * Próximo índice dentro de `[0, total)`, avançando `delta` posições (pode
 * ser negativo, para "anterior") e dando a volta nas duas pontas.
 *
 * `total <= 0` devolve sempre `0` — não há slide nenhum para apontar.
 */
export function proximoIndiceCircular(atual: number, total: number, delta = 1): number {
  if (total <= 0) return 0;
  return ((atual + delta) % total + total) % total;
}
