"use client";

import Link from "next/link";
import type * as api from "@/lib/api";
import { usePublicacoes } from "@/lib/queries";
import Badge from "@/components/Badge";
import { EmptyState, ErrorState, SkeletonLista } from "@/components/ui/Estados";

function CartaoPublicacao({ publicacao }: { publicacao: api.Publicacao }) {
  return (
    <Link href={`/comunidade/${publicacao.id}`} style={{ textDecoration: "none", color: "inherit" }}>
      <article className="cartao">
        <div className="cartao-meta">
          <Badge variante={publicacao.tipo === "opiniao" ? "premium" : "neutro"}>
            {publicacao.tipo === "opiniao" ? "Opinião" : "Análise"}
          </Badge>
          {publicacao.categoria && <Badge variante="neutro">{publicacao.categoria}</Badge>}
          {publicacao.destaque && <Badge variante="sucesso">Destaque editorial</Badge>}
        </div>
        <h2 className="cartao-titulo">{publicacao.titulo}</h2>
        <p className="texto-suave">por {publicacao.autor_nome}</p>
      </article>
    </Link>
  );
}

export default function PaginaComunidade() {
  const destaques = usePublicacoes({ destaque: true });
  const lista = usePublicacoes();

  return (
    <div>
      <h1>Comunidade — Opiniões e Análises</h1>
      <p className="texto-suave">
        Conteúdo de autores credenciados. Opinião e análise são sempre identificadas como tal —
        nunca confunda com a cobertura factual do feed.
      </p>

      {lista.isLoading && <SkeletonLista quantidade={4} />}
      {lista.isError && (
        <ErrorState
          mensagem={lista.error instanceof Error ? lista.error.message : "Não foi possível carregar a comunidade."}
          aoTentarNovamente={() => void lista.refetch()}
        />
      )}

      {destaques.data && destaques.data.length > 0 && (
        <>
          <h2 style={{ fontSize: "1.1rem", marginTop: "1.5rem" }}>Destaques editoriais</h2>
          {destaques.data.map((publicacao) => (
            <CartaoPublicacao key={publicacao.id} publicacao={publicacao} />
          ))}
        </>
      )}

      {!lista.isLoading && !lista.isError && lista.data?.length === 0 && (
        <EmptyState titulo="Nenhuma publicação ainda" descricao="Volte em breve para ler as análises dos jornalistas." />
      )}

      {(lista.data?.length ?? 0) > 0 && (destaques.data?.length ?? 0) > 0 && (
        <h2 style={{ fontSize: "1.1rem", marginTop: "1.5rem" }}>Todas as publicações</h2>
      )}
      {lista.data?.map((publicacao) => (
        <CartaoPublicacao key={publicacao.id} publicacao={publicacao} />
      ))}
    </div>
  );
}
