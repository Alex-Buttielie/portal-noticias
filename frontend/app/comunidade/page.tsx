"use client";

import Link from "next/link";
import type * as api from "@/lib/api";
import { usePublicacoes } from "@/lib/queries";
import Badge from "@/components/Badge";
import { Card, CardHeader, CardTitle } from "@/components/ui/Cards";
import { EmptyState, ErrorState, SkeletonLista } from "@/components/ui/Estados";
import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/utils";

function CartaoPublicacao({ publicacao }: { publicacao: api.Publicacao }) {
  return (
    <Link href={`/comunidade/${publicacao.id}`} className="block min-w-0 overflow-hidden break-words no-underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] rounded-xl cartao-titulo cartao-meta">
      <Card className="h-full min-w-0 overflow-hidden break-words p-4 transition-colors hover:border-[var(--cor-primaria)] motion-reduce:transition-none">
        <div className="mb-2 flex flex-wrap gap-1.5">
          <Badge variante={publicacao.tipo === "opiniao" ? "premium" : "neutro"}>
            {publicacao.tipo === "opiniao" ? "Opinião" : "Análise"}
          </Badge>
          {publicacao.categoria && <Badge variante="neutro">{publicacao.categoria}</Badge>}
          {publicacao.destaque && <Badge variante="sucesso">Destaque editorial</Badge>}
        </div>
<CardTitle className="break-words line-clamp-3 text-base">{publicacao.titulo}</CardTitle>
        <p className="mt-1 break-words text-sm text-[var(--cor-texto-suave)] texto-suave">por {publicacao.autor_nome}</p>
      </Card>
    </Link>
  );
}

export default function PaginaComunidade() {
  const destaques = usePublicacoes({ destaque: true });
  const lista = usePublicacoes();

  return (
<div className="min-w-0 w-full max-w-full space-y-6 overflow-hidden">
      <header className={cn("seu-rio", "min-w-0 space-y-2 overflow-hidden")}>
        <p className="text-xs font-bold uppercase tracking-[0.14em] text-[var(--cor-primaria)] secao-eyebrow">Vozes</p>
        <h1 className="font-[var(--fonte-titulo)] text-3xl font-extrabold tracking-[-0.03em] text-wrap-balance seu-rio__titulo">Comunidade</h1>
        <p className="max-w-[62ch] break-words text-sm leading-relaxed text-[var(--cor-texto-suave)] texto-suave">
          Opiniões e análises de autores credenciados — sempre identificadas como tal, nunca confundidas com a cobertura factual do feed.{" "}
          <Link href="/comunidade/nova" className="font-medium text-[var(--cor-primaria)] hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] secao-ver-tudo">
            Publicar análise →
          </Link>
        </p>
      </header>

<div aria-live="polite" aria-busy={lista.isLoading || undefined}>
        {lista.isLoading && <SkeletonLista quantidade={4} />}
        {lista.isError && (
          <ErrorState
            mensagem={lista.error instanceof Error ? lista.error.message : "Não foi possível carregar a comunidade."}
            aoTentarNovamente={() => void lista.refetch()}
          />
        )}
      </div>

      {destaques.data && destaques.data.length > 0 && (
<section className="min-w-0 space-y-4 overflow-hidden secao-bloco" aria-label="Destaques editoriais">
          <div className="flex items-baseline gap-3 border-b-2 border-[var(--cor-borda)] pb-3 secao-cabecalho">
            <p className="text-xs font-bold uppercase tracking-[0.14em] text-[var(--cor-primaria)] secao-eyebrow">Seleção</p>
            <h2 className="font-[var(--fonte-titulo)] text-xl font-extrabold tracking-tight secao-titulo">Destaques editoriais</h2>
          </div>
          <div className={cn("grade-noticias", "grid w-full max-w-full grid-cols-1 gap-4 overflow-hidden break-words sm:grid-cols-2 lg:grid-cols-3")}>
            {destaques.data.map((publicacao) => (
              <div key={publicacao.id} className="min-w-0 overflow-hidden break-words grade-noticias">
                <CartaoPublicacao publicacao={publicacao} />
              </div>
            ))}
          </div>
        </section>
      )}

      {!lista.isLoading && !lista.isError && lista.data?.length === 0 && (
        <EmptyState titulo="Nenhuma publicação ainda" descricao="Volte em breve para ler as análises dos jornalistas." />
      )}

      {(lista.data?.length ?? 0) > 0 && (destaques.data?.length ?? 0) > 0 && (
<section className="min-w-0 space-y-4 overflow-hidden secao-bloco" aria-label="Todas as publicações">
          <div className="flex items-baseline gap-3 border-b-2 border-[var(--cor-borda)] pb-3 secao-cabecalho">
            <p className="text-xs font-bold uppercase tracking-[0.14em] text-[var(--cor-primaria)] secao-eyebrow">Arquivo</p>
            <h2 className="font-[var(--fonte-titulo)] text-xl font-extrabold tracking-tight secao-titulo">Todas as publicações</h2>
          </div>
          <div className={cn("grade-noticias", "grid w-full max-w-full grid-cols-1 gap-4 overflow-hidden break-words sm:grid-cols-2 lg:grid-cols-3")}>
            {lista.data?.map((publicacao) => (
              <div key={publicacao.id} className="min-w-0 overflow-hidden break-words grade-noticias">
                <CartaoPublicacao publicacao={publicacao} />
              </div>
            ))}
          </div>
        </section>
      )}
      {(lista.data?.length ?? 0) > 0 && (destaques.data?.length ?? 0) === 0 && (
<div className={cn("grade-noticias", "grid w-full max-w-full grid-cols-1 gap-4 overflow-hidden break-words sm:grid-cols-2 lg:grid-cols-3")}>
          {lista.data?.map((publicacao) => (
            <div key={publicacao.id} className="min-w-0 overflow-hidden break-words grade-noticias">
              <CartaoPublicacao publicacao={publicacao} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
