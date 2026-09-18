/**
 * FRENTE 3 — camada de serviço do frontend para recomendação/busca.
 *
 * Transporte + formatação apenas: ranking, score, seções, autocomplete e
 * correção vêm prontos do backend (`feed/recomendacao.py`, `feed/busca.py`).
 * Nenhum peso, ordenação por afinidade ou decisão editorial vive aqui —
 * o que era client-side antes (`ordenarPorGosto` etc.) continua existindo
 * como fallback offline, mas com dado real o backend manda.
 *
 * Telemetria (view/click/read/search/search_result_click) passa por
 * `lib/analytics.ts` (FRENTE 6) → `POST /api/metricas/eventos/` → modelos
 * `feed.*` — não duplicar pipeline aqui.
 */

import {
  buscarNoticias,
  obterCobertura,
  obterDestaquesDia,
  obterHomeSecoes,
  type BuscaResposta,
  type CoberturaCompleta,
  type EntradaRanqueda,
  type FeedEntrada,
  type NomeSecaoHome,
  type SecoesHome,
} from "@/lib/api";
import { trackSearchClick } from "@/lib/analytics";

export const ORDEM_SECOES: NomeSecaoHome[] = [
  "manchetes",
  "curadoria",
  "para_voce",
  "populares",
  "tendencia",
  "recentes",
];

export const ROTULO_SECAO: Record<NomeSecaoHome, string> = {
  manchetes: "Manchetes",
  curadoria: "Curadoria",
  para_voce: "Para você",
  populares: "Mais lidas",
  tendencia: "Em tendência",
  recentes: "Recentes",
};

/** Achata as seções preservando prioridade (sem repetir entradas). */
export function achatarSecoes(secoes: SecoesHome): FeedEntrada[] {
  const vistas = new Set<string>();
  const saida: FeedEntrada[] = [];
  for (const nome of ORDEM_SECOES) {
    for (const entrada of secoes[nome] || []) {
      const chave = `${entrada.tipo}-${entrada.id}`;
      if (!vistas.has(chave)) {
        vistas.add(chave);
        saida.push(entrada);
      }
    }
  }
  return saida;
}

export async function carregarHome(limite = 6): Promise<{
  secoes: SecoesHome | null;
  feed: FeedEntrada[];
  destaques: EntradaRanqueda[];
}> {
  try {
    const [home, destaques] = await Promise.all([
      obterHomeSecoes({ limite }),
      obterDestaquesDia({ limite: 5 }).catch(() => [] as EntradaRanqueda[]),
    ]);
    return { secoes: home, feed: achatarSecoes(home), destaques };
  } catch {
    return { secoes: null, feed: [], destaques: [] };
  }
}

export async function executarBusca(q: string, filtros: Record<string, string> = {}): Promise<BuscaResposta | null> {
  const termo = q.trim();
  if (!termo) return null;
  try {
    return await buscarNoticias({ q: termo, ...filtros, limite: 20 });
  } catch {
    return null;
  }
}

/** Clique em resultado de busca → evento search_result_click (métricas + recomendação). */
export function clicarResultadoBusca(
  entrada: { tipo: "cluster" | "item"; id: number },
  termo: string
): void {
  try {
    trackSearchClick(entrada.tipo, entrada.id, termo);
  } catch {
    /* telemetria nunca quebra a navegação */
  }
}

export async function carregarCobertura(
  tipo: "cluster" | "item",
  id: number | string
): Promise<CoberturaCompleta | null> {
  try {
    return await obterCobertura(tipo, id);
  } catch {
    return null;
  }
}
