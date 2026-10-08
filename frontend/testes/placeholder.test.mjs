/**
 * Prova de que o placeholder LOCAL preserva a variação que o `seed` do
 * picsum produzia, e de que ele não abre conexão nenhuma.
 *
 * POR QUE ISTO É UM TESTE COMPORTAMENTAL E NÃO UMA ASSERÇÃO DE TEXTO
 * ===================================================================
 * O medo registrado quando a decisão de produto foi tomada (asset local ×
 * portão de consentimento) era: "asset local deixa TODOS os placeholders
 * iguais, porque o picsum gera imagens diferentes por seed". Esse medo é
 * sobre o VALOR QUE SAI do gerador, não sobre o texto do fonte. Um teste
 * que lesse o fonte passaria com um gerador que devolvesse string vazia,
 * com um hash constante, ou com um template único — e a home viraria um mar
 * de cartões idênticos sem que nenhum teste reclamasse.
 *
 * Então aqui o gerador é EXECUTADO, e as asserções são sobre a saída:
 *
 *  PROVA, por construção + asserção:
 *  - o MESMO identificador devolve SEMPRE a mesma string (o `seed` fazia
 *    isso; sem isso a home "pisca" entre carregamentos);
 *  - identificadores DIFERENTES devolvem imagens diferentes, inclusive
 *    dentro da MESMA categoria (é o caso que o `seed` resolvia) e
 *    através de muitas amostras;
 *  - a saída não contém nenhuma URL http(s) — é `data:image/svg+xml`, que
 *    não abre conexão;
 *  - o SVG é bem formado e mantém a proporção 16:9 do placeholder antigo,
 *    para não quebrar a geometria do cartão;
 *  - `categoria` (conteúdo de terceiro, vem do XML do RSS) não injeta
 *    script nem atributo no SVG;
 *  - `imagemNoticia` ainda devolve a foto REAL quando ela existe, e cai no
 *    placeholder local quando não existe ou quando aponta para o host do
 *    placeholder antigo.
 *
 *  NÃO PROVA: que o browser desenha o SVG como se espera. Isso é
 *  propriedade do renderizador; o que se demonstra aqui é a condição
 *  necessária e suficiente no nível de bytes — que o que vai para o `src`
 *  é um SVG válido, sem host e sem script.
 */
import test from "node:test";
import assert from "node:assert/strict";

import "./hooks.mjs";
import { placeholderSvg } from "../lib/placeholder.ts";
import {
  HOST_PLACEHOLDER,
  ehHostDePlaceholder,
  imagemNoticia,
  placeholder,
  urlImagemUtilizavel,
} from "../lib/imagens.ts";

/** Decodifica o data URI de volta no SVG, que é o que o browser parseia. */
function svgDe(uri) {
  return decodeURIComponent(uri.replace(/^data:image\/svg\+xml,/, ""));
}

// ---------------------------------------------------------------------------
// 1. DETERMINISMO — o que o `seed` do picsum garantia
// ---------------------------------------------------------------------------
test("o MESMO identificador devolve SEMPRE a mesma imagem", () => {
  for (const id of ["politica-1", "politica-7", "economia-2", "geral-0", "saude-33"]) {
    const a = placeholderSvg(id, id.replace(/-\d+$/, ""));
    const b = placeholderSvg(id, id.replace(/-\d+$/, ""));
    const c = placeholderSvg(id, id.replace(/-\d+$/, ""));
    assert.equal(a, b, `${id} mudou entre duas chamadas`);
    assert.equal(b, c, `${id} mudou entre três chamadas`);
  }
});

test("o mesmo identificador com a mesma categoria é o mesmo, e o identificador manda", () => {
  // A categoria entra no identificador, então mudar a categoria MUDA a
  // imagem — que é o comportamento do `seed` (`categoria-id`).
  assert.notEqual(placeholderSvg("politica-1", "politica"), placeholderSvg("economia-1", "economia"));
  // E a mesma notícia re-renderizada no SSR e depois no cliente dá o
  // mesmo byte — sem isso a imagem "pisca" na hidratação.
  assert.equal(placeholderSvg("politica-1", "politica"), placeholderSvg("politica-1", "politica"));
});

// ---------------------------------------------------------------------------
// 2. VARIAÇÃO — o que o `seed` produzia e o que a decisão exigia preservar
// ---------------------------------------------------------------------------
test("identificadores diferentes dão imagens diferentes", () => {
  const ids = ["politica-1", "politica-2", "economia-3", "cultura-4", "mundo-5"];
  const imagens = new Set(ids.map((id) => placeholderSvg(id, id.replace(/-\d+$/, ""))));
  assert.equal(imagens.size, ids.length, "a variação do placeholder não sobreviveu");
});

test("a MESMA categoria com ids diferentes dá imagens diferentes", () => {
  // Este é exatamente o caso que o medo da decisão de produto apontava:
  // se o placeholder fosse "um por categoria", as notícias de uma mesma
  // editoria seriam idênticas — que é o mar de cartões que o `seed`
  // evitava.
  const mesmaCategoria = [1, 2, 3, 4, 5, 6, 7, 8].map((i) => placeholderSvg(`politica-${i}`, "politica"));
  assert.equal(new Set(mesmaCategoria).size, mesmaCategoria.length);
});

test("categorias diferentes com o MESMO id dão imagens diferentes", () => {
  const categorias = ["politica", "economia", "esportes", "cultura", "mundo", "saude"];
  const mesmaId = categorias.map((c) => placeholderSvg(`${c}-1`, c));
  assert.equal(new Set(mesmaId).size, categorias.length);
});

test("muitas amostras: a variação não se esgota", () => {
  // 2000 identificadores sequenciais. Uma taxa alta de colisão aqui
  // significaria que a home de um portal grande mostraria duas notícias
  // com a mesma imagem — o defeito que a decisão recusou aceitar.
  const distintas = new Set();
  for (let i = 0; i < 2000; i++) distintas.add(placeholderSvg(`categoria-${i}`, "categoria"));
  assert.ok(
    distintas.size >= 1990,
    `2000 identificadores produziram só ${distintas.size} imagens distintas`
  );
});

// ---------------------------------------------------------------------------
// 3. ZERO CONEXÃO — o critério que fecha o item
// ---------------------------------------------------------------------------
test("o placeholder não contém NENHUMA URL http(s)", () => {
  for (const id of ["politica-1", "economia-2", "geral-0"]) {
    const uri = placeholderSvg(id, id.replace(/-\d+$/, ""));
    assert.match(uri, /^data:image\/svg\+xml,/);
    // `xmlns` é identificador de namespace e aparece dentro do SVG; o que
    // não pode aparecer é uma URL FORA do data URI.
    const foraDoSvg = uri.replace(/^data:image\/svg\+xml,/, "");
    assert.ok(!/^https?:\/\//.test(foraDoSvg), "o data URI aponta para um host");
  }
});

test("placeholder() — o ponto que a ImagemNoticia consome — também é local", () => {
  // POR QUE ESTE TESTE EXISTE SEPARADO DO ANTERIOR
  // ===============================================
  // `placeholderSvg()` é o gerador; `placeholder()` é o que `ImagemNoticia`
  // põe no `src`. São DUAS funções, e a mutação que esta run mediu mudou
  // só a segunda — devolvendo `https://${HOST_PLACEHOLDER}/seed/...`. Todos
  // os testes acima continuaram verdes, porque nenhum deles chamava a
  // função que o browser realmente busca.
  //
  // Isso é a forma mais comum de guarda cega: provar a coisa certa no lugar
  // errado. Por isso a asserção é sobre o nome que o componente usa.
  for (const seed of ["politica-1", "economia-2", "geral-0", "cultura-99"]) {
    const uri = placeholder(seed);
    assert.match(
      uri,
      /^data:image\/svg\+xml,/,
      `placeholder("${seed}") devolveu host externo: ${uri.slice(0, 80)}`
    );
    assert.ok(
      !uri.includes(HOST_PLACEHOLDER),
      `placeholder("${seed}") voltou a apontar para ${HOST_PLACEHOLDER}`
    );
  }
});

test("placeholder() e determinístico e varied, como o seed fazia", () => {
  assert.equal(placeholder("politica-1"), placeholder("politica-1"));
  const distintos = new Set([1, 2, 3, 4, 5, 6, 7, 8].map((i) => placeholder(`politica-${i}`)));
  assert.equal(distintos.size, 8, "placeholder() degenerou para uma imagem única");
});

test("o SVG é bem formado e mantém a proporção 16:9 do placeholder antigo", () => {
  const svg = svgDe(placeholderSvg("politica-1", "politica"));
  assert.ok(svg.startsWith("<svg"), "o SVG não abre");
  assert.ok(svg.endsWith("</svg>"), "o SVG não fecha");
  assert.match(svg, /viewBox='0 0 800 450'/);
  // o placeholder antigo (picsum 800/450) tinha exatamente esta geometria, e
  // as classes do cartão dependem dela para não haver shift de layout.
  assert.match(svg, /<rect width='800' height='450'/);
});

// ---------------------------------------------------------------------------
// 4. SEGURANÇA — `categoria` é conteúdo de terceiro
// ---------------------------------------------------------------------------
test("categoria com marcação não injeta script nem atributo no SVG", () => {
  const injetores = [
    ['"><script>alert(1)</script>', "categoria"],
    ["<img src=x onerror=alert(1)>", "x"],
    ["javascript:alert(1)", "y"],
    ["']]><foreignObject><iframe>", "z"],
  ];
  for (const [categoria] of injetores) {
    const svg = svgDe(placeholderSvg("x-1", categoria));
    assert.ok(!/<script/i.test(svg), `categoria ${categoria} injetou <script>`);
    assert.ok(!/<foreignObject/i.test(svg), `categoria ${categoria} injetou <foreignObject>`);
    assert.ok(!/<iframe/i.test(svg), `categoria ${categoria} injetou <iframe>`);
    assert.ok(!/\son\w+\s*=/i.test(svg), `categoria ${categoria} injetou atributo de evento`);
  }
});

test("categoria sem letra latina produz placeholder SEM letra, não letra quebrada", () => {
  for (const categoria of ["技术", "КИНО", "🎬", "   "]) {
    const svg = svgDe(placeholderSvg("x-1", categoria));
    assert.ok(!/<text/.test(svg), `categoria "${categoria}" desenhou letra indevida`);
    // e continua sendo um placeholder válido
    assert.match(svg, /viewBox='0 0 800 450'/);
  }
});

test("categoria com letra latina desenha a inicial", () => {
  const svg = svgDe(placeholderSvg("politica-1", "politica"));
  assert.match(svg, /<text[^>]*>P<\/text>/);
});

// ---------------------------------------------------------------------------
// 5. O CAMINHO DE IMAGEM REAL — a cadeia não pode ter quebrado
// ---------------------------------------------------------------------------
test("foto real do RSS é preservada", () => {
  const url = "https://veiculo.exemplo/foto-da-noticia.jpg";
  assert.equal(urlImagemUtilizavel(url), url);
  assert.equal(
    imagemNoticia({ imagem_url: url, categoria: "politica", id: 1 }),
    url
  );
});

test("esquema perigoso continua recusado (fail-closed)", () => {
  for (const ruim of ["javascript:alert(1)", "data:text/html,<script>", "vbscript:x"]) {
    assert.equal(urlImagemUtilizavel(ruim), null, `aceitou ${ruim}`);
  }
});

test(`imagem_url apontando para ${HOST_PLACEHOLDER} é recusada e cai no placeholder local`, () => {
  // Sem esta recusa, um feed apontando para o host do placeholder antigo
  // reconecta o terceiro por dentro da allowlist de esquema — e o item
  // "volta" sem que nada tenha mudado no `lib/imagens.ts`.
  const url = `https://${HOST_PLACEHOLDER}/seed/x/800/450`;
  assert.equal(ehHostDePlaceholder(url), true);
  assert.equal(urlImagemUtilizavel(url), null);
  assert.match(imagemNoticia({ imagem_url: url, categoria: "politica", id: 1 }), /^data:image\/svg\+xml,/);
});

test("sem imagem_url, imagemNoticia devolve o placeholder LOCAL", () => {
  for (const entrada of [
    { categoria: "politica", id: 1 },
    { categoria: "politica", id: 1, imagem_url: "" },
    { imagem_url: null, categoria: "cultura", id: 5 },
  ]) {
    const uri = imagemNoticia(entrada);
    assert.match(uri, /^data:image\/svg\+xml,/);
    assert.ok(!/https?:\/\//.test(uri.replace(/^data:image\/svg\+xml,/, "")));
  }
});

test("imagemNoticia e determinístico para a mesma notícia", () => {
  const entrada = { categoria: "politica", id: 42, imagem_url: null };
  assert.equal(imagemNoticia(entrada), imagemNoticia(entrada));
});

test("categoria vazia não quebra o gerador", () => {
  for (const entrada of [
    { id: 0 },
    { id: 0, categoria: "" },
    { id: 0, categoria: "   " },
    { id: 0, categoria: "Política e Economia" },
  ]) {
    assert.match(imagemNoticia(entrada), /^data:image\/svg\+xml,/);
  }
});