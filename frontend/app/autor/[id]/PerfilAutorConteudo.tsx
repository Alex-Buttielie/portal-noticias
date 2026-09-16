"use client";

import { useState } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { usePerfilAutor, useSeguirAutor } from "@/lib/queries";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState, ErrorState, SkeletonCard } from "@/components/ui/Estados";
import { Card, CardContent, CardDescription, CardHeader } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

function formatarData(data: string | null): string {
  if (!data) return "—";
  const d = new Date(data);
  if (Number.isNaN(d.getTime())) return data;
  return new Intl.DateTimeFormat("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric" }).format(d);
}

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
    <div className="mx-auto w-full max-w-3xl px-4 py-8 sm:px-6">
      <Card className="mb-6">
        <CardHeader>
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="font-[var(--fonte-titulo)] text-2xl font-bold tracking-tight text-balance text-[var(--cor-texto)]">
              {perfil.nome || `Autor #${perfil.id}`}
            </h1>
            {perfil.credenciado && <Badge variant="default">Jornalista credenciado</Badge>}
          </div>
          <CardDescription>
            {perfil.numero_seguidores} seguidor{perfil.numero_seguidores === 1 ? "" : "es"} — siga para receber as
            próximas análises.
          </CardDescription>
          {token && (
            <div>
              <Button variante="secundaria" onClick={() => void alternarSeguir()} loading={seguir.isPending} className="w-fit">
                {seguindo ? "Deixar de seguir" : "Seguir autor"}
              </Button>
            </div>
          )}
        </CardHeader>
      </Card>

      <Tabs defaultValue="publicacoes" className="grid gap-4">
        <TabsList aria-label="Conteúdo do autor">
          <TabsTrigger value="publicacoes">Publicações ({perfil.publicacoes.length})</TabsTrigger>
          <TabsTrigger value="sobre">Sobre</TabsTrigger>
        </TabsList>
        <TabsContent value="publicacoes">
          {perfil.publicacoes.length === 0 ? (
            <EmptyState titulo="Nenhuma publicação ainda" descricao="As análises deste autor aparecerão aqui." />
          ) : (
            <ul className="grid gap-3">
              {perfil.publicacoes.map((publicacao) => (
                <li key={publicacao.id}>
                  <Link
                    href={`/comunidade/${publicacao.id}`}
                    className="block rounded-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] focus-visible:ring-offset-2"
                  >
                    <Card className="p-4 transition-colors hover:border-[var(--cor-primaria)] hover:shadow-md">
                      <h2 className="line-clamp-2 font-[var(--fonte-titulo)] text-base font-semibold leading-tight text-[var(--cor-texto)]">
                        {publicacao.titulo}
                      </h2>
                      <p className="mt-1 text-sm text-[var(--cor-texto-suave)]">
                        {publicacao.publicado_em ? `Publicada em ${formatarData(publicacao.publicado_em)}` : "Abra para ler a análise completa."}
                      </p>
                    </Card>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </TabsContent>
        <TabsContent value="sobre">
          <Card>
            <CardContent className="grid gap-2 pt-6 text-sm text-[var(--cor-texto-suave)]">
              <p>
                <span className="font-semibold text-[var(--cor-texto)]">Nome:</span> {perfil.nome || `Autor #${perfil.id}`}
              </p>
              <p className="flex flex-wrap items-center gap-2">
                <span className="font-semibold text-[var(--cor-texto)]">Credenciamento:</span>
                {perfil.credenciado ? <Badge variant="default">Credenciado</Badge> : <Badge variant="secondary">Comunidade</Badge>}
              </p>
              <p>
                <span className="font-semibold text-[var(--cor-texto)]">Seguidores:</span> {perfil.numero_seguidores}
              </p>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
