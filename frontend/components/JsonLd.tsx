/**
 * Renderiza um objeto de dados estruturados schema.org (ver `lib/schema.ts`)
 * como `<script type="application/ld+json">`, gerado inteiramente
 * server-side (nenhum estado de cliente, nenhum round-trip extra além do já
 * necessário para montar a página — implementation-contract.md run
 * 20260903-1134-seo-lgpd-design-system, restrição de performance).
 *
 * `JSON.stringify` sozinho não escapa `</script>` dentro de strings de
 * conteúdo (ex.: um título de notícia contendo literalmente esse texto),
 * o que fecharia a tag prematuramente e quebraria o HTML — a troca abaixo
 * neutraliza isso sem alterar o JSON-LD resultante para leitores de dados
 * estruturados.
 */
export default function JsonLd({ data }: { data: object }) {
  const json = JSON.stringify(data).replace(/</g, "\\u003c");
  return (
    // eslint-disable-next-line react/no-danger
    <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: json }} />
  );
}
