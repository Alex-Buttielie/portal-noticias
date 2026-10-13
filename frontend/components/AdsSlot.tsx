"use client";

import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";
import { EVENTO_CONSENTIMENTO_ALTERADO } from "@/lib/cookie-consent";
import { useAuth } from "@/lib/auth-context";
import { usePremiumAtivo } from "@/lib/premium";
import { CartaoPremium } from "@/components/CartaoPremium";
import {
  ADSENSE_CLIENT_ID,
  ALTURA_FORMATO,
  consentiuAnuncio,
  mostrarPlaceholderDebug,
  podeExibirAnuncio,
  resolverSlotAnuncio,
  type FormatoAnuncio,
} from "@/lib/anuncios";

type Formato = FormatoAnuncio;

const ALTURA = ALTURA_FORMATO;

declare global {
  interface Window {
    adsbygoogle?: unknown[];
  }
}

/**
 * Slot de publicidade.
 *
 * A decisão "este visitante vê anúncio?" é de `lib/anuncios.ts`
 * (`podeExibirAnuncio`) e é resolvida AQUI, dentro do componente — não no
 * ponto de montagem. Isso é deliberado e é a correção principal do P1-09:
 *
 * - antes, cada página decidia sozinha. `HomeClient` protegia 5 dos seus 10
 *   slots com `!premiumGeral` e deixava passar os outros 5
 *   (`home-pos-bombando`, `home-topo`, `home-sidebar`, `home-sidebar-2`,
 *   `home-footer`); 6 das 9 páginas que montam `AdsSlot` — inclusive a
 *   leitura da notícia, `LeituraPremium` — não mencionavam o Premium uma vez
 *   sequer. Um assinante Premium que tivesse clicado em "Aceitar todos" pelo
 *   banner recebia anúncio no meio da leitura;
 * - agora, o Premium é decidido dentro do slot, então um `AdsSlot` esquecido
 *   numa página nova nasce correto. `!premiumGeral` no chamador continua
 *   válido (evita reservar espaço para um slot que não vai existir), mas
 *   deixou de ser a única linha de defesa.
 *
 * E o **fallback Free sem ads**: `usePremiumAtivo` devolve `liberado === true`
 * enquanto o status Premium é `null` (carregando) ou se a consulta falhou. Nesse
 * estado `premiumGeral` é `true` e o componente devolve `null` — o visitante
 * não vê anúncio no lugar do Premium que não abriu. É a direção segura, e é o
 * que o acordo do programa pede.
 */
export function AdsSlot({
  id,
  formato,
  className,
  rotulo,
  slot: slotExplicito,
}: {
  id: string;
  formato: Formato;
  className?: string;
  rotulo?: string;
  /** M-04: override manual do slot do AdSense para esta instância. Sem
   *  isto, a posição (`id`) resolve sozinha via `NEXT_PUBLIC_ADSENSE_SLOT_*`
   *  — ver `lib/anuncios.ts` (`resolverSlotAnuncio`). */
  slot?: string;
}) {
  const ref = useRef<HTMLModElement>(null);
  const [consentiu, setConsentiu] = useState(false);
  const { usuario } = useAuth();
  const { ativo } = usePremiumAtivo();
  const isPremium = usuario?.papel === "premium" || usuario?.papel === "admin";
  // Desacoplamento ads x flag global (feat/adsense-ativar-dev): a decisão usa
  // `ativo === null` (status desconhecido/erro) e NÃO `liberado`. Com a flag
  // OFF conhecida (`ativo === false`), free vê anúncio; só o desconhecido
  // esconde — é o fallback seguro sem matar a monetização em dev.
  const premiumGeral = isPremium || ativo === null;
  const slot = resolverSlotAnuncio(id, formato, slotExplicito);

  useEffect(() => {
    const atualizar = () => setConsentiu(consentiuAnuncio());
    atualizar();
    window.addEventListener(EVENTO_CONSENTIMENTO_ALTERADO, atualizar);
    return () => window.removeEventListener(EVENTO_CONSENTIMENTO_ALTERADO, atualizar);
  }, []);

  const podeExibir = podeExibirAnuncio({
    consentiu,
    premium: premiumGeral,
    temPublisherId: Boolean(ADSENSE_CLIENT_ID && slot),
  });

  useEffect(() => {
    if (!podeExibir || !ref.current) return;
    try {
      (window.adsbygoogle = window.adsbygoogle || []).push({});
    } catch {
      /* AdSense indisponível (adblock/offline) — mantém o espaço reservado */
    }
  }, [podeExibir, slot]);

  // Premium (ou status Premium desconhecido): NENHUM nó de anúncio, nem
  // placeholder, nem espaço reservado. "Premium sem anúncios" quer dizer sem
  // buraco com a palavra PUBLICIDADE no meio da leitura.
  if (premiumGeral) return null;

  if (podeExibir) {
    return (
      <div
        role="complementary"
        aria-label={`Publicidade ${id}`}
        className={cn("overflow-hidden", className)}
        style={{ minHeight: ALTURA[formato] }}
      >
        <ins
          ref={ref}
          className="adsbygoogle"
          style={{ display: "block" }}
          data-ad-client={ADSENSE_CLIENT_ID}
          data-ad-slot={slot}
          data-ad-format="auto"
          data-full-width-responsive="true"
        />
      </div>
    );
  }

  // M-05: sem anúncio disponível (sem consentimento, ou sem publisher
  // ID/slot) — em produção, o leitor NUNCA vê texto técnico
  // ("Google AdSense"/"slot {id}"). Nenhum nó, nenhum buraco visual com
  // jargão de ad tech.
  if (!mostrarPlaceholderDebug(process.env.NODE_ENV)) {
    // M-09: o espaço que ficaria vazio (Free sem consentimento, ou sem
    // publisher ID) vira oportunidade de conversão em vez de buraco —
    // nunca "publicidade"/"AdSense" no texto (ver CartaoPremium.tsx).
    return <CartaoPremium formato={formato} className={className} />;
  }

  // Só fora de produção (NODE_ENV !== "production") — ajuda quem está
  // codando a ver o espaço reservado sem publisher ID configurado.
  return (
    <div
      role="complementary"
      aria-label={`Publicidade ${id}`}
      className={cn(
        "relative flex flex-col items-center justify-center overflow-hidden rounded-[var(--raio-lg)] border border-dashed bg-[var(--cor-fundo-elevado)] p-4 text-center",
        className
      )}
      style={{ minHeight: ALTURA[formato], borderColor: "var(--cor-borda)" }}
    >
      <div className="hud-grid absolute inset-0 opacity-[0.12]" aria-hidden />
      <div className="relative flex flex-col items-center gap-1">
        <span className="text-[10px] font-medium tracking-[0.14em] text-[var(--cor-texto-suave)]">
          PUBLICIDADE{rotulo ? ` • ${rotulo.toUpperCase()}` : ""}
        </span>
        <span className="max-w-[28ch] text-balance text-sm font-medium leading-tight text-[var(--cor-texto-suave)]">
          Anúncio — Google AdSense (slot {id})
        </span>
        <span className="rounded-full border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] px-2.5 py-0.5 text-[10px] tracking-wide text-[var(--cor-texto-suave)]">
          Conteúdo publicitário
        </span>
      </div>
    </div>
  );
}
