/**
 * FRENTE 6 — Central de Inteligência: tracker de eventos comportamentais.
 *
 * Taxonomia completa (espelha `metricas/models.py::EventoSite` + roteamento
 * do `POST /api/metricas/eventos/` para `feed.InteracaoNoticia/EventoBusca`):
 * page_view, news_view, news_click, search, search_result_click,
 * category_view, category_click, author_view, columnist_view, share, save,
 * radar_view, location_permission, location_selected, home_section_view,
 * home_section_click, community_view, community_interaction.
 *
 * LGPD: NADA é enviado sem consentimento explícito de `analytics`
 * (`permiteCategoria("analytics")` em `cookie-consent.ts`). Localização só
 * vai junto quando o usuário permitiu/selecionou região. Sem IP, sem
 * user-agent bruto. `window.__portalTrack` expõe o tracker para qualquer
 * frente instrumentar declarativamente, sem importar este módulo.
 *
 * REDAÇÃO (run 20260925-1020-observabilidade, critério 28): `payload.path` era
 * preenchido com `location.pathname + location.search`, ou seja, a query string
 * COMPLETA ia para um evento de produto a cada `page_view`. Isso colocava
 * Things que o usuário digitou (termos de busca, e-mail em Invite, token de
 * convite) dentro de um evento analítico, com retenção de 12 meses no backend.
 * Agora o `path` é sempre só o pathname — query string e fragmento nunca saem
 * daqui, nem quando o chamador passa `path` explicitamente. O termo da busca
 * continua indo no campo `termo`/`query` do evento de busca, que é o contrato
 * de produto já existente e é redigido no backend.
 */

import { API_BASE_URL } from "./api";
import { permiteCategoria } from "./cookie-consent";
import { caminhoSeguro } from "./observabilidade";

export const TIPOS_EVENTO = [
  "page_view",
  "news_view",
  "news_click",
  "search",
  "search_result_click",
  "category_view",
  "category_click",
  "author_view",
  "columnist_view",
  "share",
  "save",
  "radar_view",
  "location_permission",
  "location_selected",
  "home_section_view",
  "home_section_click",
  "community_view",
  "community_interaction",
] as const;

export type TipoEvento = (typeof TIPOS_EVENTO)[number];

export interface PayloadEvento {
  tipo: TipoEvento;
  path?: string;
  sessao?: string;
  entry_tipo?: "item" | "cluster";
  entry_id?: number;
  categoria?: string;
  autor_ref?: string;
  autor?: string;
  termo?: string;
  query?: string;
  resultados?: number;
  filtros?: Record<string, unknown>;
  secao_home?: string;
  secao?: string;
  origem?: string;
  dispositivo?: string;
  pais?: string;
  estado?: string;
  cidade?: string;
  regiao?: string;
  tempo_permanencia_seg?: number;
  tempo_leitura_seg?: number;
  scroll_max_pct?: number;
  extra?: Record<string, unknown>;
}

const CHAVE_SESSAO = "portal_noticias_sessao_analytics";

export function obterSessao(): string {
  if (typeof window === "undefined") return "";
  try {
    let s = window.sessionStorage.getItem(CHAVE_SESSAO);
    if (!s) {
      s = `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
      window.sessionStorage.setItem(CHAVE_SESSAO, s);
    }
    return s;
  } catch {
    return "";
  }
}

export function detectarDispositivo(): string {
  if (typeof window === "undefined") return "";
  try {
    const ua = window.navigator.userAgent || "";
    if (/tablet|ipad/i.test(ua)) return "tablet";
    if (/mobi|android|iphone/i.test(ua)) return "mobile";
    return "desktop";
  } catch {
    return "";
  }
}

/** Origem do tráfego: busca/social/direto/referência/campanha. */
export function detectarOrigem(): string {
  if (typeof window === "undefined") return "";
  try {
    const params = new URLSearchParams(window.location.search);
    const utm = (params.get("utm_source") || params.get("utm_medium") || "").toLowerCase();
    if (utm) return "campanha";
    const ref = window.document.referrer;
    if (!ref) return "direto";
    const host = new URL(ref).hostname.toLowerCase();
    if (host === window.location.hostname.toLowerCase()) return "";
    if (/google|bing|duckduckgo|yahoo|ecosia|brave/.test(host)) return "busca";
    if (/facebook|instagram|twitter|x\.com|tiktok|linkedin|whatsapp|telegram|youtube/.test(host)) {
      return "social";
    }
    return "referencia";
  } catch {
    return "";
  }
}

export function consentido(): boolean {
  try {
    return permiteCategoria("analytics");
  } catch {
    return false;
  }
}

export function track(payload: PayloadEvento): boolean {
  if (typeof window === "undefined") return false;
  if (!consentido()) return false;
  try {
    // `caminhoSeguro` remove query string, fragment e userinfo do path. Vale
    // para o `path` explícito também: nenhum chamador deve conseguir reintroduzir
    // dado sensível no evento por passes `path` à mão.
    const pathInformado = payload.path ? caminhoSeguro(payload.path) : "";
    const corpo = {
      ...payload,
      path: pathInformado || caminhoSeguro(window.location.pathname),
      sessao: payload.sessao ?? obterSessao(),
      dispositivo: payload.dispositivo ?? detectarDispositivo(),
      origem: payload.origem ?? detectarOrigem(),
    };
    const dados = JSON.stringify(corpo);
    if (navigator.sendBeacon) {
      const blob = new Blob([dados], { type: "application/json" });
      navigator.sendBeacon(`${API_BASE_URL}/api/metricas/eventos/`, blob);
    } else {
      void fetch(`${API_BASE_URL}/api/metricas/eventos/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: dados,
        keepalive: true,
      }).catch(() => undefined);
    }
    return true;
  } catch {
    return false;
  }
}

// --- helpers por evento (extensível) -----------------------------------------

export function trackPageView(path?: string): boolean {
  return track({ tipo: "page_view", path });
}

export function trackNewsView(entry_tipo: "item" | "cluster", entry_id: number, categoria?: string): boolean {
  return track({ tipo: "news_view", entry_tipo, entry_id, categoria });
}

export function trackNewsClick(entry_tipo: "item" | "cluster", entry_id: number, categoria?: string): boolean {
  return track({ tipo: "news_click", entry_tipo, entry_id, categoria });
}

export function trackNewsRead(entry_tipo: "item" | "cluster", entry_id: number, tempo_leitura_seg: number, categoria?: string): boolean {
  // Leitura com tempo: roteada no backend para InteracaoNoticia (tipo read).
  return track({ tipo: "news_view", entry_tipo, entry_id, categoria, tempo_leitura_seg });
}

export function trackSearch(termo: string, resultados?: number, filtros?: Record<string, unknown>): boolean {
  return track({ tipo: "search", termo, resultados, filtros });
}

export function trackSearchClick(entry_tipo: "item" | "cluster", entry_id: number, termo: string): boolean {
  return track({ tipo: "search_result_click", entry_tipo, entry_id, termo });
}

export function trackCategoryView(categoria: string): boolean {
  return track({ tipo: "category_view", categoria });
}

export function trackCategoryClick(categoria: string): boolean {
  return track({ tipo: "category_click", categoria });
}

export function trackAuthorView(autor_ref: string): boolean {
  return track({ tipo: "author_view", autor_ref });
}

export function trackColumnistView(autor_ref: string): boolean {
  return track({ tipo: "columnist_view", autor_ref });
}

export function trackShare(entry_tipo: "item" | "cluster", entry_id: number, categoria?: string): boolean {
  return track({ tipo: "share", entry_tipo, entry_id, categoria });
}

export function trackSave(entry_tipo: "item" | "cluster", entry_id: number, categoria?: string): boolean {
  return track({ tipo: "save", entry_tipo, entry_id, categoria });
}

export function trackRadarView(extra?: Record<string, unknown>): boolean {
  return track({ tipo: "radar_view", extra });
}

export function trackLocationPermission(concedida: boolean): boolean {
  return track({ tipo: "location_permission", extra: { concedida } });
}

export function trackLocationSelected(regiao: { pais?: string; estado?: string; cidade?: string; regiao?: string }): boolean {
  return track({ tipo: "location_selected", ...regiao });
}

export function trackHomeSectionView(secao_home: string): boolean {
  return track({ tipo: "home_section_view", secao_home });
}

export function trackHomeSectionClick(secao_home: string, entry_tipo?: "item" | "cluster", entry_id?: number): boolean {
  return track({ tipo: "home_section_click", secao_home, entry_tipo, entry_id });
}

export function trackCommunityView(extra?: Record<string, unknown>): boolean {
  return track({ tipo: "community_view", extra });
}

export function trackCommunityInteraction(acao: string, extra?: Record<string, unknown>): boolean {
  return track({ tipo: "community_interaction", extra: { acao, ...(extra || {}) } });
}

// Expõe para instrumentação declarativa de qualquer frente.
declare global {
  interface Window {
    __portalTrack?: (payload: PayloadEvento) => boolean;
  }
}

if (typeof window !== "undefined") {
  window.__portalTrack = track;
}
