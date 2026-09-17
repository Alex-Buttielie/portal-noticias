export function categoriaImagem(categoria: string): string {
  const s = (categoria || "geral").toLowerCase().trim().replace(/\s+/g, "-") || "geral";
  return `https://picsum.photos/seed/${encodeURIComponent(s)}/800/450`;
}
export function imagemNoticia(entrada: { categoria: string; id: string | number; titulo: string }): string {
  const cat = (entrada.categoria || "geral").toLowerCase().trim().replace(/\s+/g, "-") || "geral";
  const id = String(entrada.id ?? "0");
  return `https://picsum.photos/seed/${encodeURIComponent(`${cat}-${id}`)}/800/450`;
}
export const placeholderBlur = "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7";
