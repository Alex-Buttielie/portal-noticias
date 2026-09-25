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
    // eslint-disable-next-line @next/next/no-img-element -- <img> é ESCOLHA, não esquecimento (Bloco D1, lint como gate): a origem é qualquer host de RSS, sem allowlist; o `srcSet` de picsum é montado aqui (o next/image é dono do srcset); e a cadeia de fallback depende de `onError` com fases. Migrar para next/image exige `images.remotePatterns` aberto — trocar hotlink bloqueado por erro de configuração, que é exatamente o defeito que este componente existe para resolver.
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
