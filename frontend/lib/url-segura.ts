/**
 * Allowlist de esquema para URL vinda de conteúdo externo (RSS, gateways,
 * webhooks). O vetor: `href={url_fonte_original}` com valor `javascript:`
 * executa no clique; `data:text/html,...` em `href` navega para uma página
 * controlada pelo atacante com a origem do portal.
 *
 * Aplicação (P0-10, eixo 1):
 * - `components/CoberturaCompleta.tsx`   (links "Abrir na fonte")
 * - `app/noticia/LeituraPremium.tsx`     (CTA e links de fonte)
 * - `app/admin/robos/page.tsx`           (links de URL de feed)
 *
 * REGRA: URL inválida ou de esquema não permitido vira `null` — o chamador
 * deve então renderizar texto puro. NUNCA devolver a string original como
 * fallback: isso seria o mesmo XSS com outro nome.
 */

/** Esquemas aceitos em links `href` que abrem navegação. */
const ESQUEMAS_LINK = new Set(["http:", "https:"]);

/** Esquemas aceitos em `src` de `<img>` (sem `javascript:`; SVG via data: é
 *  inerte em contexto de imagem — o browser não executa script em <img>). */
const ESQUEMAS_IMAGEM = new Set(["http:", "https:"]);

/**
 * Extrai o esquema de forma estrutural.
 *
 * NÃO usa `startsWith("https://")` nem comparação por substring: isso é
 * contornável com `https://x` + quebras de linha/tabulação que alguns
 * parsers normalizam (`java\tscript:` também funciona em alguns engines) e
 * com `JaVaScRiPt:` (case). Usamos o `URL` nativo, que faz a análise
 * completa, e comparamos o `protocol` normalizado.
 */
function esquemaDe(url: string): string | null {
  if (typeof url !== "string") return null;
  const bruto = url.trim();
  if (!bruto) return null;
  // `new URL` lança para entrada sem esquema ("evil.com/x") ou inválida.
  let analisado: URL;
  try {
    analisado = new URL(bruto);
  } catch {
    return null;
  }
  return analisado.protocol.toLowerCase();
}

/**
 * URL segura para `href`. Devolve `null` se o esquema não for http(s).
 *
 * Também rejeita credenciais embutidas (`https://user:pass@host`) — não
 * são XSS, mas appear em `href` com phishing e não têm uso legítimo num
 * portal de notícias.
 */
export function urlSeguraParaLink(url: string | null | undefined): string | null {
  if (typeof url !== "string") return null;
  const bruto = url.trim();
  if (!bruto) return null;
  if (!ESQUEMAS_LINK.has(esquemaDe(bruto) ?? "")) return null;
  try {
    const analisado = new URL(bruto);
    if (analisado.username || analisado.password) return null;
    return analisado.toString();
  } catch {
    return null;
  }
}

/**
 * URL segura para `src` de imagem. Mesma allowlist de esquema do link —
 * mantemos uma função separada (e não um parâmetro) para o ponto de uso
 * deixar explícito qual contexto está sendo validado.
 */
export function urlSeguraParaImagem(url: string | null | undefined): string | null {
  if (typeof url !== "string") return null;
  const bruto = url.trim();
  if (!bruto) return null;
  if (!ESQUEMAS_IMAGEM.has(esquemaDe(bruto) ?? "")) return null;
  return bruto;
}

/**
 * Hostname para exibição ("g1.globo.com"). Devolve `""` quando a URL é
 * inválida — nunca o texto cru, que exibiria `javascript:alert(1)` como
 * se fosse um domínio.
 */
export function hostnameSeguro(url: string | null | undefined): string {
  const seguro = urlSeguraParaLink(url);
  if (!seguro) return "";
  try {
    return new URL(seguro).hostname;
  } catch {
    return "";
  }
}
