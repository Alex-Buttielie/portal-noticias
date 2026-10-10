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

/** `status` numerico, quando o erro o carrega de alguma forma. */
function statusNumerico(erro: unknown): number | null {
  if (typeof erro !== "object" || erro === null) return null;
  const s = (erro as { status?: unknown }).status;
  return typeof s === "number" ? s : null;
}

/** `name` declarado, quando o erro o carrega. */
function nomeDeclarado(erro: unknown): string | null {
  if (typeof erro !== "object" || erro === null) return null;
  const n = (erro as { name?: unknown }).name;
  return typeof n === "string" ? n : null;
}

/**
 * Classifica uma falha vinda de `obterPaginaEditorial`.
 *
 * So 404 e `inexistente`. Todo o resto -- 5xx, 429, 401, timeout, DNS,
 * `TypeError: fetch failed`, `ApiError` com status 0 (que e o que
 * `lib/api.ts` lanca quando o `fetch` nao alcanca a rede) -- e
 * `indisponivel`.
 *
 * POR QUE A CHECAGEM E POR FORMA E NAO SO POR `instanceof`
 * -------------------------------------------------------
 * A primeira versao usava apenas `erro instanceof ApiError`. Os testes
 * passavam. Em DEV, **nao** (medido em 2026-10-08): a pagina
 * `/paginas/<slug-que-nao-existe>` devolvia HTTP 200 com o estado de
 * indisponibilidade, quando o backend responde 404 -- medido direto em
 * `/api/moderacao/paginas/<slug>/`, que da 404 com corpo vazio.
 *
 * A causa e IDENTIDADE DE MODULO. A pagina importa `@/lib/api` e este arquivo
 * importa `./api`; no bundle do servidor do Next os dois caminhos podem
 * produzir DUAS classes `ApiError` distintas, e `instanceof` compara
 * identidade de construtor -- nao forma. Um teste em Node puro nao enxerga
 * isso, porque la o modulo e carregado uma vez so: O TESTE PASSAVA E A
 * APLICACAO ESTAVA ERRADA. E o motivo de a checagem exigir `name` alem de
 * `status`.
 *
 * `lib/api.ts` faz `this.name = "ApiError"` no construtor. `name` e
 * propriedade de instancia em tempo de execucao, entao sobrevive a duplicacao
 * de modulo, minificacao e reordenacao de import. O `instanceof` continua sendo
 * consultado: e o caminho mais direto quando ele funciona.
 *
 * E a exigencia de que o erro se declare `ApiError` continua valendo. Um
 * objeto solto com `{ status: 404 }` nao e afirmacao do backend. E
 * conservador de proposito: o custo de errar para `indisponivel` e mostrar um
 * estado de erro onde havia conteudo; o custo de errar para `inexistente` e um
 * 404 em pagina que existe.
 */
export function classificarErroPaginaEditorial(erro: unknown): SituacaoPaginaEditorial {
  if (statusNumerico(erro) !== 404) return "indisponivel";
  if (erro instanceof ApiError) return "inexistente";
  if (nomeDeclarado(erro) === "ApiError") return "inexistente";
  return "indisponivel";
}
