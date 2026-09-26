import type { Metadata } from "next";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { SeloBadge } from "@/components/home/NewsCard";
import { SITE_NAME } from "@/lib/site";
import { obterPerfilAutor, type PerfilAutorPublico } from "@/lib/api";
import { seloPublicacao, iniciais, formatarDataConteudo } from "@/lib/colunistas";
import { ImagemNoticia } from "@/components/ImagemNoticia";
import { BadgeCheck } from "lucide-react";

// Perfil público do colunista (FRENTE 2): foto (ou iniciais), mini-bio,
// especialidade (assunto mais frequente), selo por texto e lista completa
// de conteúdos — tudo derivado do dado real, sem invenção.

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }): Promise<Metadata> {
  const { id: idParam } = await params;
  let nome = `Autor #${idParam}`;
  try {
    const p = await obterPerfilAutor(Number(idParam));
    if (p?.nome) nome = p.nome;
  } catch {}
  return { title: `${nome} — Colunista — ${SITE_NAME}` };
}

export function generateStaticParams() {
  return [{ id: "1" }];
}

export const revalidate = 60;

function especialidadeDe(perfil: PerfilAutorPublico): string | null {
  const contagem = new Map<string, { rotulo: string; total: number }>();
  for (const p of perfil.publicacoes || []) {
    const chave = (p.categoria || "").trim().toLowerCase();
    if (!chave) continue;
    const atual = contagem.get(chave) || { rotulo: (p.categoria || "").trim(), total: 0 };
    atual.total += 1;
    contagem.set(chave, atual);
  }
  let melhor: { rotulo: string; total: number } | null = null;
  for (const v of contagem.values()) {
    if (!melhor || v.total > melhor.total) melhor = v;
  }
  return melhor ? melhor.rotulo : null;
}

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id: idParam } = await params;
  const id = Number(idParam);
  let perfil: PerfilAutorPublico | null = null;
  try {
    perfil = await obterPerfilAutor(Number.isFinite(id) ? id : 1);
  } catch {
    perfil = null;
  }

  if (!perfil) {
    return (
      <div className="mx-auto max-w-2xl space-y-4 py-6">
        <div className="hud-line" aria-hidden />
        <Card className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
          <CardContent className="p-6 text-center text-sm text-[var(--cor-texto-suave)]">
            Autor não encontrado. <Link href="/comunidade" className="font-medium text-[var(--cor-primaria)] underline">Ver comunidade</Link>
          </CardContent>
        </Card>
      </div>
    );
  }

  const especialidade = especialidadeDe(perfil);
  const textos = [...(perfil.publicacoes || [])].sort(
    (a, b) => new Date(b.publicado_em || b.criado_em).getTime() - new Date(a.publicado_em || a.criado_em).getTime()
  );

  return (
    <div className="mx-auto max-w-2xl space-y-4 py-6">
      <div className="hud-line" aria-hidden />
      <Card className="overflow-hidden border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
        <CardHeader className="pb-3">
          <div className="flex items-center gap-4">
            {perfil.foto_url ? (
              <ImagemNoticia
                src={perfil.foto_url}
                seed={`colunista-${perfil.id}`}
                alt={`Foto de ${perfil.nome}`}
                sizes="64px"
                className="h-16 w-16 shrink-0 rounded-full border border-[var(--cor-borda)] object-cover"
                fallbackClassName="h-16 w-16 shrink-0 rounded-full border border-[var(--cor-borda)]"
                fallback={
                  <span
                    aria-hidden
                    className="flex h-16 w-16 shrink-0 items-center justify-center rounded-full bg-[var(--cor-primaria-suave)] text-lg font-bold text-[var(--cor-primaria)]"
                  >
                    {iniciais(perfil.nome)}
                  </span>
                }
              />
            ) : (
              <span
                aria-hidden
                className="flex h-16 w-16 shrink-0 items-center justify-center rounded-full bg-[var(--cor-primaria-suave)] text-lg font-bold text-[var(--cor-primaria)]"
              >
                {iniciais(perfil.nome)}
              </span>
            )}
            <div className="min-w-0">
              <CardTitle className="truncate text-xl">{perfil.nome}</CardTitle>
              <p className="mt-0.5 flex flex-wrap items-center gap-2 text-sm text-[var(--cor-texto-suave)]">
                {especialidade && <span className="font-medium capitalize text-[var(--cor-primaria)]">{especialidade}</span>}
                <span>{textos.length} {textos.length === 1 ? "texto" : "textos"} • {perfil.numero_seguidores} seguidores</span>
              </p>
            </div>
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            {perfil.credenciado && (
              <Badge className="inline-flex items-center gap-1 bg-[var(--cor-sucesso)] text-[var(--cor-texto-invertido)]">
                <BadgeCheck className="h-3 w-3" aria-hidden /> credenciado
              </Badge>
            )}
            <Badge variant="outline" className="border-[var(--cor-borda)]">Colunista</Badge>
          </div>
          {perfil.mini_bio && <p className="mt-3 text-sm leading-relaxed text-[var(--cor-texto-suave)]">{perfil.mini_bio}</p>}
        </CardHeader>
        <CardContent>
          <h2 id="textos" className="mb-2 scroll-mt-24 text-sm font-bold text-[var(--cor-texto)]">
            Todos os textos {textos.length > 0 && <span className="font-normal text-[var(--cor-texto-suave)]">({textos.length})</span>}
          </h2>
          {textos.length ? (
            <div className="grid gap-2">
              {textos.map((p) => (
                <div
                  key={p.id}
                  className="rounded-[var(--raio-md)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-3"
                >
                  <div className="mb-1.5 flex flex-wrap items-center gap-2">
                    <SeloBadge selo={seloPublicacao(p)} />
                    <time dateTime={p.publicado_em || p.criado_em} className="text-xs text-[var(--cor-texto-suave)]">
                      {formatarDataConteudo(p)}
                    </time>
                    {p.categoria && <span className="text-xs capitalize text-[var(--cor-texto-suave)]">• {p.categoria}</span>}
                  </div>
                  <Link
                    href={`/comunidade/${p.id}`}
                    className="font-medium leading-snug text-[var(--cor-texto)] hover:text-[var(--cor-primaria)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]"
                  >
                    {p.titulo}
                  </Link>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-[var(--cor-texto-suave)]">Nenhum texto publicado.</p>
          )}
          <Link href="/comunidade" className="mt-4 inline-flex text-sm font-medium text-[var(--cor-primaria)] hover:underline">
            ← Voltar para a comunidade
          </Link>
        </CardContent>
      </Card>
    </div>
  );
}
