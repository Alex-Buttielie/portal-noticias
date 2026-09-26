/**
 * Serialização segura de JSON-LD para `<script type="application/ld+json">`.
 *
 * -------------------------------------------------------------------------
 * POR QUE ESTE MÓDULO EXISTE (decisão medida, nãoPreference de estilo)
 * -------------------------------------------------------------------------
 * O padrão anterior do projeto era
 * `dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}`. Medimos o
 * que cada alternativa realmente emite (Node puro, `react-dom/server`) e a
 * medição é o que motivou a escolha:
 *
 *   entrada maliciosa:  headline = `</script><script>alert(1)</script>`
 *
 *   A) `<script type="application/ld+json">{JSON.stringify(x)}</script>`
 *      -> <script type="application/ld+json">{&quot;headline&quot;:&lt;/script&gt;…}
 *      Seguro contra XSS, MAS QUEBRADO PARA CRAWLER. `<script>` é um
 *      *raw text element* na spec HTML: o conteúdo NÃO é decodificado de
 *      entidades. O crawler recebe literalmente `&quot;` e
 *      `JSON.parse` falha. Trocar XSS por SEO quebrado não é hardening,
 *      é troca de problema.
 *
 *   B) `dangerouslySetInnerHTML` + `JSON.stringify` (o padrão anterior)
 *      -> <script type="application/ld+json">{"headline":"</script>…}
 *      O `</script>` passa cru. O parser HTML termina o elemento aí e o
 *      resto vira MARCAÇÃO VIVA. XSS armazenado real, com o título vindo
 *      de RSS (fonte externa não confiável, ver `catalogo_noticias`).
 *
 *   C) O que este módulo faz: `dangerouslySetInnerHTML` + escape de
 *      contexto `<script>` preservando o JSON byte-exato.
 *
 * A escolha é (C) porque é a única que satisfaz as DUAS exigências do
 * requisito ao mesmo tempo: "válido para crawler" E "seguro".
 *
 * -------------------------------------------------------------------------
 * POR QUE O ESCAPE ESCOLHIDO
 * -------------------------------------------------------------------------
 * Trocamos apenas `<`, `>`, `&` e os separadores de linha U+2028/U+2029
 * pelos escapes Unicode `\uXXXX` do próprio JSON. Isso vale porque:
 *
 *  1. `\u003c` é um escape legal dentro de uma STRING JSON. O valor é
 *     idêntico depois do parse (round-trip exato, verificado em teste),
 *     então o crawler lê exatamente o mesmo objeto.
 *  2. O corpo emitido não contém NENHUM caractere `<`. Como um raw text
 *     element só é encerrado por `</script` (case-insensitive, WHATWG HTML
 *     §13.2.5.8), a ausência de `<` torna estruturalmente impossível o
 *     fechamento do elemento. É uma garantia de parsing, não um filtro de
 *     blacklist que se possa contornar com encoding criativo.
 *  3. U+2028/U+2029 são legais em JSON mas ilegais em string literal JS
 *     (pré-ES2019). Quebram parsers JSON estritos usados por crawlers.
 *
 * Não aplicamos o regex sobre o valor ANTES do `JSON.stringify` nem depois
 * de um segundo `stringify`: isso duplicaria barras invertidas. O escape é
 * aplicado UMA vez, direto sobre a saída do `JSON.stringify`.
 */

// Mapeamento caractere -> escape JSON. Intencionalmente incompleto: só os
// caracteres que importam no contexto `<script>` (ver docstring acima).
const ESCAPES_CONTEXTO_SCRIPT: Record<string, string> = {
  "<": "\\u003c",
  ">": "\\u003e",
  "&": "\\u0026",
  "\u2028": "\\u2028",
  "\u2029": "\\u2029",
};

const REGEX_ESCAPE = /[<>&\u2028\u2029]/g;

/**
 * Serializa `dados` para uso como corpo de `<script type="application/ld+json">`.
 *
 * - Nunca lança. Se a serialização falhar, devolve `""` e o chamador
 *   renderiza o `<script>` com corpo vazio: preferimos perder os dados
 *   estruturados de UMA página a derrubar o render (e a nunca emitir
 *   markup não escapado).
 * - A saída é garantidamente livre de `<`, `>` e `&` crus.
 */
export function serializarJsonLd(dados: unknown): string {
  let bruto: string | undefined;
  try {
    bruto = JSON.stringify(dados);
  } catch {
    // BigInt, referência circular, `toJSON` que lança: nada representável.
    return "";
  }
  if (typeof bruto !== "string") {
    // `JSON.stringify(undefined)` e funções devolvem `undefined` — não é JSON.
    return "";
  }
  return bruto.replace(REGEX_ESCAPE, (caractere) => ESCAPES_CONTEXTO_SCRIPT[caractere]);
}

/**
 * `true` quando a string é um corpo seguro para `application/ld+json`.
 * Usado pelos testes e por `propsJsonLd` para recusar conteúdo que, por
 * algum motivo, não passou por `serializarJsonLd`.
 */
export function corpoJsonLdSeguro(corpo: string): boolean {
  if (typeof corpo !== "string" || corpo.length === 0) return false;
  if (corpo.includes("<") || corpo.includes(">") || corpo.includes("&")) return false;
  try {
    JSON.parse(corpo);
  } catch {
    return false;
  }
  return true;
}

/**
 * Props do `<script type="application/ld+json">`, ou `null` para não
 * renderizar nada.
 *
 * Existe separado do componente de propósito: o componente
 * `components/JsonLd.tsx` é JSX (que o `node:test` não compila sem
 * transformer), mas toda a LÓGICA — escape, recusa de corpo inseguro,
 * JSON inválido — mora aqui e é testável em Node puro. O componente
 * passa a ser um adaptador de 4 linhas, sem decisão própria.
 */
export function propsJsonLd(
  dados: unknown,
): { type: string; dangerouslySetInnerHTML: { __html: string } } | null {
  const corpo = serializarJsonLd(dados);
  // Defesa em profundidade: `serializarJsonLd` já garante isso, mas se
  // alguém a trocar por `JSON.stringify` um dia, o componente ainda se
  // recusa a emitir markup não escapado.
  if (!corpoJsonLdSeguro(corpo)) return null;
  return { type: "application/ld+json", dangerouslySetInnerHTML: { __html: corpo } };
}
