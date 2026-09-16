"use client";

import { useEffect } from "react";
import Link from "next/link";
import { Clock, FileText } from "lucide-react";
import * as api from "@/lib/api";
import { useDetalheCluster, useDetalheItem, useFeed } from "@/lib/queries";
import * as intencao from "@/lib/intent";
import { obterVisualCategoria } from "@/lib/categoryVisuals";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ReadingProgress } from "@/components/ui/ReadingProgress";
import { ShareButtons } from "@/components/ui/ShareButtons";
import { Prose } from "@/components/ui/prose";
import { CompactNewsCard } from "@/components/ui/Cards";
import { EmptyState, ErrorState, SkeletonCard } from "@/components/ui/Estados";
import PorQueEstouVendoIsso from "@/components/PorQueEstouVendoIsso";
import { cn } from "@/lib/utils";

const formatoDataHora = new Intl.DateTimeFormat("pt-BR", {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});

function DataPublicacao({ timestamp }: { timestamp: string }) {
  const data = new Date(timestamp);
  if (Number.isNaN(data.getTime())) return <span className="min-w-0 break-words">{timestamp}</span>;
  return <time dateTime={timestamp}>{formatoDataHora.format(data)}</time>;
}

const PALAVRAS_POR_MINUTO = 200;

function estimarTempoLeitura(detalhe: api.FeedDetalhe): number {
  const palavras = detalhe.fontes.reduce(
    (total, fonte) => total + fonte.resumo.split(/\s+/).filter(Boolean).length,
    detalhe.titulo.split(/\s+/).filter(Boolean).length
  );
  return Math.max(1, Math.round(palavras / PALAVRAS_POR_MINUTO));
}

export default function DetalheNoticia({
  tipo,
  id,
  inicial,
}: {
  tipo: "cluster" | "item";
  id: string;
  inicial?: api.FeedDetalhe | null;
}) {
  const consulta = tipo === "cluster" ? useDetalheCluster(id, inicial) : useDetalheItem(id, inicial);
  const detalhe = consulta.data ?? inicial ?? null;
  const relacionadosQuery = useFeed({ categoria: detalhe?.categoria || undefined, enabled: Boolean(detalhe) });
  const relacionados = ((relacionadosQuery.data?.pages ?? []).flatMap((p) => p.results) as api.FeedEntrada[])
    .filter((e) => !(e.tipo === detalhe?.tipo && e.id === detalhe?.id))
    .slice(0, 3);

  const categoriaDetalhe = detalhe?.categoria;
  const idDetalhe = detalhe?.id;
  useEffect(() => {
    if (detalhe && categoriaDetalhe) intencao.registrarLeitura(categoriaDetalhe);
  }, [detalhe, categoriaDetalhe, idDetalhe]);

  if (consulta.isLoading && !detalhe) {
    return (
      <div aria-live="polite" aria-busy="true">
        <span className="sr-only">Carregando notícia…</span>
        <SkeletonCard />
      </div>
    );
  }

  if (consulta.isError && !detalhe) {
    const erro = consulta.error;
    if (erro instanceof api.ApiError && erro.status === 404) {
      return <EmptyState titulo="Notícia não encontrada" descricao="Ela pode ter sido removida ou ainda estar em revisão." />;
    }
    return (
      <ErrorState
        mensagem={erro instanceof api.ApiError ? erro.message : "Não foi possível carregar esta notícia."}
        aoTentarNovamente={() => void consulta.refetch()}
      />
    );
  }

  if (!detalhe) {
    return <EmptyState titulo="Notícia não encontrada" descricao="Ela pode ter sido removida ou ainda estar em revisão." />;
  }

  const visual = obterVisualCategoria(detalhe.categoria);
  const urlCanonica = typeof window !== "undefined" ? window.location.href : "";
  const motivos = [
    ...(detalhe.urgente ? ["Marcada como urgente pela redação."] : []),
    ...(detalhe.fontes.length >= 3
      ? [`Confirmada por ${detalhe.fontes.length} fontes independentes.`]
      : ["Publicada recentemente no feed geral."]),
  ];

  return (
    <>
      <ReadingProgress />
      <article className="min-w-0">
        {detalhe.exibir_publicidade && (
          <div className="mb-4 rounded-lg border border-[var(--cor-borda)] border-l-[3px] border-l-[var(--cor-alerta)] bg-[var(--cor-fundo-elevado)] px-3 py-2 text-xs text-[var(--cor-texto-suave)]">
            Espaço publicitário — assine o Premium para navegar sem anúncios.
          </div>
        )}
        <nav className="mb-3 flex min-w-0 flex-wrap items-center gap-2 text-xs text-[var(--cor-texto-suave)]" aria-label="Você está aqui">
          <Link href="/" className="rounded-sm hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]">
            Início
          </Link>
          <span aria-hidden="true">/</span>
          <Link
            href={`/?categoria=${encodeURIComponent(detalhe.categoria)}`}
            className="min-w-0 break-words rounded-sm hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]"
          >
            {detalhe.categoria}
          </Link>
          <span aria-hidden="true">/</span>
          <span aria-current="page" className="min-w-0 break-words">
            Esta notícia
          </span>
        </nav>
        <div className="mb-3 flex min-w-0 flex-wrap items-center gap-2">
          {detalhe.urgente && (
            <Badge variant="destructive" className="min-h-0 uppercase">
              Urgente
            </Badge>
          )}
          {detalhe.categoria && (
            <Badge variant="secondary" className="min-h-0">
              <span aria-hidden="true">{visual.emoji}</span>
              {detalhe.categoria}
            </Badge>
          )}
          <span className="text-xs text-[var(--cor-texto-suave)]">
            <DataPublicacao timestamp={detalhe.timestamp} />
          </span>
        </div>
        <h1 className="min-w-0 break-words font-[var(--fonte-titulo)] text-3xl font-bold leading-tight tracking-tight text-wrap-balance">
          {detalhe.titulo}
        </h1>

        <div className="mt-3 flex min-w-0 flex-wrap items-center gap-2 text-xs text-[var(--cor-texto-suave)]">
          <span className="inline-flex min-w-0 items-center gap-1">
            <Clock className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
            {estimarTempoLeitura(detalhe)} min de leitura
          </span>
          <span aria-hidden="true">·</span>
          <span className="inline-flex min-w-0 items-center gap-1">
            <FileText className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
            {detalhe.fontes.length} {detalhe.fontes.length === 1 ? "fonte" : "fontes"}
          </span>
          <span aria-hidden="true">·</span>
          <PorQueEstouVendoIsso motivos={motivos} />
        </div>
        {urlCanonica && (
          <div className="mt-4">
            <ShareButtons titulo={detalhe.titulo} texto={detalhe.fontes[0]?.resumo} url={urlCanonica} />
          </div>
        )}

        <Prose className="mt-6 min-w-0">
          <h2>Por que confiar</h2>
          <p>
            Apuramos esta notícia em {detalhe.fontes.length}{" "}
            {detalhe.fontes.length === 1 ? "fonte independente" : "fontes independentes"}. Você
            pode conferir cada uma abaixo e ler a matéria original.
          </p>
        </Prose>

        <section className="mt-6 min-w-0" aria-label={`Fontes (${detalhe.fontes.length})`}>
          <h2 className="break-words font-[var(--fonte-titulo)] text-base font-semibold text-wrap-balance">
            Fontes ({detalhe.fontes.length})
          </h2>
          {detalhe.fontes.length > 1 ? (
            <Tabs defaultValue="fonte-0" className="mt-3 min-w-0">
              <TabsList aria-label="Escolha a fonte para ler o resumo">
                {detalhe.fontes.map((fonte, indice) => (
                  <TabsTrigger key={`${fonte.url_fonte_original}-${indice}`} value={`fonte-${indice}`} className="min-w-0 max-w-[160px] truncate">
                    {fonte.nome_fonte}
                  </TabsTrigger>
                ))}
              </TabsList>
              {detalhe.fontes.map((fonte, indice) => (
                <TabsContent key={`${fonte.url_fonte_original}-${indice}`} value={`fonte-${indice}`} className="min-w-0">
                  <Card className="min-w-0 border-l-[3px]" style={{ borderLeftColor: visual.cor }}>
                    <CardContent className="space-y-2 p-4">
                      <p className="min-w-0 break-words text-sm font-semibold">{fonte.nome_fonte}</p>
                      <p className="min-w-0 break-words text-sm leading-relaxed text-[var(--cor-texto-suave)]">
                        {fonte.resumo}
                      </p>
                      <a
                        href={fonte.url_fonte_original}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex min-h-[44px] touch-manipulation items-center rounded-sm text-sm font-medium text-[var(--cor-primaria)] hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]"
                      >
                        Ler matéria original em {fonte.nome_fonte}
                      </a>
                    </CardContent>
                  </Card>
                </TabsContent>
              ))}
            </Tabs>
          ) : (
            detalhe.fontes.map((fonte, indice) => (
              <Card
                key={`${fonte.url_fonte_original}-${indice}`}
                className="mt-3 min-w-0 border-l-[3px]"
                style={{ borderLeftColor: visual.cor }}
              >
                <CardContent className="space-y-2 p-4">
                  <p className="min-w-0 break-words text-sm font-semibold">{fonte.nome_fonte}</p>
                  <p className="min-w-0 break-words text-sm leading-relaxed text-[var(--cor-texto-suave)]">
                    {fonte.resumo}
                  </p>
                  <a
                    href={fonte.url_fonte_original}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex min-h-[44px] touch-manipulation items-center rounded-sm text-sm font-medium text-[var(--cor-primaria)] hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]"
                  >
                    Ler matéria original em {fonte.nome_fonte}
                  </a>
                </CardContent>
              </Card>
            ))
          )}
        </section>
      </article>

      <nav className={cn("mt-8 min-w-0 space-y-6")} aria-label="Continue explorando">
        <Link
          href="/"
          className={cn(
            "inline-flex min-h-[44px] touch-manipulation items-center justify-center rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] px-4 text-sm font-medium",
            "transition-colors hover:bg-[var(--cor-primaria-suave)] motion-reduce:transition-none",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] focus-visible:ring-offset-2"
          )}
        >
          Voltar ao feed
        </Link>
        {relacionados.length > 0 && (
          <section aria-label="Continue explorando">
            <p className="text-xs font-semibold uppercase tracking-widest text-[var(--cor-texto-suave)]">O rio continua</p>
            <h2 className="mt-1 break-words font-[var(--fonte-titulo)] text-lg font-bold text-wrap-balance">
              Continue explorando
            </h2>
            <div className="mt-3 grid min-w-0 grid-cols-1 gap-3">
              {relacionados.map((entrada) => (
                <CompactNewsCard key={`${entrada.tipo}-${entrada.id}`} entrada={entrada} />
              ))}
            </div>
          </section>
        )}
      </nav>
    </>
  );
}
