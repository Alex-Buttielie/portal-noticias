/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Produz `.next/standalone` — um servidor Node self-contido com só as
  // dependências realmente usadas em runtime, em vez de copiar
  // `node_modules` inteiro (~centenas de MB) para dentro da imagem Docker.
  // Reduz drasticamente o tamanho/tempo de build da imagem de produção
  // (ver frontend/Dockerfile) — importante numa VPS com CPU/disco
  // compartilhados entre vários serviços.
  output: "standalone",
};

module.exports = nextConfig;
