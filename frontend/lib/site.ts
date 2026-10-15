/**
 * Constantes de identidade do site usadas por SEO/dados estruturados
 * (implementation-contract.md run 20260903-1134-seo-lgpd-design-system,
 * escopo A) — centralizadas aqui para não duplicar nome/descrição/URL em
 * cada `generateMetadata`/JSON-LD.
 */

export const SITE_NAME = "Portal de Notícias";

export const SITE_DESCRIPTION =
  "Toda a informação que importa, organizada em um só lugar — cobertura agregada de múltiplas fontes, com rastreabilidade de origem.";

// URL pública do frontend — usada para montar links absolutos (canonical,
// Open Graph, JSON-LD, sitemap, RSS). Sem valor real de produção definido
// ainda, então usa o mesmo padrão de fallback local já usado em
// `lib/api.ts` (NEXT_PUBLIC_API_BASE_URL).
export const SITE_URL = (process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000").replace(/\/$/, "");

// Imagem padrão usada quando um conteúdo não tem imagem própria (ex.:
// NewsItem não tem campo de imagem no modelo atual — "lacuna de conteúdo"
// registrada, não corrigida aqui por estar fora de escopo — Não-objetivos:
// multimídia).
// ATENÇÃO: o arquivo `og-padrao.svg` NÃO EXISTE no projeto hoje — a pasta
// `frontend/public/` nem existe (confirmado por busca no repositório, não é
// suposição). Esta constante é usada hoje só nos dados estruturados
// (JSON-LD, `lib/schema.ts`: `organizationJsonLd`/`newsArticleJsonLd`), que
// portanto também referenciam um caminho inexistente; ela NÃO está ligada
// ao `openGraph` do layout raiz, então nenhuma página emite `og:image`.
// Além disso, mesmo que o arquivo existisse, SVG não é um formato aceito
// como `og:image` pelos principais consumidores (Facebook/WhatsApp/
// LinkedIn exigem PNG/JPG). É necessário produzir um asset de design real
// (PNG/JPG, proporção 1200×630), publicá-lo em `frontend/public/` e então
// trocar esta constante para apontar para ele e adicionar
// `images: [IMAGEM_OG_PADRAO]` ao `openGraph` em `frontend/app/layout.tsx`.
export const IMAGEM_OG_PADRAO = `${SITE_URL}/og-padrao.svg`;
