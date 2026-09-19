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
  // (Sem `rewrites` para /api: o Next congela rewrites no build em
  // routes-manifest.json. O proxy mesma-origem vive em
  // `app/api/[...path]/route.ts`, que lê API_INTERNAL_URL por request.)
};

module.exports = nextConfig;
