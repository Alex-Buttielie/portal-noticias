/**
 * Política de erro da página editorial — o que cada falha significa.
 *
 * POR QUE ESTA DECISÃO ESTÁ NOMEADA, E NÃO INLINE NO `catch`
 * =========================================================
 * O defeito que este arquivo corrige era um `catch` que tratava "a página não
 * existe" e "a API está fora" do mesmo jeito, com o mesmo fallback:
 *
 *     catch{ pagina={titulo: slugSeguro || "Página",
 *                   conteudo:`<p>Conteúdo editorial para <strong>${slugSeguro}</strong> em preparação.</p>`,
 *                   atualizado_em: new Date().toISOString()}; }
 *
 * Isso é conteúdo fictício servido como real — o que o **P0-08** proíbe — e
 * devolvia HTTP 200. Um 404 que se apresenta como 200 é pior que um 404,
 * porque monitor e leitor confiam nos dois.
 *
 * A correção é distinguir as duas causas, e a distinção é uma política: ela
 * decide o que a tela pode afirmar. Deixar isso dentro de um `catch` a torna
 * invisível para teste — e um `.tsx` de Server Component não é importável pelo
 * `node:test` (o `testes/hooks.mjs` resolve alias mas não transforma JSX, e o
 * strip de tipos do Node não cobre `.tsx`). Extrair a decisão para cá deixa a
 * política testável de verdade.
 *
 * A SEMÂNTICA
 * ===========
 * - `inexistente`: o backend AFFIRMOU, com status 404, que não há essa
 *   página. A única resposta honesta é 404.
 * - `indisponivel`: a API não respondeu, respondeu errado ou deu timeout.
 *   NÃO é prova de que a página não existe, e também NÃO autoriza inventar
 *   conteúdo. A resposta honesta é um estado de erro que diz isso.
 *
 * O `catch` original também não podia ser removido sem plano B: `next build`
 * roda no job `frontend-build` do CI, que não tem API, e sem tratamento de
 * erro o build quebraria. Por isso a distinção continua existindo — só deixou
 * de ser uma confusão.
 */
import { ApiError } from "./api";

export type SituacaoPaginaEditorial = "inexistente" | "indisponivel";

/**
 * Classifica uma falha vinda de `obterPaginaEditorial`.
 *
 * Só 404 é `inexistente`. Todo o resto — 5xx, 429, 401, timeout, DNS,
 * `TypeError: fetch failed`, `ApiError` com status 0 (que é o que
 * `lib/api.ts` lança quando o `fetch` não alcança a rede) — é
 * `indisponivel`.
 *
 * A checagem é por `instanceof ApiError` e não por `status === 404` num
 * objeto qualquer, para que um erro sem origem conhecida não seja tratado
 * como afirmação do backend. É conservador de propósito: o custo de errar
 * para `indisponivel` é mostrar um estado de erro onde havia conteúdo; o custo
 * de errar para `inexistente` é um 404 em página que existe.
 */
export function classificarErroPaginaEditorial(erro: unknown): SituacaoPaginaEditorial {
  if (erro instanceof ApiError && erro.status === 404) return "inexistente";
  return "indisponivel";
}