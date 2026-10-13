"use client";

import { useEffect, useRef } from "react";
import { useQueryPatrocinioAtivo } from "@/lib/queries";
import { trackPatrocinioView, trackPatrocinioClick } from "@/lib/analytics";
import { cn } from "@/lib/utils";

const LARGURA_CRIATIVO = 120;
const ALTURA_CRIATIVO = 80;

/**
 * M-10 (run 20261012-1806-monetizacao-sprint1) — patrocínio identificado,
 * receita direta sem depender de conta de AdSense nem de consentimento de
 * anúncio (BRD §5 e §17). Busca o patrocínio vigente de `posicao` via
 * `GET /api/patrocinio/ativo/` e, se houver, renderiza com o rótulo
 * "Patrocinado" SEMPRE visível e `rel="sponsored nofollow noopener"`.
 *
 * Sem patrocínio vigente para a posição (404, erro, ou ainda carregando):
 * não renderiza nada — nunca inventa um patrocínio nem reserva um buraco
 * vazio no lugar.
 *
 * LGPD: o CONTEÚDO (rótulo, imagem, link) aparece independente de
 * consentimento — é conteúdo de primeira parte deste site, não rastreio de
 * terceiro. Só o REGISTRO de impressão/clique em `EventoSite`
 * (`patrocinio_view`/`patrocinio_click`) respeita o consentimento de
 * `analytics` — `trackPatrocinioView`/`trackPatrocinioClick` chamam
 * `track()` de `lib/analytics.ts`, que já é fail-closed sem
 * `permiteCategoria("analytics")`.
 */
export function PatrocinioSlot({ posicao, className }: { posicao: string; className?: string }) {
  const { data: patrocinio } = useQueryPatrocinioAtivo(posicao);
  const ref = useRef<HTMLDivElement>(null);
  const jaRegistrouView = useRef(false);

  useEffect(() => {
    jaRegistrouView.current = false;
    if (!patrocinio || !ref.current) return;
    const el = ref.current;
    const observador = new IntersectionObserver(
      (entradas) => {
        for (const entrada of entradas) {
          if (entrada.isIntersecting && !jaRegistrouView.current) {
            jaRegistrouView.current = true;
            trackPatrocinioView(patrocinio.posicao, patrocinio.id);
            observador.disconnect();
          }
        }
      },
      { threshold: 0.25 }
    );
    observador.observe(el);
    return () => observador.disconnect();
  }, [patrocinio]);

  if (!patrocinio) return null;

  return (
    <div
      ref={ref}
      role="complementary"
      aria-label="Conteúdo patrocinado"
      className={cn(
        "overflow-hidden rounded-[var(--raio-lg)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] p-3",
        className
      )}
    >
      <span className="mb-2 inline-block rounded-full border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-[var(--cor-texto-suave)]">
        Patrocinado
      </span>
      <a
        href={patrocinio.url}
        target="_blank"
        rel="sponsored nofollow noopener"
        onClick={() => trackPatrocinioClick(patrocinio.posicao, patrocinio.id)}
        className="group flex items-center gap-3 rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]"
      >
        {/* eslint-disable-next-line @next/next/no-img-element -- criativo vem
            de URL arbitrária cadastrada pelo anunciante; mesma decisão já
            tomada para a foto do RSS em ImagemNoticia.tsx (domínios não
            enumeráveis, next/image exige allowlist por domínio). */}
        <img
          src={patrocinio.criativo_url}
          alt={patrocinio.texto_alt}
          width={LARGURA_CRIATIVO}
          height={ALTURA_CRIATIVO}
          loading="lazy"
          referrerPolicy="no-referrer"
          className="h-20 w-[120px] shrink-0 rounded-md object-cover"
          style={{ width: LARGURA_CRIATIVO, height: ALTURA_CRIATIVO }}
        />
        <span className="min-w-0 truncate text-sm font-medium text-[var(--cor-texto)] group-hover:underline">
          {patrocinio.anunciante}
        </span>
      </a>
    </div>
  );
}
