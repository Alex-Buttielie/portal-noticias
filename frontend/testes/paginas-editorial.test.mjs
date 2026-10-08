/**
 * Política de erro da página editorial: 404 de verdade, zero fabricação.
 *
 * O DEFEITO
 * ==========
 * `app/paginas/[slug]/page.tsx` tratava um `catch` de qualquer origem com o
 * mesmo fallback:
 *
 *     catch{ pagina={titulo: slugSeguro || "Página",
 *                   conteudo:`<p>Conteúdo editorial para <strong>${slugSeguro}</strong> em preparação.</p>`,
 *                   atualizado_em: new Date().toISOString()}; }
 *
 * Conteúdo fictício servido como real — o que o **P0-08** proíbe — devolvendo
 * **HTTP 200**. Um 404 que se apresenta como 200 é pior que um 404: monitor e
 * leitor confiam nos dois.
 *
 * MEDIDO em 2026-10-08 nos três bancos: `moderacao_PaginaEditorial` tem
 * `politica-editorial` e `termos-de-uso`. O `generateStaticParams` declarava
 * `termos` e `sobre` — nenhum dos dois existe — e o rodapé linkava "Sobre" para
 * `/paginas/sobre`, que fabricava "Conteúdo editorial para sobre em
 * preparação" com 200, enquanto a rota real `/sobre` respondia 200 com
 * conteúdo de verdade.
 *
 * O QUE ESTE TESTE MEDE, E O QUE ELE NÃO CONSEGUE MEDIR
 * ======================================================
 * A página é um Server Component em `.tsx`. O `testes/hooks.mjs` resolve o
 * alias `@/` mas NÃO transforma JSX, e o strip de tipos do Node não cobre
 * `.tsx` — então a página não é importável aqui, e nenhum teste desta suíte
 * pode chamá-la. Não élimitação contornável sem trocar o runner.
 *
 * A decisão que produz o defeito — "isto é 404 ou é indisponibilidade?" — foi
 * extraída para `lib/paginas-editoriais.ts` justamente para ser testável, e é
 * ela que este arquivo mede, com `ApiError` de verdade e não com objeto
 * literais. A LIGAÇÃO entre a decisão e a tela (a página chama `notFound()`
 * no caso `inexistente`) não é comportamento observável aqui, e é conferida por
 * leitura do fonte, marcada como o que é: uma trava de regressão, não uma
 * prova.
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { ApiError } from "@/lib/api";
import { classificarErroPaginaEditorial } from "@/lib/paginas-editoriais";

const RAIZ = path.resolve(import.meta.dirname, "..");
const FONTE_PAGINA = path.join(RAIZ, "app", "paginas", "[slug]", "page.tsx");

// ---------------------------------------------------------------------------
// A política: o que cada status significa
// ---------------------------------------------------------------------------

test("404 do backend e a UNICA coisa que significa 'a pagina nao existe'", () => {
  assert.equal(classificarErroPaginaEditorial(new ApiError(404, { detail: "nao encontrada" }, "nao encontrada")), "inexistente");
});

test("API fora do ar e' indisponibilidade, e nao prova de inexistencia", () => {
  // `lib/api.ts` lanca `ApiError` com status 0 quando o `fetch` nao alcanca a
  // rede. Status 0 NAO e 404, e tratar como 404 apagaria paginas que existem.
  assert.equal(classificarErroPaginaEditorial(new ApiError(0, null, "nao foi possivel conectar")), "indisponivel");

  // `fetch failed` chega como TypeError, sem passar por ApiError.
  assert.equal(classificarErroPaginaEditorial(new TypeError("fetch failed")), "indisponivel");

  // 5xx: o backend respondeu, mas nao sobre esta pagina.
  assert.equal(classificarErroPaginaEditorial(new ApiError(500, null, "erro interno")), "indisponivel");

  // 503 durante manutencao e deploy.
  assert.equal(classificarErroPaginaEditorial(new ApiError(503, null, "indisponivel")), "indisponivel");

  // 429 com throttle: existe pagina, existe reader, so o limite bateu.
  assert.equal(classificarErroPaginaEditorial(new ApiError(429, null, "muitospedidos", 60)), "indisponivel");
});

test("erro sem origem conhecida NAO e tratado como afirmacao do backend", () => {
  // Conservador de proposito: o custo de errar para `indisponivel` e mostrar
  // um estado de erro onde havia conteudo; o custo de errar para `inexistente`
  // e um 404 em pagina que existe.
  for (const erro of [undefined, null, {}, "404", 404, new Error("404 Not Found"), { status: 404 }]) {
    assert.equal(
      classificarErroPaginaEditorial(erro),
      "indisponivel",
      `objeto sem origem (${JSON.stringify(erro) ?? String(erro)}) foi tratado como afirmacao do backend`
    );
  }
});

test("a politica sobrevive a DUAS copias da classe ApiError", () => {
  // REGRESSAO REAL, medida em 2026-10-08. A primeira versao usava so
  // `erro instanceof ApiError`. Os testes passavam; em DEV a pagina devolvia
  // 200 com o estado de indisponibilidade quando o backend respondia 404.
  //
  // A causa: a pagina importa `@/lib/api` e a politica importa `./api`, e no
  // bundle do servidor do Next isso pode dar DUAS classes `ApiError`. `instanceof`
  // compara identidade de construtor, entao a segunda copia nao e reconhecido.
  // Este teste em Node puro carrega o modulo UMA vez -- e por isso nao via o
  // problema. Aqui as duas identities sao construidas de proposito.
  //
  // Uma classe com a MESMA forma, mas identidade diferente: e o que o bundle
  // produz.
  class ApiErrorDeOutraCopia extends Error {
    constructor(status, detail, message) {
      super(message);
      this.name = "ApiError";
      this.status = status;
      this.detail = detail;
    }
  }
  assert.notEqual(
    ApiErrorDeOutraCopia,
    ApiError,
    "esta simulacao parou de simular: as duas classes viraram a mesma"
  );

  // A copia estranha, com 404, tem de ser reconhecida como 404.
  assert.equal(
    classificarErroPaginaEditorial(new ApiErrorDeOutraCopia(404, { detail: "nao encontrada" }, "nao encontrada")),
    "inexistente",
    "uma ApiError de outra copia do modulo nao foi reconhecida; o bundle do Next produz exatamente isso"
  );

  // E o inverso: a copia estranha NAO pode fabricar um 404 onde nao ha.
  assert.equal(classificarErroPaginaEditorial(new ApiErrorDeOutraCopia(500, null, "erro")), "indisponivel");
  assert.equal(classificarErroPaginaEditorial(new ApiErrorDeOutraCopia(0, null, "sem rede")), "indisponivel");

  // Uma classe com `status: 404` mas que NAO se declara ApiError continua nao
  // sendo afirmação do backend -- a checagem por `name` tem que valer.
  class OutroErro extends Error {
    constructor() {
      super("404");
      this.name = "OutroErro";
      this.status = 404;
    }
  }
  assert.equal(classificarErroPaginaEditorial(new OutroErro()), "indisponivel");

  // E o motivo de `name` ser exigido: uma classe com `name` correto e status
  // nao numerico nao vira 404.
  class ApiErrorSemStatus extends Error {
    constructor() {
      super("sem status");
      this.name = "ApiError";
    }
  }
  assert.equal(classificarErroPaginaEditorial(new ApiErrorSemStatus()), "indisponivel");
});

test("o erro que o backend manda e' lido do status, nao da mensagem", () => {
  // Dois erros com mensagens opostas e o mesmo status tem de dar a mesma
  // resposta: o status e a afirmacao do backend, a mensagem e para o humano.
  const neg404 = new ApiError(404, null, "Pagina inexistente");
  const pos404 = new ApiError(404, null, "Tudo certo");
  assert.equal(classificarErroPaginaEditorial(neg404), "inexistente");
  assert.equal(classificarErroPaginaEditorial(pos404), "inexistente");

  // E um 200 nunca chega aqui como erro, mas se chegar, e' indisponibilidade.
  assert.equal(classificarErroPaginaEditorial(new ApiError(200, null, "ok")), "indisponivel");
});

// ---------------------------------------------------------------------------
// Trava de regressao sobre o fonte (declaradamente NAO e prova de comportamento)
// ---------------------------------------------------------------------------

test("a pagina nao fabrica mais conteudo editorial", () => {
  const fonte = fs.readFileSync(FONTE_PAGINA, "latin1");

  // 1. O fallback de fabricacao, com o texto que ele escrevia.
  assert.doesNotMatch(
    fonte,
    /em prepara/i,
    "a fabricacao 'em preparação' voltou para app/paginas/[slug]/page.tsx. Isso viola o P0-08 e devolve 200 para uma pagina que nao existe."
  );

  // 2. A ligacao com a politica: `notFound()` tem que estar no ramo
  // `inexistente`. Leitura do fonte, nao execucao — a pagina nao e
  // importavel pelo `node:test` (ver o cabecalho).
  assert.match(
    fonte,
    /classificarErroPaginaEditorial\([\s\S]*?\)\s*===\s*"inexistente"\)\s*notFound\(\)/,
    "a pagina deixou de chamar notFound() no caso 'inexistente'; um slug inexistente voltaria a devolver 200"
  );

  // 3. A politica vem do modulo, e nao de uma copia local do `status === 404`.
  assert.match(
    fonte,
    /import \{ classificarErroPaginaEditorial \} from "@\/lib\/paginas-editoriais"/,
    "a pagina nao usa a politica extraida; a distincao pode ter voltado a ser um detalhe do catch"
  );
});

test("generateStaticParams nao volta a declarar slug que o banco nao tem", () => {
  // MEDIDO nos tres bancos em 2026-10-08: `moderacao_PaginaEditorial` tem
  // apenas `politica-editorial` e `termos-de-uso`. A funcao declarava
  // `termos` e `sobre`, e por isso pre-renderizava duas paginas ficticias com
  // 200 no build.
  const fonte = fs.readFileSync(FONTE_PAGINA, "latin1");
  assert.doesNotMatch(
    fonte,
    /export function generateStaticParams/,
    "generateStaticParams voltou. Se a rota voltar a pre-renderizar, so pode declarar os slugs do seed (politica-editorial, termos-de-uso) — e o build do CI, que nao tem API, precisa de um caminho que nao fabrique conteudo."
  );
});

test("o seed do backend e o que a politica presume existir", () => {
  // Este teste nao sobe banco. Ele existe para tornar explicito o contrato:
  // `lib/paginas-editoriais.ts` presume que 404 significa "o backend disse que
  // nao existe". Se o backend passar a devolver 200 com objeto vazio, essa
  // presumicao quebra em silencio e a pagina volta a renderizar pagina vazia.
  const seed = fs.readFileSync(
    path.join(RAIZ, "..", "backend", "moderacao", "migrations", "0002_seed_paginas_legais.py"),
    "latin1"
  );
  const slugs = [...seed.matchAll(/\(\s*"([a-z0-9-]+)"\s*,/g)].map((m) => m[1]);
  assert.ok(slugs.includes("politica-editorial"), `o seed nao tem mais politica-editorial; slugs: ${slugs}`);
  assert.ok(slugs.includes("termos-de-uso"), `o seed nao tem mais termos-de-uso; slugs: ${slugs}`);
  assert.ok(
    !slugs.includes("sobre") && !slugs.includes("termos"),
    `o seed passou a ter 'sobre'/'termos', que eram exatamente os slugs que o rodape linkava e que o banco nao tinha. Se isso e proposital, atualize o redirect de /paginas/sobre em next.config.js. slugs: ${slugs}`
  );
});