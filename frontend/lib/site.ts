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
// NewsItem não tem campo de imagem no modelo atual — ver
// implementation-history.md desta run, "lacuna de conteúdo" registrada,
// não corrigida aqui por estar fora de escopo — Não-objetivos: multimídia).
// Placeholder de rascunho: precisa ser substituída por um asset visual real
// desenhado antes de produção.
export const IMAGEM_OG_PADRAO = `${SITE_URL}/og-padrao.svg`;
