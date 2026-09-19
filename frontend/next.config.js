/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Produz `.next/standalone` ÔÇö um servidor Node self-contido com s├│ as
  // depend├¬ncias realmente usadas em runtime, em vez de copiar
  // `node_modules` inteiro (~centenas de MB) para dentro da imagem Docker.
  // Reduz drasticamente o tamanho/tempo de build da imagem de produ├º├úo
  // (ver frontend/Dockerfile) ÔÇö importante numa VPS com CPU/disco
  // compartilhados entre v├írios servi├ºos.
  output: "standalone",
  // Proxy mesma-origem `/api/*` -> API Django local. O destino é lido em
  // RUNTIME (env do `next start`, nunca bakeado no build): o navegador chama
  // `/api/...` na mesma origem e o Next repassa a `127.0.0.1:<API_PORT>`.
  // Funciona via domínio, IP ou localhost sem rebuild (incidente 2026-09-19:
  // acesso direto por IP:porta não passa pelo Nginx, então o proxy precisa
  // morar no próprio Next). `/api/*` é livre: o app não tem route handlers
  // próprios nesse namespace. Default = Django local (`runserver :8000`).
  async rewrites() {
    const apiInterna = (process.env.API_INTERNAL_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
    return [{ source: "/api/:path*", destination: `${apiInterna}/api/:path*` }];
  },
};

module.exports = nextConfig;
