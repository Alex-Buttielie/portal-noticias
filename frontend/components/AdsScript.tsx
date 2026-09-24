"use client";

import Script from "next/script";
import { useEffect, useState } from "react";
import { EVENTO_CONSENTIMENTO_ALTERADO, permiteCategoria } from "@/lib/cookie-consent";

export const ADSENSE_CLIENT_ID = process.env.NEXT_PUBLIC_ADSENSE_CLIENT_ID || "";

/**
 * Script do Google AdSense (`adsbygoogle.js`). Só é injetado quando
 * `NEXT_PUBLIC_ADSENSE_CLIENT_ID=ca-pub-...` está configurado (build) e
 * o visitante consentiu com `personalizacao`. Sem publisher ID, os
 * `AdsSlot` seguem como placeholder visual — nada quebra e nenhuma
 * chamada externa acontece (LGPD/privacidade por padrão).
 */
export function AdsScript() {
  const [podeCarregar, setPodeCarregar] = useState(false);

  useEffect(() => {
    const atualizar = () => setPodeCarregar(permiteCategoria("personalizacao"));
    atualizar();
    window.addEventListener(EVENTO_CONSENTIMENTO_ALTERADO, atualizar);
    return () => window.removeEventListener(EVENTO_CONSENTIMENTO_ALTERADO, atualizar);
  }, []);

  if (!ADSENSE_CLIENT_ID || !podeCarregar) return null;
  return (
    <Script
      id="adsbygoogle"
      strategy="lazyOnload"
      src={`https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=${ADSENSE_CLIENT_ID}`}
      crossOrigin="anonymous"
    />
  );
}
