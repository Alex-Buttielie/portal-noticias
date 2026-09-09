"use client";
import Link from "next/link";
import type { FeedEntrada } from "@/lib/api";
import { obterVisualCategoria } from "@/lib/categoryVisuals";

function formatData(ts: string) {
  try {
    return new Date(ts).toLocaleDateString("pt-BR", { day: "2-digit", month: "short" });
  } catch {
    return ts;
  }
}

// Bloco de editoria — cabeçalho de seção + grade 3→2→1 (`.grade-noticias`
// em globals.css) com cartões 16/9, categoria, título serifado, resumo em
// 2 linhas e meta. Props e rotas inalteradas.
export default function BlocoEditoria({
  categoria,
  itens,
  onVerTodas,
}: {
  categoria: string;
  itens: FeedEntrada[];
  onVerTodas?: () => void;
}) {
  if (!itens.length) return null;
  const visual = obterVisualCategoria(categoria);
  const idTitulo = `editoria-${categoria.toLowerCase().replace(/\s+/g, "-")}`;
  const destino = `/?categoria=${encodeURIComponent(categoria)}`;

  return (
    <section className="secao-bloco" aria-labelledby={idTitulo}>
      <div className="secao-cabecalho">
        <p className="secao-eyebrow">Editoria</p>
        <h2 id={idTitulo} className="secao-titulo">
          <span
            aria-hidden="true"
            style={{
              width: 10,
              height: 10,
              borderRadius: "var(--raio-completo)",
              background: visual.cor,
              flexShrink: 0,
            }}
          />
          {categoria}
        </h2>
        {onVerTodas ? (
          <button
            type="button"
            className="secao-ver-tudo"
            style={{ minHeight: 40, background: "none", border: "none", cursor: "pointer", font: "inherit" }}
            onClick={onVerTodas}
            aria-label={`Ver todas as notícias de ${categoria}`}
          >
            Ver tudo →
          </button>
        ) : (
          <Link href={destino} className="secao-ver-tudo" aria-label={`Ver todas as notícias de ${categoria}`}>
            Ver tudo →
          </Link>
        )}
      </div>
      <div className="grade-noticias">
        {itens.slice(0, 3).map((e) => {
          const itemVisual = obterVisualCategoria(e.categoria);
          const href = `/noticia/${e.tipo}/${e.id}`;
          return (
            <article key={`${e.tipo}-${e.id}`} className="card-noticia">
              <Link
                href={href}
                className="card-noticia-imagem"
                style={{ background: itemVisual.gradiente, aspectRatio: "16 / 9", height: "auto" }}
                aria-hidden="true"
                tabIndex={-1}
              >
                <span aria-hidden="true" style={{ fontSize: "2rem" }}>
                  {itemVisual.emoji}
                </span>
              </Link>
              <div className="card-noticia-corpo">
                <p className="card-noticia-categoria" style={{ color: itemVisual.cor }}>
                  {e.categoria}
                  {e.urgente && (
                    <span className="etiqueta-urgente" style={{ marginLeft: "0.5rem" }}>
                      Urgente
                    </span>
                  )}
                </p>
                <h3
                  className="card-noticia-titulo limitar-linhas-3"
                  style={{ fontSize: "clamp(1.05rem, 1rem + 0.6vw, 1.3rem)" }}
                >
                  <Link href={href} style={{ color: "inherit", textDecoration: "none" }}>
                    {e.titulo}
                  </Link>
                </h3>
                <p className="card-noticia-resumo limitar-linhas-2">{e.resumo}</p>
                <p className="card-noticia-meta">
                  <time dateTime={e.timestamp}>{formatData(e.timestamp)}</time>
                  <span aria-hidden="true">·</span>
                  <span>{e.numero_fontes} fontes</span>
                </p>
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}
