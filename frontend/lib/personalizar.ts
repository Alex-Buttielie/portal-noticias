import { obterAfinidade, type FeedEntrada } from "./api";
import { obterTodasLeituras } from "./intent";
import { CATEGORIAS } from "./categorias";

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
  leituras: Record<string, number>,
  pesosExtra: Record<string, number> = {}
): number {
  let pontos = 0;
  const categoria = (entrada.categoria || "").toLowerCase();
  if (categoria && normalizarLista(perfil.interesses).includes(categoria)) pontos += 3;
  const leitura = leituras[entrada.categoria] ?? leituras[categoria] ?? 0;
  const extra = pesosExtra[entrada.categoria] ?? pesosExtra[categoria] ?? 0;
  pontos += Math.min(leitura + extra, 8);
  if (entrada.urgente) pontos += 1;
  if (entrada.numero_fontes >= 3) pontos += 1;
  return pontos;
}

/**
 * `pesosExtra`: afinidade adicional por categoria (slug em minúsculo) a
 * somar à leitura local — hoje alimentada pelo histórico de leitura da
 * conta + objetivo da assinatura Premium, vindos do backend
 * (`GET /api/feed/afinidade/`, ver `obterPesosPremium`). Opcional: sem
 * isso, o comportamento é idêntico ao anterior (só sinal local).
 */
export function ordenarPorGosto(
  itens: FeedEntrada[],
  perfil: PerfilGosto,
  pesosExtra: Record<string, number> = {}
): FeedEntrada[] {
  const leituras = obterTodasLeituras();
  return itens
    .map((entrada, indice) => ({ entrada, pontos: pontuarPorGosto(entrada, perfil, leituras, pesosExtra), indice }))
    .sort((a, b) => b.pontos - a.pontos || a.indice - b.indice)
    .map((x) => x.entrada);
}

/** Há sinal suficiente para montar uma seção "Para você"? */
export function temSinalDeGosto(perfil: PerfilGosto): boolean {
  if (normalizarLista(perfil.interesses).length > 0) return true;
  return Object.values(obterTodasLeituras()).some((n) => n >= 2);
}

/** Categorias do leitor ordenadas por afinidade (para ordenar os blocos). */
export function categoriasPorAfinidade(
  perfil: PerfilGosto,
  pesosExtra: Record<string, number> = {}
): string[] {
  const leituras = obterTodasLeituras();
  const mapa = new Map<string, number>();
  for (const interesse of normalizarLista(perfil.interesses)) {
    mapa.set(interesse, (mapa.get(interesse) ?? 0) + 3);
  }
  for (const [categoria, total] of Object.entries(leituras)) {
    const chave = categoria.toLowerCase();
    mapa.set(chave, (mapa.get(chave) ?? 0) + Math.min(total, 5));
  }
  for (const [categoria, peso] of Object.entries(pesosExtra)) {
    const chave = categoria.toLowerCase();
    mapa.set(chave, (mapa.get(chave) ?? 0) + peso);
  }
  return [...mapa.entries()].sort((a, b) => b[1] - a[1]).map(([categoria]) => categoria);
}

/**
 * Casa o objetivo da assinatura Premium (texto livre) com o vocabulário de
 * categorias que já existe no portal (`lib/categorias.ts`) — substring
 * simples, case-insensitive, contra slug/nome/termos de subcategoria.
 * Deliberadamente SEM IA: transparente e auditável (mesma filosofia do
 * resto do ranqueamento — ver docstring no topo deste arquivo).
 */
export function mapearObjetivoParaCategorias(objetivo: string): Record<string, number> {
  const texto = (objetivo || "").trim().toLowerCase();
  const pesos: Record<string, number> = {};
  if (!texto) return pesos;
  for (const cat of CATEGORIAS) {
    const termos = [cat.slug.toLowerCase(), cat.nome.toLowerCase(), ...cat.subcategorias.map((s) => s.termo.toLowerCase())];
    if (termos.some((termo) => termo && texto.includes(termo))) {
      pesos[cat.slug] = 4;
    }
  }
  return pesos;
}

/**
 * Afinidade por categoria vinda da conta (histórico de leitura persistido
 * no backend + objetivo da assinatura) — só para usuário Premium logado.
 * Nunca lança: sem token, sem Premium, ou qualquer falha de rede, devolve
 * `{}` e o chamador segue só com o sinal local (`obterTodasLeituras`),
 * sem quebrar o feed.
 */
export async function obterPesosPremium(token: string | null): Promise<Record<string, number>> {
  if (!token) return {};
  try {
    const resposta = await obterAfinidade(token);
    const doObjetivo = mapearObjetivoParaCategorias(resposta.objetivo_assinatura);
    const combinado: Record<string, number> = { ...resposta.categorias };
    for (const [categoria, peso] of Object.entries(doObjetivo)) {
      combinado[categoria] = (combinado[categoria] ?? 0) + peso;
    }
    return combinado;
  } catch {
    return {};
  }
}
