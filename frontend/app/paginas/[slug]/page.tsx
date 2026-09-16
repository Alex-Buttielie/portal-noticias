import { notFound } from "next/navigation";
import type { Metadata } from "next";
import * as api from "@/lib/api";
import { SITE_URL } from "@/lib/site";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Prose } from "@/components/ui/prose";

export async function generateMetadata({ params }: { params: { slug: string } }): Promise<Metadata> {
  const pagina = await api.obterPaginaEditorial(params.slug).catch(() => null);
  if (!pagina) {
    return { title: "Página não encontrada", robots: { index: false, follow: false } };
  }
  const url = `${SITE_URL}/paginas/${pagina.slug}`;
  const descricao = pagina.conteudo.split("\n\n")[0]?.slice(0, 160) ?? pagina.titulo;
  return {
    title: pagina.titulo,
    description: descricao,
    alternates: { canonical: url },
    openGraph: { type: "article", title: pagina.titulo, description: descricao, url },
    twitter: { card: "summary", title: pagina.titulo, description: descricao },
  };
}

function formatarData(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return new Intl.DateTimeFormat("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric" }).format(d);
}

export default async function PaginaEditorialPage({ params }: { params: { slug: string } }) {
  let pagina: api.PaginaEditorial | null = null;
  try {
    pagina = await api.obterPaginaEditorial(params.slug);
  } catch (e) {
    if (e instanceof api.ApiError && e.status === 404) notFound();
    throw e;
  }
  if (!pagina) notFound();

  return (
    <div className="mx-auto w-full max-w-3xl px-4 py-8 sm:px-6">
      <Card>
        <CardHeader>
          <h1 className="font-[var(--fonte-titulo)] text-3xl font-bold leading-tight tracking-tight text-balance text-[var(--cor-texto)]">
            {pagina.titulo}
          </h1>
          <p className="text-sm text-[var(--cor-texto-suave)]">Atualizado em {formatarData(pagina.atualizado_em)}</p>
        </CardHeader>
        <CardContent>
          <Prose>
            {pagina.conteudo.split("\n\n").map((paragrafo, indice) => (
              <p key={indice}>{paragrafo}</p>
            ))}
          </Prose>
        </CardContent>
      </Card>
    </div>
  );
}
