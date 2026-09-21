/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: "standalone",
  // Sem isso o Next devolve 308 para /api/feed/ -> /api/feed ANTES do
  // handler em app/api/[...path]/route.ts ser executado (trailing slash
  // normalization). O proxy perderia a barra final e cairia num loop
  // 308 (Next) <-> 301 (Django APPEND_SLASH).
  skipTrailingSlashRedirect: true,
};

module.exports = nextConfig;
