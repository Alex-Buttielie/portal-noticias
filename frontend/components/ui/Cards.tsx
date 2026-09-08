import Link from "next/link";
import type { FeedEntrada } from "@/lib/api";
import { obterVisualCategoria } from "@/lib/categoryVisuals";
import BotaoSalvar from "@/components/BotaoSalvar";

function hrefDaEntrada(entrada: FeedEntrada): string {
  return entrada.tipo === "cluster" ? `/noticia/cluster/${entrada.id}` : `/noticia/item/${entrada.id}`;
}

function Meta({ entrada }: { entrada: FeedEntrada }) {
  const data = new Date(entrada.timestamp);
  const dataValida = !Number.isNaN(data.getTime());
  return (
    <p className="cartao-noticia__meta">
      <span>{entrada.categoria}</span>
      {entrada.urgente && <span className="etiqueta-urgente">Urgente</span>}
      {entrada.numero_fontes > 1 && <span>{entrada.numero_fontes} fontes</span>}
      {dataValida && (
        <time dateTime={entrada.timestamp}>
          {data.toLocaleDateString("pt-BR", { day: "2-digit", month: "short" })}
        </time>
      )}
    </p>
  );
}

export function NewsCard({ entrada }: { entrada: FeedEntrada }) {
  const visual = obterVisualCategoria(entrada.categoria);
  return (
    <article className="cartao-noticia">
      <Link href={hrefDaEntrada(entrada)} className="cartao-noticia__imagem" style={{ background: visual.gradiente }} aria-hidden="true" tabIndex={-1}>
        <span>{visual.emoji}</span>
      </Link>
      <div className="cartao-noticia__corpo">
        <Meta entrada={entrada} />
        <h3 className="cartao-noticia__titulo">
          <Link href={hrefDaEntrada(entrada)}>{entrada.titulo}</Link>
        </h3>
        <p className="cartao-noticia__resumo limitar-linhas-3">{entrada.resumo}</p>
        <BotaoSalvar entrada={entrada} />
      </div>
    </article>
  );
}

export function FeaturedNewsCard({ entrada }: { entrada: FeedEntrada }) {
  const visual = obterVisualCategoria(entrada.categoria);
  return (
    <article className="cartao-noticia cartao-noticia--destaque">
      <Link href={hrefDaEntrada(entrada)} className="cartao-noticia__imagem cartao-noticia__imagem--grande" style={{ background: visual.gradiente }} aria-hidden="true" tabIndex={-1}>
        <span>{visual.emoji}</span>
      </Link>
      <div className="cartao-noticia__corpo">
        <Meta entrada={entrada} />
        <h2 className="cartao-noticia__titulo cartao-noticia__titulo--grande">
          <Link href={hrefDaEntrada(entrada)}>{entrada.titulo}</Link>
        </h2>
        <p className="cartao-noticia__resumo limitar-linhas-4">{entrada.resumo}</p>
        <BotaoSalvar entrada={entrada} />
      </div>
    </article>
  );
}

export function CompactNewsCard({ entrada }: { entrada: FeedEntrada }) {
  return (
    <article className="cartao-noticia cartao-noticia--compacto">
      <Meta entrada={entrada} />
      <h3 className="cartao-noticia__titulo">
        <Link href={hrefDaEntrada(entrada)}>{entrada.titulo}</Link>
      </h3>
    </article>
  );
}

export function HorizontalNewsCard({ entrada, posicao }: { entrada: FeedEntrada; posicao?: number }) {
  return (
    <article className="cartao-noticia cartao-noticia--horizontal">
      {typeof posicao === "number" && <span className="cartao-noticia__posicao" aria-hidden="true">{posicao}</span>}
      <div>
        <Meta entrada={entrada} />
        <h3 className="cartao-noticia__titulo">
          <Link href={hrefDaEntrada(entrada)}>{entrada.titulo}</Link>
        </h3>
      </div>
    </article>
  );
}
