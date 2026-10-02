"use client";

// Imagem resiliente mobile-first.
//
// Problemas que corrige:
// - URLs de RSS com hotlink bloqueado/404/mixed-content exibiam o ícone
//   quebrado e estouravam o layout (grid, trilho "Ao vivo", hero).
// - Sem `referrerPolicy="no-referrer"` vários portais negam o hotlink.
// - Sem `srcSet` o mobile baixava 800px+ no 4G (lento + shift de layout).
//
// Cadeia de fallback: src original → placeholder LOCAL → bloco com ícone.
// O placeholder mantém a mesma geometria (mesmas classes), então o layout
// nunca quebra nem desloca, mesmo offline.
//
// O PLACEHOLDER É LOCAL, E ISSO MUDOU A CADEIA
// =============================================
// A etapa do meio era `picsum.photos`, que é host de TERCEIRO e era
// requisitado ANTES de qualquer consentimento — 42 conexões na home. Hoje
// ela é um SVG gerado dentro do HTML (`lib/placeholder.ts`): o browser não
// abre conexão nenhuma para desenhá-lo. A máquina de estados continua com
// os mesmos três estágios, e o último continua existindo: se a imagem real
// falhar, cai no placeholder local; se algo der errado com ele, cai no bloco
// com o ícone do Newspaper.
//
// Sobre o `srcSet`: sumiu com o picsum, e por um bom motivo — um SVG escala
// para qualquer largura, então não há candidata maior/menor para escolher, e
// um `srcset` de data URI seria ruído. A foto REAL continua sem `srcSet`, por
// decisão antiga e independente: os domínios do RSS são arbitrários e não
// há como enumerá-los (ver a nota sobre `next/image` mais abaixo).

import { useState, type ReactNode } from "react";
import { Newspaper } from "lucide-react";
import { cn } from "@/lib/utils";
import { placeholder, urlImagemUtilizavel } from "@/lib/imagens";

type Props = {
  src?: string | null;
  alt: string;
  /** identificador do placeholder (ex.: `${categoria}-${id}`) */
  seed: string;
  eager?: boolean;
  /** classes aplicadas à <img> (geometria: aspect, h/w, object-cover...) */
  className?: string;
  /** aceito e ignorado: sem `srcSet` não há para que `sizes` seja usado */
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
  fallback,
  fallbackClassName,
}: Props) {
  // `src` chega cru de várias rotas (`n.imagem_url` direto do feed), sem
  // passar por `imagemNoticia()`. Por isso as duas recusas são aplicadas AQUI,
  // no último ponto antes do `src`: nenhum caminho pode contornar.
  //
  // `urlImagemUtilizavel` = allowlist de ESQUEMA (fail-closed: um
  // `javascript:` recusado nunca vira `src`) + recusa do host que já foi o
  // placeholder do portal, para que um feed apontando para ele não
  // reconecte o terceiro por dentro da allowlist.
  const original = urlImagemUtilizavel(src) ?? "";
  const [fase, setFase] = useState<"original" | "placeholder" | "falhou">(
    original ? "original" : "placeholder"
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

  const usandoPlaceholder = fase === "placeholder" || !original;
  const atual = usandoPlaceholder ? placeholder(seed) : original;

  return (
    // `<img>` proposital, não descuido. Três motivos, nenhum contornável
    // trocando a tag:
    // 1. A cadeia de fallback (original → placeholder local → bloco) é
    //    dirigida por `onError`; o `next/image` tem o próprio ciclo de
    //    fallback e quebraria a máquina de estados de `fase`.
    // 2. As imagens vêm de domínios de RSS arbitrários (e justamente
    //    hostis: hotlink bloqueado, 404, mixed-content). O `next/image` exige
    //    enumerar cada host em `remotePatterns` — impossível para um portal
    //    agregador, e o hotlink que hoje é contornado passaria a 400/502.
    // 3. O `next/image` serve via `/_next/image`, que é exatamente a rota do
    //    RCE crítico ainda sem patch neste repositório
    //    (GHSA-2xp9-vwfh-vxw4, faixa >=10.0.0 <15.5.24). Mandar as imagens
    //    para lá aumentaria a exposição enquanto o Next não for atualizado.
    // O LCP é tratado com `loading`/`decoding` acima. Desativação
    // pontual e justificada, não da regra.
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={atual}
      alt={alt}
      loading={eager ? "eager" : "lazy"}
      decoding="async"
      draggable={false}
      referrerPolicy="no-referrer"
      onError={() =>
        setFase((f) => (f === "original" ? "placeholder" : "falhou"))
      }
      className={className}
    />
  );
}

export default ImagemNoticia;