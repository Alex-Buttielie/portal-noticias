/**
 * FRENTE 6 — Reporters explícitos (montados nas páginas server-side):
 * - `NoticiaReporter`: fonte única de `news_view`, com evento inicial +
 *   tempo de leitura (heartbeat de 5s com a aba visível) + scroll máximo,
 *   enviados ao sair (`pagehide`);
 * - `BuscarReporter`: search com termo + nº de resultados (dado real do
 *   servidor — nunca 0 inventado: sem contagem, não envia `resultados`).
 */

"use client";

import { useEffect, useRef } from "react";
import { track, trackSearch } from "@/lib/analytics";

export function NoticiaReporter({
  entryTipo,
  entryId,
  categoria,
}: {
  entryTipo: "item" | "cluster";
  entryId: number;
  categoria?: string;
}) {
  const lido = useRef(0);
  const scrollMax = useRef(0);
  useEffect(() => {
    // Fonte única de news_view: o tracker global não deriva este evento da
    // URL, para não contar a mesma leitura duas vezes.
    track({ tipo: "news_view", entry_tipo: entryTipo, entry_id: entryId, categoria });
    const tick = window.setInterval(() => {
      if (document.visibilityState === "visible") lido.current += 5;
    }, 5000);
    const onScroll = () => {
      try {
        const total = document.documentElement.scrollHeight - window.innerHeight;
        const pct = total > 0 ? Math.round((window.scrollY / total) * 100) : 0;
        scrollMax.current = Math.max(scrollMax.current, Math.min(100, pct));
      } catch {
        /* noop */
      }
    };
    const onHide = () => {
      if (lido.current >= 5) {
        track({
          tipo: "news_view",
          entry_tipo: entryTipo,
          entry_id: entryId,
          categoria,
          tempo_leitura_seg: lido.current,
          scroll_max_pct: scrollMax.current,
          extra: { leitura: true },
        });
      }
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("pagehide", onHide);
    return () => {
      window.clearInterval(tick);
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("pagehide", onHide);
    };
  }, [entryTipo, entryId, categoria]);
  return null;
}

export function BuscarReporter({ termo, resultados }: { termo: string; resultados?: number }) {
  const enviado = useRef(false);
  useEffect(() => {
    if (enviado.current || !termo) return;
    enviado.current = true;
    trackSearch(
      termo,
      typeof resultados === "number" ? resultados : undefined,
      { origem: "pagina_buscar" }
    );
  }, [termo, resultados]);
  return null;
}

export function CategoriaReporter({ categoria }: { categoria: string }) {
  useEffect(() => {
    if (categoria) track({ tipo: "category_view", categoria });
  }, [categoria]);
  return null;
}

export function AutorReporter({ autorRef, colunista }: { autorRef: string; colunista?: boolean }) {
  useEffect(() => {
    if (autorRef) track({ tipo: colunista ? "columnist_view" : "author_view", autor_ref: autorRef });
  }, [autorRef, colunista]);
  return null;
}
