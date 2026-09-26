/**
 * Provas do sanitizador de HTML editorial (eixo XSS) e da allowlist de URL.
 *
 * O que estes testes provam:
 *  - Que marcação fora da allowlist é removida e o TEXTO interno
 *    preservado (o default é "não renderizar", não "não bloquear").
 *  - Que vetores clássicos de XSS não sobrevivem: `<script>`, handlers
 *    `on*`, `javascript:`, `<iframe>`, `<svg onload>`, `<object>`,
 *    `<style>`, `data:text/html`, smuggling de tag em atributo.
 *  - Que a allowlist de URL rejeita `javascript:`, `data:`, `vbscript:`,
 *    credenciais embutidas e variações com whitespace/controle, e aceita
 *    `http`/`https`/`mailto` e relativas.
 *
 * O que NÃO provam: que o sanitizador seja equivalente a DOMPurify. Ele é
 * deliberadamente conservador e baseado em tokenização por regex
 * (limitação registrada em `lib/sanitizar-html.ts`); a fronteira primária
 * é o sanitizador Python no backend, que usa `html.parser` de verdade.
 */
import test from "node:test";
import assert from "node:assert/strict";

import "./hooks.mjs";
import { sanitizarHtmlEditorial } from "../lib/sanitizar-html.ts";
import { urlSeguraParaLink, urlSeguraParaImagem, hostnameSeguro } from "../lib/url-segura.ts";

test("remove a tag mas preserva o texto de marcação não permitida", () => {
  assert.equal(
    sanitizarHtmlEditorial("<p>Olá <img src=x onerror=alert(1)> mundo</p>"),
    "<p>Olá  mundo</p>",
  );
  assert.equal(
    sanitizarHtmlEditorial("<form><input name=a><b>texto</b></form>"),
    "<b>texto</b>",
  );
  assert.equal(sanitizarHtmlEditorial("<marquee>passa</marquee>"), "passa");
});

test("script e conteúdo perigoso são eliminados por inteiro", () => {
  // Elemento `script` nunca sobrevive; o texto-fonte pode ficar como
  // text node inerte (regra "texto é sempre preservado").
  for (const entrada of [
    "<script>alert(1)</script>",
    "<p>a</p><script>alert(1)</script><p>b</p>",
    "<style>body{display:none}</style>x",
    "<svg><script>alert(1)</script></svg>x",
    "<scr" + "ipt>alert(1)</scr" + "ipt>",
    "<script><script>alert(1)</script></script>ok",
  ]) {
    const saida = sanitizarHtmlEditorial(entrada);
    assert.equal(/<\s*script/i.test(saida), false, `script sobreviveu: ${saida}`);
    assert.equal(/<\s*style/i.test(saida), false, `style sobreviveu: ${saida}`);
  }
  // `iframe`/`object` não têm tag de fechamento obrigatória no input
  // malformado e o conteúdo é descartado junto.
  assert.equal(sanitizarHtmlEditorial("<iframe src=//evil.tld></iframe>x"), "x");
  assert.equal(sanitizarHtmlEditorial("<object data=x.swf></object>x"), "x");
  // Script SEM fechamento é o caso mais perigoso (não dá para saber onde
  // termina): o consumo vai até o fim do documento, que é fail-closed.
  assert.equal(sanitizarHtmlEditorial("<script>alert(1)"), "");
});

test("handlers on* nunca sobrevivem, em nenhuma tag permitida", () => {
  for (const payload of [
    "<p onclick=\"alert(1)\">x</p>",
    "<p ONMOUSEOVER=alert(1)>x</p>",
    "<a href=\"https://ok.tld\" onerror=\"alert(1)\">x</a>",
    "<b onfocus=alert(1) autofocus>x</b>",
  ]) {
    const saida = sanitizarHtmlEditorial(payload);
    assert.equal(
      atributosDaPrimeiraTag(saida).some(([n]) => n.startsWith("on")),
      false,
      `handler sobreviveu como atributo: ${saida}`,
    );
  }
  assert.equal(sanitizarHtmlEditorial("<p onclick=\"alert(1)\">x</p>"), "<p>x</p>");
});

test("href perigoso é removido, href legítimo é preservado", () => {
  // Esquemas fora da allowlist: o atributo inteiro some.
  assert.equal(sanitizarHtmlEditorial('<a href="javascript:alert(1)">x</a>'), "<a>x</a>");
  assert.equal(sanitizarHtmlEditorial('<a href="JaVaScRiPt:alert(1)">x</a>'), "<a>x</a>");
  assert.equal(sanitizarHtmlEditorial('<a href=" javascript:alert(1)">x</a>'), "<a>x</a>");
  assert.equal(
    sanitizarHtmlEditorial('<a href="java\tscript:alert(1)">x</a>'),
    "<a>x</a>",
    "whitespace/controle dentro do esquema deve neutralizar a URL",
  );
  // `data:text/html,<script>...` — o `href` é rejeitado e o `<script>`
  // interno também é eliminado (pela neutralização de conteúdo perigoso).
  const data = sanitizarHtmlEditorial('<a href="data:text/html,<script>alert(1)</script>">x</a>');
  assert.equal(/<\s*script/i.test(data), false, data);
  assert.equal(/data:text\/html/i.test(data), false, data);
  // URLs legítimas preservadas (com normalização canônica do `new URL`).
  assert.equal(
    sanitizarHtmlEditorial('<a href="https://exemplo.com/a?b=1&amp;c=2">x</a>'),
    '<a href="https://exemplo.com/a?b=1&amp;c=2">x</a>',
  );
  assert.equal(sanitizarHtmlEditorial('<a href="/politica">x</a>'), '<a href="/politica">x</a>');
  assert.equal(
    sanitizarHtmlEditorial('<a href="mailto:ola@exemplo.com">x</a>'),
    '<a href="mailto:ola@exemplo.com">x</a>',
  );
  // Credenciais embutidas (phishing) — recusadas.
  assert.equal(sanitizarHtmlEditorial('<a href="https://u:p@exemplo.com">x</a>'), "<a>x</a>");
});

test("link com target=_blank ganha rel=noopener (reverse tabnabbing)", () => {
  const saida = sanitizarHtmlEditorial('<a href="https://exemplo.com" target="_blank">x</a>');
  assert.match(saida, /rel="noopener noreferrer nofollow"/);
  // `_top`/`_self`/lixo não são normalizados para `_blank`: o atributo
  // simplesmente some (não ampliamos o que o autor pediu).
  assert.equal(
    sanitizarHtmlEditorial('<a href="https://exemplo.com" target="_top">x</a>'),
    '<a href="https://exemplo.com/">x</a>',
  );
});

test("style é sempre removido (CSS injection / clickjacking)", () => {
  assert.equal(
    sanitizarHtmlEditorial('<p style="position:fixed;inset:0;background:url(//evil.tld)">x</p>'),
    "<p>x</p>",
  );
});

test("texto é escapado e não pode virar marcação", () => {
  assert.equal(sanitizarHtmlEditorial("1 < 2 e 3 > 2"), "1 &lt; 2 e 3 &gt; 2");
  assert.equal(sanitizarHtmlEditorial("Tom &amp; Jerry"), "Tom &amp; Jerry");
  // Entidade já válida é preservada (round-trip de texto, sem duplo escape).
  assert.equal(sanitizarHtmlEditorial("&lt;script&gt;"), "&lt;script&gt;");
  // Entidade TRUNCADA/incompleta não é reinterpretada: escapa o `&`.
  assert.equal(sanitizarHtmlEditorial("&lt"), "&amp;lt");
  assert.equal(sanitizarHtmlEditorial("&#xZZ;"), "&amp;#xZZ;");
});

test("payload do enunciado: `</script><script>alert(1)</script>` não sobrevive", () => {
  const saida = sanitizarHtmlEditorial("<p>x</p></script><script>alert(1)</script>");
  // O ELEMENTO perigoso não sobrevive — é isto que impede execução.
  assert.equal(/<\s*script/i.test(saida), false, saida);
  assert.equal(/onerror|onload/i.test(saida), false, saida);
  // O texto "alert(1)" fica como text node inerte, que é a regra
  // documentada do módulo ("texto é sempre preservado"). Ele NÃO é
  // executável: só aparece se o navegador o renderizar como texto.
  assert.equal(saida, "<p>x</p>alert(1)");
});

test("payload do enunciado: `\"><img src=x onerror=alert(1)>` não sobrevive", () => {
  const saida = sanitizarHtmlEditorial('"><img src=x onerror=alert(1)>');
  assert.equal(/<img/i.test(saida), false, saida);
  assert.equal(/onerror/i.test(saida), false, saida);
  assert.equal(saida, "&quot;&gt;");
});

test("smuggling de tag dentro de atributo é neutralizado", () => {
  // O `title` contém `onclick=` como TEXTO. O que importa não é a
  // substring: é se sobrou um ATRIBUTO chamado `onclick`. Por isso este
  // teste re-parseia a saída e olha os NOMES dos atributos.
  const saida = sanitizarHtmlEditorial(
    '<a href="https://ok.tld" title="a&quot; onclick=&quot;alert(1)">x</a>',
  );
  const nomes = atributosDaPrimeiraTag(saida).map(([n]) => n);
  assert.deepEqual(nomes.sort(), ["href", "title"], `atributos inesperados: ${saida}`);
  assert.equal(nomes.includes("onclick"), false, `onclick virou atributo: ${saida}`);
  // E a saída realmente não quebra o atributo: o `&quot;` mantém a
  // integrity da citação, então o valor do title é texto inerte.
  assert.match(saida, /title="a&quot; onclick=&quot;alert\(1\)"/);
});

/**
 * Re-parseia a PRIMEIRA tag do HTML sanitizado e devolve
 * `[[nome, valor], ...]`. Parser propositalmente simples, mas fiel ao
 * suficiente para a única coisa que queremos observar aqui: quais
 * NOMES de atributo existem de fato (e não quais strings aparecem).
 */
function atributosDaPrimeiraTag(html) {
  const abre = html.search(/<[a-zA-Z]/);
  if (abre === -1) return [];
  const inicio = html.indexOf(">", abre);
  const bruto = html.slice(html.slice(abre).search(/[a-zA-Z]/), inicio);
  const saida = [];
  const REGEX = /([a-zA-Z_:][a-zA-Z0-9_.:-]*)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'>=`]+)))?/g;
  let m;
  let primeiro = true;
  while ((m = REGEX.exec(bruto)) !== null) {
    if (primeiro) {
      primeiro = false; // o primeiro match é o NOME da tag, não um atributo
      continue;
    }
    saida.push([(m[1] ?? "").toLowerCase(), m[2] ?? m[3] ?? m[4] ?? null]);
  }
  return saida;
}

test("conteúdo legítimo é preservado (sem regressão de SEO/editorial)", () => {
  const entrada =
    '<p>Reforma <strong>tributária</strong> em <em>fase</em> de regulamentação.</p>' +
    "<ul><li>Item 1</li><li>Item 2</li></ul>";
  assert.equal(sanitizarHtmlEditorial(entrada), entrada);
});

test("entrada não-string vira string vazia (nunca 'undefined')", () => {
  assert.equal(sanitizarHtmlEditorial(null), "");
  assert.equal(sanitizarHtmlEditorial(undefined), "");
  assert.equal(sanitizarHtmlEditorial(42), "");
  assert.equal(sanitizarHtmlEditorial({}), "");
  assert.equal(sanitizarHtmlEditorial(""), "");
});

// -------------------------------------------------------------------------
// Allowlist de URL
// -------------------------------------------------------------------------

test("urlSeguraParaLink aceita http/https e mailto; recusa o resto", () => {
  assert.ok(urlSeguraParaLink("https://g1.globo.com/politica"));
  assert.ok(urlSeguraParaLink("http://exemplo.com"));
  assert.equal(urlSeguraParaLink("javascript:alert(1)"), null);
  assert.equal(urlSeguraParaLink("JaVaScRiPt:alert(1)"), null);
  assert.equal(urlSeguraParaLink(" javascript:alert(1)"), null);
  assert.equal(urlSeguraParaLink("java\tscript:alert(1)"), null);
  assert.equal(urlSeguraParaLink("java\nscript:alert(1)"), null);
  assert.equal(urlSeguraParaLink("data:text/html,<script>alert(1)</script>"), null);
  assert.equal(urlSeguraParaLink("vbscript:msgbox(1)"), null);
  assert.equal(urlSeguraParaLink("file:///etc/passwd"), null);
  assert.equal(urlSeguraParaLink("gopher://exemplo.com"), null);
  // Sem esquema é relativo: o browser resolveria contra a origem, mas como
  // `href` de fonte externa o uso esperado é absoluto — devolvemos null.
  assert.equal(urlSeguraParaLink("g1.globo.com/politica"), null);
  // Credenciais embutidas (phishing, não XSS) —同样 recusado.
  assert.equal(urlSeguraParaLink("https://usuario:senha@exemplo.com"), null);
  assert.equal(urlSeguraParaLink(""), null);
  assert.equal(urlSeguraParaLink(null), null);
  assert.equal(urlSeguraParaLink(undefined), null);
});

test("urlSeguraParaImagem recusa javascript: e data:", () => {
  assert.ok(urlSeguraParaImagem("https://exemplo.com/a.jpg"));
  assert.equal(urlSeguraParaImagem("javascript:alert(1)"), null);
  assert.equal(urlSeguraParaImagem("data:image/svg+xml,<svg onload=alert(1)>"), null);
  assert.equal(urlSeguraParaImagem(null), null);
});

test("hostnameSeguro nunca expõe o esquema cru", () => {
  assert.equal(hostnameSeguro("https://g1.globo.com/politica"), "g1.globo.com");
  assert.equal(hostnameSeguro("javascript:alert(1)"), "");
  assert.equal(hostnameSeguro("lixo"), "");
});
