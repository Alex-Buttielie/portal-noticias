export function categoriaImagem(categoria: string): string {
  const s = (categoria || "geral").toLowerCase().trim().replace(/\s+/g, "-") || "geral";
  return `https://picsum.photos/seed/${encodeURIComponent(s)}/800/450`;
}
export function imagemNoticia(entrada: { imagem_url?: string | null; categoria: string; id: string | number; titulo?: string }): string {
  const real = (entrada.imagem_url || "").trim();
  if (real) return real;
  const cat = (entrada.categoria || "geral").toLowerCase().trim().replace(/\s+/g, "-") || "geral";
  const id = String(entrada.id ?? "0");
  return `https://picsum.photos/seed/${encodeURIComponent(`${cat}-${id}`)}/800/450`;
}
export function temImagemReal(entrada: { imagem_url?: string | null }): boolean {
  return !!((entrada.imagem_url || "").trim());
}
export const placeholderBlur = "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7";

/** Tamanhos mobile-first do placeholder picsum (evita baixar 800px no 4G). */
export function picsum(seed: string, w = 800, h = 450): string {
  return `https://picsum.photos/seed/${encodeURIComponent(seed)}/${w}/${h}`;
}

/** srcSet responsivo — só faz sentido para URLs picsum (padrão /seed/s/W/H). */
export function srcSetPicsum(seed: string): string {
  return [400, 640, 800]
    .map((w) => `${picsum(seed, w, Math.round((w * 9) / 16))} ${w}w`)
    .join(", ");
}

export function ehPicsum(url: string): boolean {
  return /(^|\/\/)picsum\.photos\//.test(url || "");
}

/** Extrai a seed de URLs picsum para reaproveitar no srcSet/fallback. */
export function seedDePicsum(url: string): string | null {
  const m = (url || "").match(/picsum\.photos\/seed\/([^/]+)/);
  return m ? decodeURIComponent(m[1]) : null;
}
