/**
 * FRENTE 6 — Tracker global da Central de Inteligência (montado no layout).
 *
 * Automático, sem tocar nas páginas das outras frentes:
 * - `page_view` a cada troca de rota;
 * - derivados do pathname: category_view (/categoria, /editorias),
 *   author_view (/autor), radar_view (/radar), community_view
 *   (/comunidade), search_result_click não (precisa de termo);
 *   `news_view` é instrumentado exclusivamente por `NoticiaReporter`;
 * - `news_click`: clique em qualquer link para /noticia/* (com entry_tipo/id
 *   extraídos da URL) + `home_section_click` quando o clique ocorre na Home
 *   dentro de `section[aria-label]`;
 * - `home_section_view`: IntersectionObserver sobre `section[aria-label]`;
 * - `community_interaction`: cliques dentro de /comunidade*;
 * - tempo de permanência + scroll máximo: enviados no `pagehide`.
 *
 * Instrumentação fina (termo buscado, tempo de leitura, share/save,
 * região) vive nos componentes específicos via `lib/analytics.ts`.
 */

"use client";

import { useEffect, useRef } from "react";
import { usePathname, useSearchParams } from "next/navigation";
import {
  track,
  trackCommunityInteraction,
  trackHomeSectionClick,
  trackHomeSectionView,
  trackNewsClick,
} from "@/lib/analytics";

function slugSecao(label: string | null): string {
  if (!label) return "";
  return label
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 60);
}

function parseNoticia(href: string): { entry_tipo: "item" | "cluster"; entry_id: number } | null {
  try {
    const m = href.match(/\/noticia\/(?:(cluster|item)\/)?(\d+)/);
    if (!m) return null;
    return { entry_tipo: (m[1] as "item" | "cluster") || "item", entry_id: Number(m[2]) };
  } catch {
    return null;
  }
}

export function AnalyticsTracker() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const vistos = useRef<Set<string>>(new Set());
  const scrollMax = useRef(0);
  const inicio = useRef<number>(Date.now());

  // page_view + derivados da rota.
  useEffect(() => {
    inicio.current = Date.now();
    scrollMax.current = 0;
    // P1-10: o `path` do evento é o PATHNAME, sem query string. A busca
    // (`/buscar?q=…`) e a paginação (`/arquivo?page=…`) continuam
    // instrumentadas pelo campo `termo` do evento de busca; o que não pode é a
    // query string inteira colada em `path`, porque em `/verificar-email?token=…`
    // e `/newsletter?token=…` ela É um token de uso único — e o backend
    // persiste `path` sem redação (`backend/metricas/views.py:93`).
    //
    // `searchParams` continua no array de dependências de propósito: trocar só
    // a query dentro da MESMA rota (`/buscar?q=A` → `/buscar?q=B`) continua
    // sendo um page_view distinto. O que mudou é o valor, não o gatilho.
    const path = pathname;
    track({ tipo: "page_view", path });

    // `news_view` não é derivado aqui: `NoticiaReporter` é a fonte única
    // e preserva entry_tipo/entry_id, categoria, tempo de leitura e scroll.
    if (pathname.startsWith("/categoria/") || pathname.startsWith("/editorias")) {
      const categoria = decodeURIComponent(pathname.split("/").pop() || "").replace(/-/g, " ");
      if (categoria) track({ tipo: "category_view", categoria, path });
    } else if (pathname.startsWith("/autor/")) {
      const autor = decodeURIComponent(pathname.split("/").pop() || "");
      if (autor) track({ tipo: "author_view", autor_ref: autor, path });
    } else if (pathname === "/radar" || pathname.startsWith("/radar/")) {
      track({ tipo: "radar_view", path });
    } else if (pathname === "/comunidade" || pathname.startsWith("/comunidade")) {
      track({ tipo: "community_view", path });
    }
  }, [pathname, searchParams]);

  // home_section_view via IntersectionObserver (sections com aria-label).
  useEffect(() => {
    if (typeof window === "undefined") return;
    if (pathname !== "/") return;
    const obs = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (!e.isIntersecting) continue;
          const el = e.target as HTMLElement;
          const secao = slugSecao(el.getAttribute("aria-label")) || el.id || "home_secao";
          const chave = `hs:${secao}`;
          if (vistos.current.has(chave)) continue;
          vistos.current.add(chave);
          trackHomeSectionView(secao);
        }
      },
      { threshold: 0.25 }
    );
    const secoes = Array.from(
      document.querySelectorAll("main section[aria-label], main section[id]")
    );
    secoes.forEach((s) => obs.observe(s));
    return () => obs.disconnect();
  }, [pathname]);

  // Cliques delegados: news_click (+ home_section_click na Home) e
  // community_interaction nas páginas de comunidade. Scroll máximo contínuo.
  useEffect(() => {
    const onScroll = () => {
      try {
        const total = document.documentElement.scrollHeight - window.innerHeight;
        const pct = total > 0 ? Math.round((window.scrollY / total) * 100) : 0;
        scrollMax.current = Math.max(scrollMax.current, Math.min(100, pct));
      } catch {
        /* noop */
      }
    };
    const onClick = (ev: MouseEvent) => {
      try {
        const alvo = (ev.target as HTMLElement).closest?.("a[href], button");
        if (!alvo) return;
        // Opt-out declarativo.
        if ((alvo as HTMLElement).closest?.("[data-track-off]")) return;
        const href = (alvo as HTMLAnchorElement).getAttribute?.("href") || "";
        const noticia = href ? parseNoticia(href) : null;
        if (noticia && Number.isFinite(noticia.entry_id)) {
          trackNewsClick(noticia.entry_tipo, noticia.entry_id);
          if (window.location.pathname === "/") {
            const secaoEl = (alvo as HTMLElement).closest?.("section[aria-label], section[id]");
            const secao = secaoEl
              ? slugSecao(secaoEl.getAttribute("aria-label")) || secaoEl.id || "home_geral"
              : "home_geral";
            trackHomeSectionClick(secao, noticia.entry_tipo, noticia.entry_id);
          }
          return;
        }
        if (window.location.pathname.startsWith("/comunidade") && alvo.tagName === "BUTTON") {
          const acao = (alvo.textContent || "").trim().slice(0, 60) || "clique";
          trackCommunityInteraction(acao);
        }
      } catch {
        /* tracking nunca quebra a página */
      }
    };
    const onHide = () => {
      try {
        const seg = Math.round((Date.now() - inicio.current) / 1000);
        if (seg >= 3) {
          track({
            tipo: "page_view",
            path: window.location.pathname,
            tempo_permanencia_seg: seg,
            scroll_max_pct: scrollMax.current,
            extra: { saida: true },
          });
        }
      } catch {
        /* noop */
      }
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    document.addEventListener("click", onClick);
    window.addEventListener("pagehide", onHide);
    return () => {
      window.removeEventListener("scroll", onScroll);
      document.removeEventListener("click", onClick);
      window.removeEventListener("pagehide", onHide);
    };
  }, []);

  return null;
}
