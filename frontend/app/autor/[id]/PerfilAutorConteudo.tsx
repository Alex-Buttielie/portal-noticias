"use client";

import { useState } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { usePerfilAutor, useSeguirAutor } from "@/lib/queries";
import Badge from "@/components/Badge";
import { Button } from "@/components/ui/Button";
import { EmptyState, ErrorState, SkeletonCard } from "@/components/ui/Estados";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Cards";
import { cn } from "@/lib/utils";

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
<div className={cn("container mx-auto max-w-3xl px-4 py-8 sm:px-6")}>
      <Card className="mb-6 shadow-sm secao-bloco secao-titulo cartao-titulo">
        <CardHeader className="space-y-3">
          <p className="text-xs font-bold uppercase tracking-widest text-[var(--cor-primaria)] secao-eyebrow">Quem escreve</p>
          <CardTitle id="autor-titulo" className="flex flex-wrap items-center gap-2 text-2xl">
            {perfil.nome || `Autor #${perfil.id}`} {perfil.credenciado && <Badge variante="premium">Jornalista credenciado</Badge>}
          </CardTitle>
          <p className="text-sm text-[var(--cor-texto-suave)]">
            {perfil.numero_seguidores} seguidor{perfil.numero_seguidores === 1 ? "" : "es"} — siga para receber as próximas análises.
          </p>
          {token && (
            <Button variante="secundaria" onClick={() => void alternarSeguir()} carregando={seguir.isPending} className="w-fit">
              {seguindo ? "Deixar de seguir" : "Seguir autor"}
            </Button>
          )}
        </CardHeader>
      </Card>

      <div className="grid gap-4 container--estreito secao-cabecalho cartao">
        <h2 id="autor-publicacoes" className="font-[var(--fonte-titulo)] text-lg font-bold tracking-tight text-[var(--cor-texto)]">
          Publicações
        </h2>
        {perfil.publicacoes.length === 0 && <EmptyState titulo="Nenhuma publicação ainda" descricao="As análises deste autor aparecerão aqui." />}
        <div className="grid gap-3">
          {perfil.publicacoes.map((publicacao) => (
            <Link key={publicacao.id} href={`/comunidade/${publicacao.id}`} className="block">
              <Card className="p-4 transition-colors hover:border-[var(--cor-primaria)] hover:shadow-md">
                <h3 className="font-[var(--fonte-titulo)] text-base font-semibold leading-tight text-[var(--cor-texto)] line-clamp-2">{publicacao.titulo}</h3>
                <p className="mt-1 text-sm text-[var(--cor-texto-suave)]">Abra para ler a análise completa.</p>
              </Card>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
