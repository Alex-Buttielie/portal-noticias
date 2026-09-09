"use client";

import { useState } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { usePerfilAutor, useSeguirAutor } from "@/lib/queries";
import Badge from "@/components/Badge";
import { Button } from "@/components/ui/Button";
import { EmptyState, ErrorState, SkeletonCard } from "@/components/ui/Estados";

/**
 * Conteúdo interativo da página de perfil de autor — extraído de `page.tsx`
 * para que `page.tsx` possa virar um Server Component com
 * `generateMetadata`/JSON-LD (metadata não pode ser exportado por um
 * Client Component).
 */
export default function PerfilAutorConteudo({ id }: { id: string }) {
  const { token } = useAuth();
  const autorId = Number(id);
  const perfilQuery = usePerfilAutor(autorId);
  const [seguindo, setSeguindo] = useState(false);

  const perfil = perfilQuery.data ?? null;
  const seguir = useSeguirAutor(autorId, perfil?.nome || "este autor");

  async function alternarSeguir() {
    if (!token || !perfil) return;
    try {
      await seguir.mutateAsync(seguindo);
      setSeguindo((s) => !s);
    } catch {
      // useSeguirAutor já reverte o otimista e notifica.
    }
  }

  if (perfilQuery.isLoading) return <SkeletonCard />;
  if (perfilQuery.isError) {
    return (
      <ErrorState
        mensagem="Não foi possível carregar o perfil."
        aoTentarNovamente={() => void perfilQuery.refetch()}
      />
    );
  }
  if (!perfil) {
    return <EmptyState titulo="Perfil não encontrado" descricao="Este autor não existe." />;
  }

  return (
    <div>
      <h1>
        {perfil.nome || `Autor #${perfil.id}`}{" "}
        {perfil.credenciado && <Badge variante="premium">Jornalista credenciado</Badge>}
      </h1>
      <p className="texto-suave">
        {perfil.numero_seguidores} seguidor{perfil.numero_seguidores === 1 ? "" : "es"}
      </p>

      {token && (
        <Button variante="secundaria" onClick={() => void alternarSeguir()} carregando={seguir.isPending}>
          {seguindo ? "Deixar de seguir" : "Seguir"}
        </Button>
      )}

      <h2 style={{ fontSize: "1.1rem", marginTop: "1.5rem" }}>Publicações</h2>
      {perfil.publicacoes.length === 0 && (
        <EmptyState titulo="Nenhuma publicação ainda" descricao="As análises deste autor aparecerão aqui." />
      )}
      {perfil.publicacoes.map((publicacao) => (
        <Link
          key={publicacao.id}
          href={`/comunidade/${publicacao.id}`}
          style={{ textDecoration: "none", color: "inherit" }}
        >
          <article className="cartao">
            <h3 className="cartao-titulo">{publicacao.titulo}</h3>
          </article>
        </Link>
      ))}
    </div>
  );
}
