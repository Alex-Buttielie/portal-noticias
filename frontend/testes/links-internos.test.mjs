/**
 * Integridade dos links internos: nenhum `href` para um caminho que não existe.
 *
 * POR QUE ESTE TESTE EXISTE (o bug que ele pega)
 * ================================================
 * MEDIDO em 2026-10-08 nos logs de acesso de DEV e de PROD: 2 requisições por
 * dia de `GET /privacidade/cookies` e 2 de `GET /privacidade/termos`, todas
 * com `_rsc=` (prefetch do App Router) e todas respondendo **404**.
 *
 * Quem gerava as requisições era o próprio portal. `Rodape.tsx` e
 * `BannerConsentimentoCookies.tsx` apontavam para `/privacidade/cookies` e
 * `/privacidade/termos`; as rotas que existem são `/cookies` e `/termos`.
 *
 * O que tornava isso grave, e não cosmético: o link quebrado estava no
 * **banner de consentimento de cookies**, cujo texto diz "Veja nossa política
 * de cookies". O link que a LGPD manda oferecer morria em 404. E o rodapé —
 * que é onde se procura contato e política — tinha dois 404.
 *
 * NADA no projeto pegava isso: não há runner de rotas, não há lint de `href`,
 * e o build do Next não reclama de `Link` para página inexistente — ele
 * compila, e o 404 só aparece no log de acesso do nginx, dias depois. É
 * exatamente o tipo de defeito que sobrevive a todos os gates.
 *
 * AS DUAS REGRAS
 * ==============
 * 1. `href` estático tem que resolver para uma rota real do App Router
 *    (`app/**\/page.tsx` ou `app/**\/route.ts`) ou para um redirect declarado
 *    em `next.config.js`. Um caminho que não é nenhum dos dois é 404 na
 *    produção, garantido.
 *
 * 2. `href` estático que entra numa rota DINÂMICA (`app/**\/[param]/**`) tem
 *    que constar do `generateStaticParams` daquela rota. É o que pega slug
 *    digitado errado: sem essa regra, `/categoria/cultura` passaria mesmo se o
 *    slug fosse `culturaa`.
 *
 * O QUE ESTE TESTE NÃO CONSEGUE VER (e é importante saber)
 * =======================================================
 * A falha que motivou a regra 2 ter sido aceita como "suficiente" era outra:
 * `/paginas/sobre` estava declarado no `generateStaticParams` de
 * `app/paginas/[slug]/page.tsx` — então a regra 2 passaria — mas esse slug não
 * existe em `moderacao_PaginaEditorial` (só existem `politica-editorial` e
 * `termos-de-uso`, medido nos três bancos). A rota ainda fabricava conteúdo e
 * devolvia 200.
 *
 * Esse desalinhamento é entre o CÓDIGO e o BANCO, e este teste roda sem banco.
 * Não afirma que está coberto: afirma que está **fora** do que ele cobre.
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";

const RAIZ = path.resolve(import.meta.dirname, "..");
const APP = path.join(RAIZ, "app");

/** Todo arquivo sob `dir` com um dos sufixos, pulando `node_modules` e `.next`. */
function arquivos(dir, sufixos) {
  const saida = [];
  const pilha = [dir];
  while (pilha.length) {
    const atual = pilha.pop();
    for (const entrada of fs.readdirSync(atual, { withFileTypes: true })) {
      if (entrada.name === "node_modules" || entrada.name === ".next") continue;
      const completo = path.join(atual, entrada.name);
      if (entrada.isDirectory()) pilha.push(completo);
      else if (sufixos.some((s) => entrada.name.endsWith(s))) saida.push(completo);
    }
  }
  return saida;
}

/**
 * Lê um arquivo como texto SEM perder conteúdo por causa de encoding.
 *
 * Existe pelo menos um arquivo do frontend que não é UTF-8 válido
 * (`components/ui/pagination.tsx` — medido). Se o teste simplesmente pulasse
 * arquivo ilegível, ele perderia a cobertura justamente onde há menos
 * conferência, e o defeito apareceria como "teste passa". Ler em latin1 é
 * semanticamente errado para o resto do arquivo, mas paraextrair `href` não
 * há diferença — e nenhum link é descartado.
 */
function lerTexto(caminho) {
  const buf = fs.readFileSync(caminho);
  try {
    return buf.toString("utf8");
  } catch {
    return buf.toString("latin1");
  }
}

/** Caminho de rota do App Router a partir de um `page.tsx`/`route.ts`. */
function rotaDe(caminhoArquivo) {
  const rel = path.relative(APP, path.dirname(caminhoArquivo));
  const partes = rel.split(path.sep).filter((p) => p && !(p.startsWith("(") && p.endsWith(")")));
  return partes.length ? "/" + partes.join("/") : "/";
}

/** Rotas concretas do App Router. */
function rotasDoApp() {
  const estaticas = new Map(); // rota -> arquivo
  const dinamicas = new Map(); // "/categoria/[slug]" -> { arquivo, padroes:Set }
  for (const arq of arquivos(APP, ["page.tsx", "route.ts"])) {
    const rota = rotaDe(arq);
    if (rota.includes("[")) {
      dinamicas.set(rota, { arquivo: arq, padroes: slugsEstaticosDe(arq) });
    } else {
      estaticas.set(rota, arq);
    }
  }
  return { estaticas, dinamicas };
}

/**
 * Slugs declarados no `generateStaticParams` de uma rota.
 *
 * Lê o código-fonte e não importa o módulo: `generateStaticParams` é uma
 * função, e a alternativa seria compilar/executar a página para extrair um
 * array literal. Aceita `[{slug:"termos"}]`, `[{ slug: "termos" }]` e
 * `[{slug: 'termos'}]`. Se a rota não declarar nada, devolve conjunto vazio —
 * e a regra 2 cobra o slug de outro jeito.
 */
function slugsEstaticosDe(caminhoArquivo) {
  const txt = lerTexto(caminhoArquivo);
  const achados = new Set();
  const corpo = (txt.match(/generateStaticParams\s*\(\)\s*\{([\s\S]*?)\n\}/) || [])[1];
  if (!corpo) return achados;
  for (const m of corpo.matchAll(/\bslug\s*:\s*["']([^"']+)["']/g)) achados.add(m[1]);
  for (const m of corpo.matchAll(/\bslug\s*:\s*`([^`$]+)`/g)) achados.add(m[1]);
  return achados;
}

/**
 * `source` de cada redirect declarado em `next.config.js`.
 *
 * `redirects()` é `async` no Next, então devolve Promise — chamar e usar como
 * array dá `undefined.map is not a function`, que é a forma mais confusa de
 * esse defeito aparecer.
 */
async function redirectsDeclarados() {
  const config = createRequire(import.meta.url)(path.join(RAIZ, "next.config.js"));
  const brutos = typeof config.redirects === "function" ? await config.redirects() : [];
  return new Map((brutos || []).map((r) => [r.source, r.destination]));
}

/**
 * `href` estáticos de um arquivo.
 *
 * Só interessa link INTERNO e ESTÁTICO:
 *  - `"/categoria/cultura"` entra; `/categoria/${slug}` e `/noticia/${id}` não,
 *    porque o alvo depende de dado e não pode ser conferido contra as rotas;
 *  - `"/privacidade/cookies"` entra; `"/?categoria=politica"` não, porque é a
 *    home com query — existe;
 *  - `"http://..."` e `"mailto:..."` não entram.
 */
const RE_HREF = /href\s*=\s*(?:\{\s*)?["'](\/[^"'#?{}`\s]*)["']/g;

function hrefsEstaticos(txt) {
  const achados = new Map();
  for (const m of txt.matchAll(RE_HREF)) {
    if (!achados.has(m[1])) achados.set(m[1], []);
    achados.get(m[1]).push(1);
  }
  return [...achados.keys()];
}

// ---------------------------------------------------------------------------

test("todo href interno estatico resolve para uma rota real ou um redirect declarado", async () => {
  const { estaticas, dinamicas } = rotasDoApp();
  const redirects = await redirectsDeclarados();

  const origens = [
    ...arquivos(path.join(RAIZ, "app"), [".tsx", ".ts"]),
    ...arquivos(path.join(RAIZ, "components"), [".tsx", ".ts"]),
  ];

  const quebrados = [];
  const slugsNaoDeclarados = [];

  for (const arq of origens) {
    const txt = lerTexto(arq);
    for (const href of hrefsEstaticos(txt)) {
      const normalizado = href.replace(/\/$/, "") || "/";

      if (estaticas.has(normalizado) || estaticas.has(href) || redirects.has(normalizado) || redirects.has(href)) continue;

      // A regra 2: cai numa rota dinâmica? O caminho concreto tem que estar
      // entre os slugs que ela declara.
      //
      // O casamento é pelo PREFIXO ESTÁTICO, não pela chave completa:
      // `/categoria/[slug]` nunca é prefixo de `/categoria/cultura`, porque o
      // `[slug]` está no meio. O que separa as duas coisas é o primeiro
      // segmento com `[` — o que vem antes é o prefixo, e o segmento seguinte
      // é o slug a conferir.
      const casa = [...dinamicas.entries()].find(([r]) => {
        const estaticos = r.split("/").filter((s) => s && !s.includes("["));
        return estaticos.length > 0 && normalizado.startsWith("/" + estaticos.join("/") + "/");
      });
      if (casa) {
        const [rotaDinamica, { padroes }] = casa;
        const estaticos = rotaDinamica.split("/").filter((s) => s && !s.includes("["));
        const slug = normalizado.split("/")[estaticos.length + 1];
        // `generateStaticParams` vazio = rota gerada sob demanda. Não dá para
        // conferir o slug, mas também não é erro por si.
        if (padroes.size && !padroes.has(slug)) {
          slugsNaoDeclarados.push(
            `${path.relative(RAIZ, arq)}: ${href} -> ${rotaDinamica} declara [${[...padroes].sort().join(", ")}], nao "${slug}"`
          );
        }
        continue;
      }

      quebrados.push(
        `${path.relative(RAIZ, arq)}: ${href} nao e rota (${estaticas.size} rotas estaticas, ${dinamicas.size} dinamicas) nem redirect declarado`
      );
    }
  }

  assert.deepEqual(
    quebrados,
    [],
    `hrefs internos que dariam 404 em producao (${quebrados.length}):\n  ${quebrados.join("\n  ")}`
  );
  assert.deepEqual(
    slugsNaoDeclarados,
    [],
    `hrefs com slug que a rota dinamica nao declara (${slugsNaoDeclarados.length}):\n  ${slugsNaoDeclarados.join("\n  ")}`
  );
});

test("a base do teste enxerga o que ela diz enxergar (o alcance nao e zero)", async () => {
  // Um teste que passa porque nao achou nada nao mede nada. Este teste falha se
  // a coleta silenciosamente zerar — o modo de falha mais comum quando um
  // glob ou um filtro muda.
  const { estaticas, dinamicas } = rotasDoApp();
  assert.ok(estaticas.size >= 40, `so achei ${estaticas.size} rotas estaticas; a varredura esta quebrada`);
  assert.ok(dinamicas.size >= 5, `so achei ${dinamicas.size} rotas dinamicas; a varredura esta quebrada`);
  assert.ok(estaticas.has("/cookies"), "a rota /cookies sumiu da varredura");
  assert.ok(estaticas.has("/termos"), "a rota /termos sumiu da varredura");

  const redirects = await redirectsDeclarados();
  assert.ok(redirects.size >= 4, `so achei ${redirects.size} redirects; next.config.js parou de ser lido`);

  const todos = hrefsEstaticos(lerTexto(path.join(RAIZ, "components", "Rodape.tsx")));
  assert.ok(todos.length >= 5, `so achei ${todos.length} hrefs no Rodape; a extracao de href esta quebrada`);
});

test("o portfolio de hrefs nao encolheu (o teste nao esta virando no-op)", () => {
  // Trava o numero minimo de hrefs internos estaticos no codigo. Se um refactor
  // trocar todo `Link` por `router.push` com string, este numero cai e o teste
  // avisa — porque a partir dai a regra 1 deixa de medir o que ela mede hoje.
  const origens = [
    ...arquivos(path.join(RAIZ, "app"), [".tsx"]),
    ...arquivos(path.join(RAIZ, "components"), [".tsx"]),
  ];
  let total = 0;
  for (const arq of origens) total += hrefsEstaticos(lerTexto(arq)).length;
  // BASE MEDIDA em 2026-10-08: 71 hrefs internos estáticos distintos, somados
  // por arquivo. O limiar é 65 e não 71 de propósito: 71 transformaria a
  // remoção de UM link legítimo em build vermelho, e teste que protesta de
  // tudo acaba não sendo lido. 65 ainda pega o modo de falha que importa — a
  // coleta virando zero — e deixa cinco de folga.
  assert.ok(total >= 65, `so achei ${total} hrefs internos estaticos (base medida: 71); a regra 1 pode ter parado de medir`);
});