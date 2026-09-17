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
