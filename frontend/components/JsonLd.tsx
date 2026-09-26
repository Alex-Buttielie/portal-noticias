/**
 * Componente único de JSON-LD. Todo `<script type="application/ld+json">`
 * do portal passa por aqui — não há outro jeito de emitir dados
 * estruturados no frontend.
 *
 * Server component (sem "use client"): roda só no servidor, não adiciona
 * nenhum byte ao bundle do cliente e o corpo é escrito uma única vez no
 * HTML estático.
 *
 * `dangerouslySetInnerHTML` continua sendo necessário (e é seguro aqui)
 * porque, dentro de um raw text element, escaping de entidade HTML não é
 * decodificado — ver a justificativa completa e a medição comparativa em
 * `lib/jsonld.ts`.
 *
 * Este arquivo é intencionalmente um adaptador SEM lógica: todo o
 * escape/validação vive em `lib/jsonld.ts` (`propsJsonLd`), que é o que
 * os testes exercitam diretamente em Node. Se algum dia este arquivo
 * ganhar um `if`, o teste deixa de cobrir a página inteira — daí a
 * separação.
 */

import { propsJsonLd } from "@/lib/jsonld";

export function JsonLd({ dados }: { dados: unknown }) {
  const props = propsJsonLd(dados);
  if (!props) return null;
  return <script {...props} />;
}

export default JsonLd;
