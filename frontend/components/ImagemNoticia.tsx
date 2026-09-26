"use client";

// Imagem resiliente mobile-first.
//
// Problemas que corrige:
// - URLs de RSS com hotlink bloqueado/404/mixed-content exibiam o ícone
//   quebrado e estouravam o layout (grid, trilho "Ao vivo", hero).
// - Sem `referrerPolicy="no-referrer"` vários portais negam o hotlink.
// - Sem `srcSet` o mobile baixava 800px+ no 4G (lento + shift de layout).
//
// Cadeia de fallback: src original → picsum (seed) → placeholder local.
// O placeholder mantém a mesma geometria (mesmas classes), então o layout
// nunca quebra nem desloca, mesmo offline.

import { useState, type ReactNode } from "react";
import { Newspaper } from "lucide-react";
import { cn } from "@/lib/utils";
import { ehPicsum, picsum, seedDePicsum, srcSetPicsum } from "@/lib/imagens";

type Props = {
  src?: string | null;
  alt: string;
  /** seed do fallback picsum (ex.: `${categoria}-${id}`) */
  seed: string;
  eager?: boolean;
  /** classes aplicadas à <img> (geometria: aspect, h/w, object-cover...) */
  className?: string;
  /** sizes para o srcSet; default mobile-first */
  sizes?: string;
  /** conteúdo alternativo quando TUDO falha (ex.: iniciais do avatar) */
  fallback?: ReactNode;
  /** classes do placeholder; default = mesmas da img */
  fallbackClassName?: string;
};

export function ImagemNoticia({
  src,
  alt,
  seed,
  eager = false,
  className,
  sizes = "(max-width: 640px) 100vw, (max-width: 1024px) 50vw, 33vw",
  fallback,
  fallbackClassName,
}: Props) {
  const original = (src || "").trim();
  const [fase, setFase] = useState<"original" | "picsum" | "falhou">(
    original ? "original" : "picsum"
  );

  if (fase === "falhou") {
    if (fallback) return <>{fallback}</>;
    return (
      <span
        role="img"
        aria-label={alt || "Imagem indisponível"}
        className={cn(
          "flex items-center justify-center bg-gradient-to-br from-[var(--cor-primaria-suave)] via-[var(--cor-fundo-elevado)] to-[var(--cor-fundo)]",
          fallbackClassName ?? className
        )}
      >
        <Newspaper
          className="h-8 w-8 text-[var(--cor-primaria)] opacity-60"
          aria-hidden
        />
      </span>
    );
  }

  const usandoPicsum = fase === "picsum" || !original;
  const atual = usandoPicsum ? picsum(seed) : original;
  // Reaproveita a seed quando o próprio original já é picsum.
  const seedEfetiva = usandoPicsum ? seed : (seedDePicsum(original) ?? seed);
  const comSrcSet = usandoPicsum || ehPicsum(original);

  return (
    // `<img>` proposital, não descuido. Três motivos, nenhum contornável
    // trocando a tag:
    // 1. A cadeia de fallback (original → picsum → placeholder) é dirigida por
    //    `onError`; o `next/image` tem o próprio ciclo de fallback e
    //    quebraria a máquina de estados de `fase`.
    // 2. As imagens vêm de domínios de RSS arbitrários (e justamente
    //    hostis: hotlink bloqueado, 404, mixed-content). O `next/image` exige
    //    enumerar cada host em `remotePatterns` — impossível para um portal
    //    agregador, e o hotlink que hoje é contornado passaria a 400/502.
    // 3. O `next/image` serve via `/_next/image`, que é exatamente a rota do
    //    RCE crítico ainda sem patch neste repositório
    //    (GHSA-2xp9-vwfh-vxw4, faixa >=10.0.0 <15.5.24). Mandar as imagens
    //    para lá aumentaria a exposição enquanto o Next não for atualizado.
    // O LCP é tratado com `loading`/`decoding`/`srcSet` acima. Desativação
    // pontual e justificada, não da regra.
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={atual}
      srcSet={comSrcSet ? srcSetPicsum(seedEfetiva) : undefined}
      sizes={comSrcSet ? sizes : undefined}
      alt={alt}
      loading={eager ? "eager" : "lazy"}
      decoding="async"
      draggable={false}
      referrerPolicy="no-referrer"
      onError={() =>
        setFase((f) => (f === "original" ? "picsum" : "falhou"))
      }
      className={className}
    />
  );
}

export default ImagemNoticia;
