import type { FeedEntrada } from "./api";
import { obterTodasLeituras } from "./intent";

/**
 * Ranqueamento por gosto — o portal não destaca editorialmente nenhuma
 * notícia. A ordem de "Para você" nasce só dos sinais do próprio leitor:
 * interesses do onboarding + categorias que ele já leu. Transparente: cada
 * cartão pode exibir o motivo via `PorQueEstouVendoIsso`.
 */

export interface PerfilGosto {
  interesses: string[];
}

function normalizarLista(valores: string[]): string[] {
  return valores.map((v) => v.trim().toLowerCase()).filter(Boolean);
}

export function pontuarPorGosto(
  entrada: FeedEntrada,
  perfil: PerfilGosto,
  leituras: Record<string, number>
): number {
  let pontos = 0;
  const categoria = (entrada.categoria || "").toLowerCase();
  if (categoria && normalizarLista(perfil.interesses).includes(categoria)) pontos += 3;
  pontos += Math.min(leituras[entrada.categoria] ?? leituras[categoria] ?? 0, 5);
  if (entrada.urgente) pontos += 1;
  if (entrada.numero_fontes >= 3) pontos += 1;
  return pontos;
}

export function ordenarPorGosto(itens: FeedEntrada[], perfil: PerfilGosto): FeedEntrada[] {
  const leituras = obterTodasLeituras();
  return itens
    .map((entrada, indice) => ({ entrada, pontos: pontuarPorGosto(entrada, perfil, leituras), indice }))
    .sort((a, b) => b.pontos - a.pontos || a.indice - b.indice)
    .map((x) => x.entrada);
}

/** Há sinal suficiente para montar uma seção "Para você"? */
export function temSinalDeGosto(perfil: PerfilGosto): boolean {
  if (normalizarLista(perfil.interesses).length > 0) return true;
  return Object.values(obterTodasLeituras()).some((n) => n >= 2);
}

/** Categorias do leitor ordenadas por afinidade (para ordenar os blocos). */
export function categoriasPorAfinidade(perfil: PerfilGosto): string[] {
  const leituras = obterTodasLeituras();
  const mapa = new Map<string, number>();
  for (const interesse of normalizarLista(perfil.interesses)) {
    mapa.set(interesse, (mapa.get(interesse) ?? 0) + 3);
  }
  for (const [categoria, total] of Object.entries(leituras)) {
    const chave = categoria.toLowerCase();
    mapa.set(chave, (mapa.get(chave) ?? 0) + Math.min(total, 5));
  }
  return [...mapa.entries()].sort((a, b) => b[1] - a[1]).map(([categoria]) => categoria);
}
