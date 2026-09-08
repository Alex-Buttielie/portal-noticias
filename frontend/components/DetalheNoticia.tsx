"use client";

import { useEffect } from "react";
import Link from "next/link";
import * as api from "@/lib/api";
import { useDetalheCluster, useDetalheItem, useFeed } from "@/lib/queries";
import * as intencao from "@/lib/intent";
import { obterVisualCategoria } from "@/lib/categoryVisuals";
import Badge from "@/components/Badge";
import { ReadingProgress } from "@/components/ui/ReadingProgress";
import { ShareButtons } from "@/components/ui/ShareButtons";
import { CompactNewsCard } from "@/components/ui/Cards";
import { EmptyState, ErrorState, SkeletonCard } from "@/components/ui/Estados";

function formatarData(timestamp: string): string {
  try {
    return new Date(timestamp).toLocaleString("pt-BR", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return timestamp;
  }
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
        <span className="visualmente-oculto">Carregando notícia…</span>
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
      <article style={{ animation: "entrada-suave var(--duracao-lenta) var(--curva-padrao) both" }}>
        {detalhe.exibir_publicidade && (
          <div className="faixa-publicidade">
            Espaço publicitário — assine o Premium para navegar sem anúncios.
          </div>
        )}
        <div className="cartao-meta">
          {detalhe.urgente && <Badge variante="erro">Urgente</Badge>}
          {detalhe.categoria && (
            <Badge variante="neutro">
              <span className="cartao-emoji" aria-hidden="true">
                {visual.emoji}
              </span>
              {detalhe.categoria}
            </Badge>
          )}
          <span>{formatarData(detalhe.timestamp)}</span>
        </div>
        <h1>{detalhe.titulo}</h1>

        <div className="info-leitura">
          <span>{estimarTempoLeitura(detalhe)} min de leitura</span>
          <span aria-hidden="true">·</span>
          <span>{detalhe.fontes.length} {detalhe.fontes.length === 1 ? "fonte" : "fontes"}</span>
        </div>
        {urlCanonica && (
          <ShareButtons titulo={detalhe.titulo} texto={detalhe.fontes[0]?.resumo} url={urlCanonica} />
        )}

        <h2 style={{ fontSize: "1rem", marginTop: "1.5rem" }}>
          Fontes ({detalhe.fontes.length})
        </h2>
        {detalhe.fontes.map((fonte, indice) => (
          <div
            className="cartao cartao-acento"
            style={{ ["--acento" as string]: visual.cor }}
            key={`${fonte.url_fonte_original}-${indice}`}
          >
            <div className="cartao-meta">
              <strong>{fonte.nome_fonte}</strong>
            </div>
            <p className="artigo-corpo" style={{ fontSize: "1rem" }}>
              {fonte.resumo}
            </p>
            <a href={fonte.url_fonte_original} target="_blank" rel="noopener noreferrer">
              Ler matéria original em {fonte.nome_fonte} →
            </a>
          </div>
        ))}
      </article>

      <nav className="fluxo-leitura" aria-label="Continue explorando">
        <Link href="/" className="botao botao--fantasma botao--medio">
          ← Voltar ao feed
        </Link>
        {relacionados.length > 0 && (
          <section aria-label="Continue explorando">
            <p className="secao-eyebrow">O rio continua</p>
            <h2 className="secao-titulo">Continue explorando</h2>
            <div className="lista-compacta">
              {relacionados.map((entrada) => (
                <CompactNewsCard
                  key={`${entrada.tipo}-${entrada.id}`}
                  entrada={entrada}
                />
              ))}
            </div>
          </section>
        )}
      </nav>
    </>
  );
}
