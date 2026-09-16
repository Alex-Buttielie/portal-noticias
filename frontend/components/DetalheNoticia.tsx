"use client";

import { useEffect } from "react";
import Link from "next/link";
import { Clock, FileText } from "lucide-react";
import * as api from "@/lib/api";
import { useDetalheCluster, useDetalheItem, useFeed } from "@/lib/queries";
import * as intencao from "@/lib/intent";
import { obterVisualCategoria } from "@/lib/categoryVisuals";
import Badge from "@/components/Badge";
import { ReadingProgress } from "@/components/ui/ReadingProgress";
import { ShareButtons } from "@/components/ui/ShareButtons";
import { CompactNewsCard } from "@/components/ui/Cards";
import { EmptyState, ErrorState, SkeletonCard } from "@/components/ui/Estados";
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
  if (Number.isNaN(data.getTime())) return <span>{timestamp}</span>;
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

  useEffect(() => {
    if (detalhe) intencao.registrarLeitura(detalhe.categoria);
  }, [detalhe?.categoria, detalhe?.id]);

  if (consulta.isLoading && !detalhe) {
    return (
      <div aria-live="polite" aria-busy="true">
        <span className="sr-only botao--medio">Carregando notícia…</span>
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

  return (
    <>
      <ReadingProgress />
      <article className={cn("animate-in fade-in duration-300 motion-reduce:animate-none")}>
        {detalhe.exibir_publicidade && (
          <div className={cn("mb-4 rounded-lg border border-[var(--cor-borda)] border-l-[3px] bg-[var(--cor-fundo-card)] px-3 py-2 text-xs text-[var(--cor-texto-suave)]")}>
            Espaço publicitário — assine o Premium para navegar sem anúncios.
          </div>
        )}
<nav className={cn("mb-3 flex items-center gap-2 text-xs text-[var(--cor-texto-suave)]")} aria-label="Você está aqui">
          <Link href="/" className={cn("hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] rounded-sm")}>
            Início
          </Link>
          <span aria-hidden="true">/</span>
          <Link
            href={`/?categoria=${encodeURIComponent(detalhe.categoria)}`}
            className={cn("hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] rounded-sm")}
          >
            {detalhe.categoria}
          </Link>
          <span aria-hidden="true">/</span>
          <span aria-current="page" className="text-[var(--cor-texto-suave)] cartao-meta etiqueta-urgente">
            Esta notícia
          </span>
        </nav>
        <div className={cn("mb-3 flex flex-wrap items-center gap-2")}>
          {detalhe.urgente && (
            <span className={cn("inline-flex items-center rounded bg-[var(--cor-erro)] px-1.5 py-0.5 text-xs font-bold uppercase text-white")}>
              Urgente
            </span>
          )}
          {detalhe.categoria && (
            <Badge variante="neutro" className={cn("gap-1")}>
              <span aria-hidden="true">{visual.emoji}</span>
              {detalhe.categoria}
            </Badge>
          )}
<span className={cn("text-xs text-[var(--cor-texto-suave)]")}>
            <DataPublicacao timestamp={detalhe.timestamp} />
          </span>
        </div>
        <h1 className={cn("font-[var(--fonte-titulo,Georgia)] text-3xl font-bold leading-tight tracking-[-0.025em] text-wrap-balance")}>
          {detalhe.titulo}
        </h1>

        <div className={cn("mt-3 flex items-center gap-2 text-xs text-[var(--cor-texto-suave)]")}>
          <span className={cn("inline-flex items-center gap-1")}>
            <Clock className="h-3.5 w-3.5" aria-hidden="true" />
            {estimarTempoLeitura(detalhe)} min de leitura
          </span>
          <span aria-hidden="true">·</span>
          <span className={cn("inline-flex items-center gap-1")}>
            <FileText className="h-3.5 w-3.5" aria-hidden="true" />
            {detalhe.fontes.length} {detalhe.fontes.length === 1 ? "fonte" : "fontes"}
          </span>
        </div>
        {urlCanonica && (
          <div className="mt-4">
            <ShareButtons titulo={detalhe.titulo} texto={detalhe.fontes[0]?.resumo} url={urlCanonica} />
          </div>
        )}

<h2 className={cn("mt-6 text-base font-semibold")}>Por que confiar</h2>
        <div className={cn("mt-2 rounded-lg border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] p-4 shadow-sm border-l-[3px]")} style={{ borderLeftColor: visual.cor }}>
          <p className={cn("text-sm leading-relaxed")}>
            Apuramos esta notícia em {detalhe.fontes.length} {detalhe.fontes.length === 1 ? "fonte independente" : "fontes independentes"}. Você
            pode conferir cada uma abaixo e ler a matéria original.
          </p>
        </div>
        <h2 className={cn("mt-6 text-base font-semibold")}>Fontes ({detalhe.fontes.length})</h2>
        {detalhe.fontes.map((fonte, indice) => (
          <div
            key={`${fonte.url_fonte_original}-${indice}`}
            className={cn("mt-3 rounded-lg border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] p-4 shadow-sm border-l-[3px]")}
            style={{ borderLeftColor: visual.cor }}
          >
            <div className={cn("mb-1 text-sm font-semibold")}>
              <strong>{fonte.nome_fonte}</strong>
            </div>
<p className={cn("text-sm leading-relaxed text-[var(--cor-texto-suave)]")}>{fonte.resumo}</p>
            <a
              href={fonte.url_fonte_original}
              target="_blank"
              rel="noopener noreferrer"
              className={cn(
                "mt-2 inline-flex text-sm font-medium text-[var(--cor-primaria)] hover:underline",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] rounded-sm"
              )}
            >
              Ler matéria original em {fonte.nome_fonte}
            </a>
          </div>
        ))}
      </article>

      <nav className={cn("mt-8 space-y-6")} aria-label="Continue explorando">
        <Link
          href="/"
          className={cn(
            "inline-flex h-10 items-center justify-center rounded-md border border-[var(--cor-borda)] bg-white px-4 text-sm font-medium",
            "hover:bg-[var(--cor-primaria-suave)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] focus-visible:ring-offset-2",
            "motion-reduce:transition-none transition-colors"
          )}
        >
          ← Voltar ao feed
        </Link>
        {relacionados.length > 0 && (
          <section aria-label="Continue explorando">
            <p className={cn("text-xs font-semibold uppercase tracking-widest text-[var(--cor-texto-suave)]")}>O rio continua</p>
            <h2 className={cn("mt-1 font-[var(--fonte-titulo,Georgia)] text-lg font-bold tracking-[-0.01em]")}>Continue explorando</h2>
            <div className={cn("mt-3 grid gap-3")}>
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
