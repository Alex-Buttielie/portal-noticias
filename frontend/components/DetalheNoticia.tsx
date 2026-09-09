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

// Página de notícia em tipografia editorial: coluna de leitura em 68ch
// (`.artigo-corpo`), capitular no primeiro parágrafo (`.detalhe-dropcap`,
// ver css-needs), compartilhar em faixa fixa — dados e rotas inalterados.
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
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

        <header>
          <p className="cartao-noticia__meta" style={{ marginBottom: "var(--espaco-3)" }}>
            {detalhe.urgente && <Badge variante="erro">Urgente</Badge>}
            {detalhe.categoria && (
              <Badge variante="neutro">
                <span className="cartao-emoji" aria-hidden="true">
                  {visual.emoji}
                </span>{" "}
                {detalhe.categoria}
              </Badge>
            )}
            <time dateTime={detalhe.timestamp}>{formatarData(detalhe.timestamp)}</time>
          </p>
          <h1 style={{ fontSize: "clamp(1.9rem, 1.4rem + 2.4vw, 2.9rem)", maxWidth: "22ch" }}>
            {detalhe.titulo}
          </h1>
          <div className="info-leitura" style={{ marginTop: "var(--espaco-2)" }}>
            <span>{estimarTempoLeitura(detalhe)} min de leitura</span>
            <span aria-hidden="true">·</span>
            <span>
              {detalhe.fontes.length} {detalhe.fontes.length === 1 ? "fonte" : "fontes"}
            </span>
          </div>
        </header>

        {urlCanonica && (
          <div
            className="share-sticky"
            style={{
              position: "sticky",
              top: 72,
              zIndex: 20,
              padding: "var(--espaco-2) 0",
              marginTop: "var(--espaco-3)",
            }}
          >
            <ShareButtons titulo={detalhe.titulo} texto={detalhe.fontes[0]?.resumo} url={urlCanonica} />
          </div>
        )}

        <h2 style={{ fontSize: "1rem", marginTop: "1.5rem" }}>Fontes ({detalhe.fontes.length})</h2>
        {detalhe.fontes.map((fonte, indice) => (
          <section
            className="cartao-noticia"
            style={{ marginBottom: "var(--espaco-4)", ["--acento" as string]: visual.cor }}
            key={`${fonte.url_fonte_original}-${indice}`}
            aria-label={`Fonte ${indice + 1}: ${fonte.nome_fonte}`}
          >
            <div className="cartao-noticia__corpo">
              <p className="cartao-noticia__meta">
                <strong style={{ color: "var(--cor-texto)" }}>{fonte.nome_fonte}</strong>
              </p>
              <p className={`artigo-corpo${indice === 0 ? " detalhe-dropcap" : ""}`}>{fonte.resumo}</p>
              <a href={fonte.url_fonte_original} target="_blank" rel="noopener noreferrer">
                Ler matéria original em {fonte.nome_fonte} →
              </a>
            </div>
          </section>
        ))}
      </article>

      <nav className="fluxo-leitura" aria-label="Continue explorando">
        <Link href="/" className="botao botao--fantasma botao--medio" style={{ minHeight: 44, alignSelf: "flex-start" }}>
          ← Voltar ao feed
        </Link>
        {relacionados.length > 0 && (
          <section aria-label="Continue explorando">
            <p className="secao-eyebrow">O rio continua</p>
            <h2 className="secao-titulo">Continue explorando</h2>
            <div className="lista-compacta">
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
