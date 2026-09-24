"use client";
import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { SeloBadge } from "@/components/home/NewsCard";
import { ImagemNoticia } from "@/components/ImagemNoticia";
import { formatarDataConteudo, iniciais, type Colunista } from "@/lib/colunistas";
import { Feather, ArrowRight, BadgeCheck } from "lucide-react";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Seção Colunistas na Home (FRENTE 2) — componente apresentacional: os
// dados são carregados uma vez no Server Component/ISR da Home e chegam
// por props, evitando a cascata client-side de publicações + perfis.
// Mantém o mesmo padrão visual dos cards de
// notícia (article + borda + hover), com foto (ou iniciais, nunca inventada),
// nome, especialidade, selo e conteúdo mais recente. Oculta-se quando não há
// dado real (sem mocks de pessoas).
// ---------------------------------------------------------------------------

function AvatarColunista({ colunista, tamanho = "md" }: { colunista: Colunista; tamanho?: "md" | "sm" }) {
  const cls =
    tamanho === "sm"
      ? "h-9 w-9 text-xs"
      : "h-12 w-12 text-sm";
  if (colunista.foto_url) {
    return (
      <ImagemNoticia
        src={colunista.foto_url}
        seed={`colunista-${colunista.id}`}
        alt={`Foto de ${colunista.nome}`}
        sizes="48px"
        className={cn("shrink-0 rounded-full border border-[var(--cor-borda)] object-cover", cls)}
        fallbackClassName={cn("shrink-0 rounded-full border border-[var(--cor-borda)]", cls)}
        fallback={
          <span
            aria-hidden
            className={cn(
              "flex shrink-0 items-center justify-center rounded-full bg-[var(--cor-primaria-suave)] font-bold text-[var(--cor-primaria)]",
              cls
            )}
          >
            {iniciais(colunista.nome)}
          </span>
        }
      />
    );
  }
  return (
    <span
      aria-hidden
      className={cn(
        "flex shrink-0 items-center justify-center rounded-full bg-[var(--cor-primaria-suave)] font-bold text-[var(--cor-primaria)]",
        cls
      )}
    >
      {iniciais(colunista.nome)}
    </span>
  );
}

export function SecaoColunistas({ colunistas }: { colunistas: Colunista[] }) {
  if (colunistas.length === 0) return null;

  return (
    <section aria-label="Colunistas" className="space-y-3">
      <div className="flex items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 text-lg font-bold text-[var(--cor-texto)]">
          <Feather className="h-5 w-5 text-[var(--cor-primaria)]" aria-hidden /> Colunistas
        </h2>
        <Link href="/comunidade" className="text-sm font-medium text-[var(--cor-primaria)] hover:underline">
          Ver comunidade →
        </Link>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {colunistas.map((c) => (
          <article
            key={c.id}
            className="group flex flex-col overflow-hidden rounded-[var(--raio-lg)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] motion-safe:transition-all hover:shadow-[var(--sombra-2)] hover:-translate-y-0.5"
          >
            <div className="flex items-center gap-3 p-4 pb-3">
              <AvatarColunista colunista={c} />
              <div className="min-w-0 flex-1">
                <Link
                  href={`/autor/${c.id}`}
                  className="block truncate text-sm font-bold text-[var(--cor-texto)] hover:text-[var(--cor-primaria)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]"
                >
                  {c.nome}
                </Link>
                <p className="truncate text-xs capitalize text-[var(--cor-texto-suave)]">{c.especialidade}</p>
              </div>
              {c.credenciado && (
                <Badge
                  variant="outline"
                  className="inline-flex shrink-0 items-center gap-1 border-[var(--cor-sucesso)] text-[var(--cor-sucesso)]"
                  title="Colunista credenciado"
                >
                  <BadgeCheck className="h-3 w-3" aria-hidden /> Selo
                </Badge>
              )}
            </div>

            <Link
              href={`/comunidade/${c.recente.id}`}
              aria-label={c.recente.titulo}
              className="mx-4 block overflow-hidden rounded-[var(--raio-md)] bg-[var(--cor-fundo-elevado)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]"
            >
              <ImagemNoticia
                seed={`col-${c.recente.id}`}
                alt=""
                className="aspect-[16/9] w-full object-cover motion-safe:transition motion-safe:duration-300 group-hover:motion-safe:scale-[1.02]"
              />
            </Link>

            <CardContent className="flex flex-1 flex-col gap-2 p-4 pt-3">
              <div className="flex flex-wrap items-center gap-2">
                <SeloBadge selo={c.selo} />
                <time dateTime={c.recente.publicado_em || c.recente.criado_em} className="text-xs text-[var(--cor-texto-suave)]">
                  {formatarDataConteudo(c.recente)}
                </time>
              </div>
              <Link
                href={`/comunidade/${c.recente.id}`}
                className="line-clamp-2 text-balance text-[15px] font-bold leading-tight text-[var(--cor-texto)] hover:text-[var(--cor-primaria)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] motion-safe:transition-colors"
              >
                {c.recente.titulo}
              </Link>
              <div className="mt-auto flex items-center justify-between pt-2 text-xs">
                <span className="text-[var(--cor-texto-suave)]">
                  {c.total_textos} {c.total_textos === 1 ? "texto" : "textos"}
                  {c.numero_seguidores > 0 && ` • ${c.numero_seguidores} seguidores`}
                </span>
                <Link
                  href={`/autor/${c.id}`}
                  className="inline-flex shrink-0 items-center gap-1 font-medium text-[var(--cor-primaria)] hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]"
                >
                  Ver perfil <ArrowRight className="h-3 w-3" aria-hidden />
                </Link>
              </div>
            </CardContent>
          </article>
        ))}
      </div>

      {colunistas.length > 0 && (
        <Card className="border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)]">
          <CardContent className="flex flex-wrap items-center justify-between gap-2 p-3 text-xs text-[var(--cor-texto-suave)]">
            <span>Opinião e análise de autores credenciados — o contraditório faz parte da cobertura.</span>
            <Link href="/comunidade" className="font-medium text-[var(--cor-primaria)] hover:underline">
              Todos os textos →
            </Link>
          </CardContent>
        </Card>
      )}
    </section>
  );
}
