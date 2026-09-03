import type { Metadata } from "next";
import JsonLd from "@/components/JsonLd";
import PerfilAutorConteudo from "./PerfilAutorConteudo";
import * as api from "@/lib/api";
import { personJsonLd } from "@/lib/schema";
import { SITE_URL } from "@/lib/site";

/**
 * Server Component (metadata + JSON-LD `Person` — implementation-contract.md
 * run 20260903-1134-seo-lgpd-design-system, escopo A). O corpo interativo
 * (seguir/deixar de seguir, lista de publicações) foi extraído para
 * `PerfilAutorConteudo.tsx` (Client Component) — `generateMetadata` só pode
 * ser exportado por um Server Component.
 */
export async function generateMetadata({
  params,
}: {
  params: { id: string };
}): Promise<Metadata> {
  const perfil = await api.obterPerfilAutor(Number(params.id)).catch(() => null);
  if (!perfil) {
    return { title: "Autor não encontrado", robots: { index: false, follow: false } };
  }
  const nome = perfil.nome || `Autor #${perfil.id}`;
  const url = `${SITE_URL}/autor/${perfil.id}`;
  const descricao = `Perfil de ${nome} no Portal de Notícias — ${perfil.numero_seguidores} seguidor${perfil.numero_seguidores === 1 ? "" : "es"}.`;

  return {
    title: nome,
    description: descricao,
    alternates: { canonical: url },
    openGraph: { type: "profile", title: nome, description: descricao, url },
    twitter: { card: "summary", title: nome, description: descricao },
  };
}

export default async function PaginaPerfilAutor({ params }: { params: { id: string } }) {
  const perfil = await api.obterPerfilAutor(Number(params.id)).catch(() => null);

  return (
    <>
      {perfil && (
        <JsonLd
          data={personJsonLd({
            id: perfil.id,
            nome: perfil.nome,
            url: `${SITE_URL}/autor/${perfil.id}`,
          })}
        />
      )}
      <PerfilAutorConteudo id={params.id} />
    </>
  );
}
