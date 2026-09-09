import Link from "next/link";
import type { CSSProperties } from "react";
import type { FeedEntrada } from "@/lib/api";
import { obterVisualCategoria } from "@/lib/categoryVisuals";
import BotaoSalvar from "@/components/BotaoSalvar";

function hrefDaEntrada(entrada: FeedEntrada): string {
  return entrada.tipo === "cluster" ? `/noticia/cluster/${entrada.id}` : `/noticia/item/${entrada.id}`;
}

function formatarData(timestamp: string): string | null {
  const data = new Date(timestamp);
  if (Number.isNaN(data.getTime())) return null;
  return data.toLocaleDateString("pt-BR", { day: "2-digit", month: "short" });
}

// Linha de categoria + selo + fontes + data — mesma em todos os cartões.
function Meta({ entrada }: { entrada: FeedEntrada }) {
  const data = formatarData(entrada.timestamp);
  return (
    <p className="cartao-noticia__meta">
      <span>{entrada.categoria}</span>
      {entrada.urgente && <span className="etiqueta-urgente">Urgente</span>}
      {entrada.numero_fontes > 1 && <span>{entrada.numero_fontes} fontes</span>}
      {data && <time dateTime={entrada.timestamp}>{data}</time>}
    </p>
  );
}

// Faixa 16/9 decorativa (o feed não entrega imagem) — gradiente + emoji da editoria.
function FaixaImagem({ entrada, grande = false }: { entrada: FeedEntrada; grande?: boolean }) {
  const visual = obterVisualCategoria(entrada.categoria);
  return (
    <Link
      href={hrefDaEntrada(entrada)}
      className={grande ? "cartao-noticia__imagem cartao-noticia__imagem--grande" : "cartao-noticia__imagem"}
      style={{ background: visual.gradiente, aspectRatio: "16 / 9", minHeight: 0 }}
      aria-hidden="true"
      tabIndex={-1}
    >
      <span aria-hidden="true">{visual.emoji}</span>
    </Link>
  );
}

const estiloTitulo: CSSProperties = { fontSize: "clamp(1.05rem, 1rem + 0.6vw, 1.3rem)" };

export function NewsCard({ entrada }: { entrada: FeedEntrada }) {
  return (
    <article className="cartao-noticia">
      <FaixaImagem entrada={entrada} />
      <div className="cartao-noticia__corpo">
        <Meta entrada={entrada} />
        <h3 className="cartao-noticia__titulo limitar-linhas-3" style={estiloTitulo}>
          <Link href={hrefDaEntrada(entrada)}>{entrada.titulo}</Link>
        </h3>
        <p className="cartao-noticia__resumo limitar-linhas-2">{entrada.resumo}</p>
        <BotaoSalvar entrada={entrada} />
      </div>
    </article>
  );
}

export function FeaturedNewsCard({ entrada }: { entrada: FeedEntrada }) {
  return (
    <article className="cartao-noticia cartao-noticia--destaque">
      <FaixaImagem entrada={entrada} grande />
      <div className="cartao-noticia__corpo">
        <Meta entrada={entrada} />
        <h2
          className="cartao-noticia__titulo cartao-noticia__titulo--grande limitar-linhas-3"
          style={{ fontSize: "clamp(1.35rem, 1.2rem + 1.2vw, 1.9rem)" }}
        >
          <Link href={hrefDaEntrada(entrada)}>{entrada.titulo}</Link>
        </h2>
        <p className="cartao-noticia__resumo limitar-linhas-2">{entrada.resumo}</p>
        <BotaoSalvar entrada={entrada} />
      </div>
    </article>
  );
}

export function CompactNewsCard({ entrada }: { entrada: FeedEntrada }) {
  return (
    <article className="cartao-noticia cartao-noticia--compacto">
      <Meta entrada={entrada} />
      <h3 className="cartao-noticia__titulo limitar-linhas-2">
        <Link href={hrefDaEntrada(entrada)}>{entrada.titulo}</Link>
      </h3>
    </article>
  );
}

export function HorizontalNewsCard({ entrada, posicao }: { entrada: FeedEntrada; posicao?: number }) {
  return (
    <article className="cartao-noticia cartao-noticia--horizontal">
      {typeof posicao === "number" && (
        <span className="cartao-noticia__posicao" aria-hidden="true">
          {posicao}
        </span>
      )}
      <div>
        <Meta entrada={entrada} />
        <h3 className="cartao-noticia__titulo limitar-linhas-2">
          <Link href={hrefDaEntrada(entrada)}>{entrada.titulo}</Link>
        </h3>
      </div>
    </article>
  );
}
