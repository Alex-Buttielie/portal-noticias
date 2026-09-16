"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import * as api from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Cards";
import { ErrorState, LoadingSpinner } from "@/components/ui/Estados";
import { cn } from "@/lib/utils";

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
          e instanceof api.ApiError && e.status === 404 ? "Página não encontrada." : "Não foi possível carregar esta página."
        );
      })
      .finally(() => setCarregando(false));
  }, [params.slug]);

  if (carregando)
    return (
      <div className={cn("container mx-auto max-w-2xl px-4 py-10")}>
        <LoadingSpinner rotulo="Carregando página…" />
      </div>
    );
  if (erro)
    return (
      <div className={cn("container mx-auto max-w-2xl px-4 py-10")}>
        <ErrorState mensagem={erro} />
      </div>
    );
  if (!pagina) return null;

  return (
<div className={cn("container mx-auto max-w-3xl px-4 py-8 sm:px-6")}>
      <Card className="shadow-sm container--estreito secao-bloco">
        <CardHeader className="space-y-2">
          <p className="text-xs font-bold uppercase tracking-widest text-[var(--cor-primaria)] secao-eyebrow">Institucional</p>
          <CardTitle id="pagina-editorial-titulo" className="text-3xl leading-tight">
            {pagina.titulo}
          </CardTitle>
          <p className="text-sm text-[var(--cor-texto-suave)]">Atualizado em {new Date(pagina.atualizado_em).toLocaleDateString("pt-BR")}</p>
        </CardHeader>
        <CardContent className="grid gap-4">
          {pagina.conteudo.split("\n\n").map((paragrafo, indice) => (
            <p key={indice} className="whitespace-pre-line text-sm leading-relaxed text-[var(--cor-texto)]">
              {paragrafo}
            </p>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
