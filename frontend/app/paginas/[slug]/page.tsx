"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import * as api from "@/lib/api";

export default function PaginaEditorialPage() {
  const params = useParams<{ slug: string }>();
  const [pagina, setPagina] = useState<api.PaginaEditorial | null>(null);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    if (!params.slug) return;
    setCarregando(true);
    setErro(null);
    api
      .obterPaginaEditorial(params.slug)
      .then(setPagina)
      .catch((e: unknown) => {
        setErro(
          e instanceof api.ApiError && e.status === 404
            ? "Página não encontrada."
            : "Não foi possível carregar esta página."
        );
      })
      .finally(() => setCarregando(false));
  }, [params.slug]);

  if (carregando) return <p className="texto-suave">Carregando...</p>;
  if (erro) return <p className="mensagem-erro">{erro}</p>;
  if (!pagina) return null;

  return (
    <div className="pagina-editorial">
      <h1>{pagina.titulo}</h1>
      <p className="texto-suave">
        Atualizado em {new Date(pagina.atualizado_em).toLocaleDateString("pt-BR")}
      </p>
      {pagina.conteudo.split("\n\n").map((paragrafo, indice) => (
        <p key={indice} style={{ whiteSpace: "pre-line", marginTop: "1rem" }}>
          {paragrafo}
        </p>
      ))}
    </div>
  );
}
