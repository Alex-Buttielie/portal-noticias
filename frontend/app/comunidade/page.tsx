"use client";

import { Suspense, useMemo } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import type * as api from "@/lib/api";
import { usePublicacoes } from "@/lib/queries";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { DataTable } from "@/components/ui/data-table";
import type { LegacyColumnDef } from "@tanstack/react-table/legacy";
import { EmptyState, ErrorState, SkeletonLista } from "@/components/ui/Estados";
import { cn } from "@/lib/utils";

const formatoData = new Intl.DateTimeFormat("pt-BR", { day: "2-digit", month: "short", year: "numeric" });

function formatarData(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : formatoData.format(d);
}

function CartaoPublicacao({ publicacao }: { publicacao: api.Publicacao }) {
  return (
    <Link
      href={`/comunidade/${publicacao.id}`}
      className="block min-w-0 overflow-hidden break-words rounded-xl no-underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]"
    >
      <Card className="h-full min-w-0 overflow-hidden break-words p-4 transition-colors hover:border-[var(--cor-primaria)] motion-reduce:transition-none">
        <div className="mb-2 flex min-w-0 flex-wrap gap-1.5">
          <Badge variant={publicacao.tipo === "opiniao" ? "default" : "secondary"} className="min-h-0">
            {publicacao.tipo === "opiniao" ? "Opinião" : "Análise"}
          </Badge>
          {publicacao.categoria && (
            <Badge variant="secondary" className="min-h-0">
              {publicacao.categoria}
            </Badge>
          )}
          {publicacao.destaque && (
            <Badge variant="success" className="min-h-0">
              Destaque editorial
            </Badge>
          )}
        </div>
        <p className="min-w-0 break-words font-[var(--fonte-titulo)] text-base font-semibold leading-snug text-wrap-balance line-clamp-3">
          {publicacao.titulo}
        </p>
        <p className="mt-1 min-w-0 break-words text-sm text-[var(--cor-texto-suave)]">por {publicacao.autor_nome}</p>
      </Card>
    </Link>
  );
}

type FiltroTipo = "todas" | "opiniao" | "analise";

/** Linha da tabela: Publicacao + assinatura de índice exigida pelo DataTable. */
type LinhaPublicacao = api.Publicacao & { [chave: string]: unknown };

function ConteudoComunidade() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const tipoParam = searchParams.get("tipo");
  const filtro: FiltroTipo = tipoParam === "opiniao" || tipoParam === "analise" ? tipoParam : "todas";

  const destaques = usePublicacoes({ destaque: true });
  const lista = usePublicacoes();

  function trocarFiltro(valor: string) {
    const params = new URLSearchParams(searchParams.toString());
    if (valor === "todas") params.delete("tipo");
    else params.set("tipo", valor);
    const qs = params.toString();
    router.replace(`/comunidade${qs ? `?${qs}` : ""}`, { scroll: false });
  }

  const publicacoesFiltradas: LinhaPublicacao[] = useMemo(() => {
    const todas = (lista.data ?? []) as LinhaPublicacao[];
    if (filtro === "todas") return todas;
    return todas.filter((p) => p.tipo === filtro);
  }, [lista.data, filtro]);

  const colunas: LegacyColumnDef<LinhaPublicacao>[] = useMemo(
    () => [
      {
        id: "titulo",
        header: "Título",
        accessorKey: "titulo",
        enableSorting: true,
        cell: (info) => {
          const row = info.row.original;
          return (
            <Link
              href={`/comunidade/${row.id}`}
              className="min-w-0 break-words font-medium text-[var(--cor-primaria)] hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] line-clamp-2"
            >
              {row.titulo}
            </Link>
          );
        },
      },
      {
        id: "tipo",
        header: "Tipo",
        accessorKey: "tipo",
        enableSorting: true,
        cell: (info) => {
          const row = info.row.original;
          return (
            <Badge variant={row.tipo === "opiniao" ? "default" : "secondary"} className="min-h-0">
              {row.tipo === "opiniao" ? "Opinião" : "Análise"}
            </Badge>
          );
        },
      },
      {
        id: "autor_nome",
        header: "Autoria",
        accessorKey: "autor_nome",
        enableSorting: true,
        cell: (info) => (
          <span className="min-w-0 break-words text-sm">{info.row.original.autor_nome}</span>
        ),
      },
      {
        id: "publicado_em",
        header: "Publicada em",
        accessorKey: "publicado_em",
        enableSorting: true,
        cell: (info) => {
          const row = info.row.original;
          return (
            <span className="whitespace-nowrap text-sm tabular-nums text-[var(--cor-texto-suave)]">
              {formatarData(row.publicado_em ?? row.criado_em)}
            </span>
          );
        },
      },
    ],
    []
  );

  return (
    <div className="min-w-0 w-full max-w-full space-y-6 overflow-hidden">
      <header className="min-w-0 space-y-2 overflow-hidden">
        <p className="text-xs font-bold uppercase tracking-[0.14em] text-[var(--cor-primaria)]">Vozes</p>
        <h1 className="font-[var(--fonte-titulo)] text-3xl font-extrabold tracking-tight text-wrap-balance">
          Comunidade
        </h1>
        <p className="max-w-[62ch] break-words text-sm leading-relaxed text-[var(--cor-texto-suave)]">
          Opiniões e análises de autores credenciados — sempre identificadas como tal, nunca confundidas com a
          cobertura factual do feed.{" "}
          <Link href="/comunidade/nova" className="font-medium text-[var(--cor-primaria)] hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]">
            Publique sua análise
          </Link>
        </p>
        <Button asChild className="mt-2">
          <Link href="/comunidade/nova">Publique sua análise</Link>
        </Button>
      </header>

      {destaques.data && destaques.data.length > 0 && (
        <section className="min-w-0 space-y-4 overflow-hidden" aria-label="Destaques editoriais">
          <div className="flex min-w-0 items-baseline gap-3 border-b-2 border-[var(--cor-borda)] pb-3">
            <h2 className="break-words font-[var(--fonte-titulo)] text-xl font-extrabold tracking-tight text-wrap-balance">
              Destaques editoriais
            </h2>
          </div>
          <div className="grid w-full max-w-full grid-cols-1 gap-4 overflow-hidden break-words sm:grid-cols-2 lg:grid-cols-3">
            {destaques.data.map((publicacao) => (
              <div key={publicacao.id} className="min-w-0 overflow-hidden break-words">
                <CartaoPublicacao publicacao={publicacao} />
              </div>
            ))}
          </div>
        </section>
      )}

      <section className="min-w-0 space-y-4 overflow-hidden" aria-label="Todas as publicações">
        <div className="flex min-w-0 flex-wrap items-baseline justify-between gap-3 border-b-2 border-[var(--cor-borda)] pb-3">
          <h2 className="break-words font-[var(--fonte-titulo)] text-xl font-extrabold tracking-tight text-wrap-balance">
            Todas as publicações
          </h2>
        </div>
        <Tabs value={filtro} onValueChange={trocarFiltro} className="min-w-0">
          <TabsList aria-label="Filtrar por tipo de publicação">
            <TabsTrigger value="todas">Todas</TabsTrigger>
            <TabsTrigger value="opiniao">Opinião</TabsTrigger>
            <TabsTrigger value="analise">Análise</TabsTrigger>
          </TabsList>
        </Tabs>
        <div aria-live="polite" aria-busy={lista.isLoading || undefined} className="min-w-0">
          {lista.isLoading && <SkeletonLista quantidade={4} />}
          {lista.isError && (
            <ErrorState
              mensagem={lista.error instanceof Error ? lista.error.message : "Não foi possível carregar a comunidade."}
              aoTentarNovamente={() => void lista.refetch()}
            />
          )}
          {!lista.isLoading && !lista.isError && publicacoesFiltradas.length === 0 && (
            <EmptyState titulo="Nenhuma publicação aqui ainda" descricao="Ajuste o filtro ou volte em breve para ler as análises." />
          )}
        </div>
        {!lista.isLoading && !lista.isError && publicacoesFiltradas.length > 0 && (
          <div className={cn("min-w-0 overflow-x-auto")}>
            <DataTable
              columns={colunas}
              data={publicacoesFiltradas}
              pageSize={10}
              searchable
              searchKey="busca"
              searchPlaceholder="Buscar publicações…"
              onRowClick={(row) => router.push(`/comunidade/${row.id}`)}
            />
          </div>
        )}
      </section>
    </div>
  );
}

export default function PaginaComunidade() {
  return (
    <Suspense fallback={<SkeletonLista quantidade={4} />}>
      <ConteudoComunidade />
    </Suspense>
  );
}
