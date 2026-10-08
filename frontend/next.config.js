/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: "standalone",
  // Sem isso o Next devolve 308 para /api/feed/ -> /api/feed ANTES do
  // handler em app/api/[...path]/route.ts ser executado (trailing slash
  // normalization). O proxy perderia a barra final e cairia num loop
  // 308 (Next) <-> 301 (Django APPEND_SLASH).
  skipTrailingSlashRedirect: true,
  // Redirects permanentes de caminhos que NUNCA existiram como página.
  //
  // MEDIDO em 2026-10-08 nos logs de acesso de DEV e de PROD: 2 requisições
  // por dia de `GET /privacidade/cookies` e 2 de `GET /privacidade/termos`,
  // todas com `_rsc=` (prefetch do App Router) e TODAS respondendo 404.
  //
  // Quem gerava essas requisições era o próprio portal:
  // `components/BannerConsentimentoCookies.tsx:24` e `components/Rodape.tsx:37-38`
  // apontavam para `/privacidade/cookies` e `/privacidade/termos`, mas as
  // rotas que existem são `app/cookies/page.tsx` e `app/termos/page.tsx` — ou
  // seja, `/cookies` e `/termos`.
  //
  // Por que isso é bug e não detalhe: o link quebrado estava no BANNER DE
  // CONSENTIMENTO DE COOKIES, cujo texto diz "Veja nossa política de cookies".
  // A página de consentimento da LGPD apontava para um 404.
  //
  // `/paginas/sobre` é o outro caso, e é mais grave que um 404: a rota
  // `app/paginas/[slug]/page.tsx` fabricava conteúdo quando o slug não
  // existia (violação do P0-08) e devolvia HTTP 200 com "Conteúdo editorial
  // para sobre em preparação". O rodapé linkava "Sobre" para lá, enquanto a
  // rota real `/sobre` (estática, com conteúdo) existia e respondia 200.
  //
  // Redirect e não trocar os links: além de parar de gerar o erro, conserta o
  // que JÁ FOI SALVO ou COMPARTILHADO por alguém. Um link trocado deixa de
  // funcionar no instante da troca; o 308 mantém o caminho antigo vivo.
  // `permanent: true` = 308.
  async redirects() {
    return [
      { source: "/privacidade/cookies", destination: "/cookies", permanent: true },
      { source: "/privacidade/termos", destination: "/termos", permanent: true },
      { source: "/paginas/sobre", destination: "/sobre", permanent: true },
      { source: "/paginas/termos", destination: "/termos", permanent: true },
    ];
  },
};

module.exports = nextConfig;
