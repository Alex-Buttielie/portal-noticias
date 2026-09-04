"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import * as api from "@/lib/api";

function CartaoPublicacao({ publicacao }: { publicacao: api.Publicacao }) {
  return (
    <Link href={`/comunidade/${publicacao.id}`} style={{ textDecoration: "none", color: "inherit" }}>
      <article className="cartao">
        <div className="cartao-meta">
          <span className="badge-categoria">{publicacao.tipo === "opiniao" ? "Opinião" : "Análise"}</span>
          {publicacao.categoria && <span className="badge-categoria">{publicacao.categoria}</span>}
        </div>
        <h2 className="cartao-titulo">{publicacao.titulo}</h2>
        <p className="texto-suave">por {publicacao.autor_nome}</p>
      </article>
    </Link>
  );
}

export default function PaginaComunidade() {
  const [publicacoes, setPublicacoes] = useState<api.Publicacao[]>([]);
  const [destaques, setDestaques] = useState<api.Publicacao[]>([]);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    // BRD seção 12 — "Destaques editoriais" é um item explícito do que a
    // Comunidade deve oferecer. Gap real encontrado na análise do BRD: o
    // backend já suportava `?destaque=true` desde sempre, mas nenhuma tela
    // usava esse filtro — publicações marcadas como destaque pelo admin
    // ficavam misturadas na lista comum, sem nenhum destaque visual.
    api
      .obterPublicacoes({ destaque: true })
      .then(setDestaques)
      .catch(() => {
        // destaques são um extra da tela — falha aqui não impede ver a lista completa
      });
    api
      .obterPublicacoes()
      .then(setPublicacoes)
      .catch((e: unknown) => {
        setErro(e instanceof api.ApiError ? e.message : "Não foi possível carregar a comunidade.");
      })
      .finally(() => setCarregando(false));
  }, []);

  return (
    <div>
      <h1>Comunidade — Opiniões e Análises</h1>
      <p className="texto-suave">
        Conteúdo de autores credenciados. Opinião e análise são sempre identificadas como tal —
        nunca confunda com a cobertura factual do feed.
      </p>

      {erro && <p className="mensagem-erro">{erro}</p>}
      {carregando && <p className="texto-suave">Carregando...</p>}

      {destaques.length > 0 && (
        <>
          <h2 style={{ fontSize: "1.1rem", marginTop: "1.5rem" }}>Destaques editoriais</h2>
          {destaques.map((publicacao) => (
            <CartaoPublicacao key={publicacao.id} publicacao={publicacao} />
          ))}
        </>
      )}

      {!carregando && publicacoes.length === 0 && (
        <p className="texto-suave">Nenhuma publicação ainda.</p>
      )}

      {publicacoes.length > 0 && destaques.length > 0 && (
        <h2 style={{ fontSize: "1.1rem", marginTop: "1.5rem" }}>Todas as publicações</h2>
      )}
      {publicacoes.map((publicacao) => (
        <CartaoPublicacao key={publicacao.id} publicacao={publicacao} />
      ))}
    </div>
  );
}
