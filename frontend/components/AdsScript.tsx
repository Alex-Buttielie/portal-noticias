"use client";

import Script from "next/script";
import { useEffect, useState } from "react";
import { EVENTO_CONSENTIMENTO_ALTERADO } from "@/lib/cookie-consent";
import { useAuth } from "@/lib/auth-context";
import { usePremiumAtivo } from "@/lib/premium";
import {
  ADSENSE_CLIENT_ID,
  consentiuAnuncio,
  revogarSaidaAds,
} from "@/lib/anuncios";

export { ADSENSE_CLIENT_ID };

/**
 * Script do Google AdSense (`adsbygoogle.js`). Só é injetado quando
 * `NEXT_PUBLIC_ADSENSE_CLIENT_ID=ca-pub-...` está configurado (build),
 * o visitante consentiu com a categoria de publicidade E não é Premium
 * (nem o status Premium está desconhecido). Sem publisher ID, os `AdsSlot`
 * seguem como placeholder visual — nada quebra e nenhuma chamada externa
 * acontece (LGPD/privacidade por padrão).
 *
 * Três condições, e as três importam:
 *
 * 1. **Consentimento.** `podeCarregar` começa em `false` e só vira `true` no
 *    `useEffect`, ou seja, nunca durante o SSR. O HTML do `<head>` servido
 *    pelo servidor não contém referência a `googlesyndication.com` — provado
 *    em runtime, não por leitura de código.
 * 2. **Premium.** Um assinante Premium não baixa `adsbygoogle.js` sequer. Não
 *    basta esconder o `<ins>`: baixar a biblioteca já é declarar a visita ao
 *    Google, e o acordo do programa é "Premium sem anúncios".
 * 3. **Fallback Free sem ads.** Enquanto o status Premium não é conhecido
 *    (`liberado === true` em `usePremiumAtivo`, que é fail-open para o
 *    Premium), `podeCarregar` é `false`. Quem não tem assinatura veem a
 *    banner de consentimento primeiro; ninguém vê anúncio "no lugar" do
 *    Premium que não abriu.
 */
export function AdsScript() {
  const [consentiu, setConsentiu] = useState(false);
  const { usuario } = useAuth();
  const { liberado } = usePremiumAtivo();
  const isPremium = usuario?.papel === "premium" || usuario?.papel === "admin";
  // `liberado` (fail-open) conta como Premium de propósito: status
  // desconhecido ou com erro => sem anúncio, nunca "anúncio no lugar".
  const premiumGeral = isPremium || liberado;
  const podeCarregar = consentiu && !premiumGeral && Boolean(ADSENSE_CLIENT_ID);

  useEffect(() => {
    const atualizar = () => setConsentiu(consentiuAnuncio());
    atualizar();
    window.addEventListener(EVENTO_CONSENTIMENTO_ALTERADO, atualizar);
    return () => window.removeEventListener(EVENTO_CONSENTIMENTO_ALTERADO, atualizar);
  }, []);

  // Revogação (ou troca para Premium, ou navegador sem sessão): derruba a
  // saída de anúncio JÁ carregada. Sem este efeito, revogar o consentimento
  // deixava o `<script>` do AdSense vivo no DOM — `next/script` com
  // `lazyOnload` não tem cleanup de unmount — e o tracking continuava depois
  // da revogação. Ver `lib/anuncios.ts::revogarSaidaAds`.
  useEffect(() => {
    if (!podeCarregar) revogarSaidaAds();
  }, [podeCarregar]);

  if (!podeCarregar) return null;
  return (
    <Script
      id="adsbygoogle"
      strategy="lazyOnload"
      src={`https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=${ADSENSE_CLIENT_ID}`}
      crossOrigin="anonymous"
    />
  );
}
