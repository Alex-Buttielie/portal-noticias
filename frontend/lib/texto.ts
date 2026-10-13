/**
 * Utilidades de truncamento de texto exibido na UI — extraídas para serem
 * testáveis sem renderizar nenhum componente (run
 * 20261013-1048-home-radar-central-ux, Bloco H / H-02).
 *
 * BUG QUE ISTO CORRIGE
 * --------------------
 * `NewsCard.tsx` cortava o resumo com `string.slice(0, max)` puro: um corte
 * por CONTAGEM DE CARACTERES, sem nenhuma consciência de onde as palavras
 * terminam e sem nenhum indicador de truncamento (`…`). O resultado visível
 * era um resumo que parava no meio de uma palavra, sem reticências — para
 * quem lê, indistinguível de um bug de dados faltando, não de um truncamento
 * intencional.
 */

/**
 * Corta `texto` em até `max` caracteres, preferindo parar no último espaço
 * encontrado (para não partir uma palavra no meio) e acrescentando `…`
 * sempre que o texto original for maior que o limite.
 *
 * `margemPalavra` (0-1): só recua até o último espaço se isso não descartar
 * mais que essa fração do orçamento de caracteres — evita um resultado
 * artificialmente curto quando a primeira "palavra" já é maior que `max`
 * (ex.: um token sem espaços) ou quando o único espaço está muito atrás.
 */
export function truncarPreservandoPalavra(
  texto: string,
  max: number,
  margemPalavra = 0.4
): string {
  const limpo = (texto || "").trim();
  if (max <= 0) return "";
  if (limpo.length <= max) return limpo;

  const cortado = limpo.slice(0, max);
  const ultimoEspaco = cortado.lastIndexOf(" ");
  const limiteRecuo = max * (1 - margemPalavra);
  const base = ultimoEspaco >= limiteRecuo ? cortado.slice(0, ultimoEspaco) : cortado;
  return `${base.trimEnd()}…`;
}
