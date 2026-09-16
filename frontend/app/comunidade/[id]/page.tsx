"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { useToast } from "@/components/ToastProvider";
import * as api from "@/lib/api";
import { useComentar, useComentarios, useEditarPublicacao, useExcluirComentario, useExcluirPublicacao, usePublicacao } from "@/lib/queries";
import Badge from "@/components/Badge";
import { Button } from "@/components/ui/Button";
import { CampoAreaTexto, CampoTexto } from "@/components/ui/FormField";
import { EmptyState, ErrorState, SkeletonCard } from "@/components/ui/Estados";
import { Card, CardContent } from "@/components/ui/Cards";
import { cn } from "@/lib/utils";

const ID_TEMPORARIO_BASE = -1;
const formatoData = new Intl.DateTimeFormat("pt-BR", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });

function formatarData(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : formatoData.format(d);
}

export default function PaginaDetalhePublicacao({ params }: { params: { id: string } }) {
  const router = useRouter();
  const { token, usuario } = useAuth();
  const { notificar } = useToast();
  const publicacaoId = Number(params.id);

  const publicacaoQuery = usePublicacao(publicacaoId);
  const comentariosQuery = useComentarios(publicacaoId);
  const comentarMutacao = useComentar(publicacaoId);
  const editarMutacao = useEditarPublicacao(publicacaoId);
  const excluirPubMutacao = useExcluirPublicacao();
  const excluirComentMutacao = useExcluirComentario(publicacaoId);

  const publicacao = publicacaoQuery.data ?? null;
  const [novoComentario, setNovoComentario] = useState("");
  const [otimistas, setOtimistas] = useState<api.Comentario[]>([]);
  const [editando, setEditando] = useState(false);
  const [tituloEdicao, setTituloEdicao] = useState("");
  const [conteudoEdicao, setConteudoEdicao] = useState("");

  const comentarios = [...(comentariosQuery.data ?? []), ...otimistas];

  async function aoComentar(evento: FormEvent) {
    evento.preventDefault();
    const conteudo = novoComentario.trim();
    if (!token || !conteudo || !usuario) return;
    const provisorio: api.Comentario = {
      id: ID_TEMPORARIO_BASE - otimistas.length,
      autor: usuario.id,
      autor_nome: usuario.nome,
      conteudo,
      publicacao: publicacaoId,
      news_item: null,
      resposta_de: null,
      criado_em: new Date().toISOString(),
    };
    setOtimistas((atual) => [...atual, provisorio]);
    setNovoComentario("");
    try {
      await comentarMutacao.mutateAsync(conteudo);
      setOtimistas((atual) => atual.filter((c) => c.id !== provisorio.id));
    } catch (e) {
      setOtimistas((atual) => atual.filter((c) => c.id !== provisorio.id));
      setNovoComentario(conteudo);
      notificar(e instanceof api.ApiError ? e.message : "Não foi possível comentar.", "erro");
    }
  }

  function iniciarEdicao() {
    if (!publicacao) return;
    setTituloEdicao(publicacao.titulo);
    setConteudoEdicao(publicacao.conteudo);
    setEditando(true);
  }

  async function salvarEdicao(evento: FormEvent) {
    evento.preventDefault();
    if (!token || !publicacao) return;
    try {
      await editarMutacao.mutateAsync({ titulo: tituloEdicao, conteudo: conteudoEdicao });
      setEditando(false);
      notificar("Publicação atualizada.", "sucesso");
    } catch (e) {
      notificar(e instanceof api.ApiError ? e.message : "Não foi possível salvar a edição.", "erro");
    }
  }

  if (publicacaoQuery.isLoading) return <SkeletonCard />;
  if (publicacaoQuery.isError) {
    return (
      <ErrorState
        mensagem={
          publicacaoQuery.error instanceof api.ApiError
            ? publicacaoQuery.error.message
            : "Não foi possível carregar a publicação."
        }
        aoTentarNovamente={() => void publicacaoQuery.refetch()}
      />
    );
  }
  if (!publicacao) {
    return (
      <EmptyState
        titulo="Publicação não encontrada"
        descricao="Ela pode ter sido removida ou ainda não estar disponível."
      />
    );
  }

  const ehAutor = usuario?.id === publicacao.autor;
  const podeExcluirPub = ehAutor || usuario?.papel === "admin";
  const podeExcluirComentario = (autorId: number) => usuario?.id === autorId || usuario?.papel === "admin";

  async function excluirPublicacao() {
    if (!window.confirm("Excluir esta publicação permanentemente? Os comentários serão apagados junto.")) return;
    try {
      await excluirPubMutacao.mutateAsync(publicacaoId);
      notificar("Publicação excluída.", "info");
      router.push("/comunidade");
    } catch (e) {
      notificar(e instanceof api.ApiError ? e.message : "Não foi possível excluir.", "erro");
    }
  }

  async function excluirComentario(id: number) {
    if (!window.confirm("Excluir este comentário?")) return;
    try {
      await excluirComentMutacao.mutateAsync(id);
    } catch (e) {
      notificar(e instanceof api.ApiError ? e.message : "Não foi possível excluir o comentário.", "erro");
    }
  }

  return (
<article className="mx-auto max-w-prose space-y-6 cartao-meta">
      <p className="text-sm text-[var(--cor-texto-suave)]">
        <Link href="/comunidade" className="font-medium text-[var(--cor-primaria)] hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]">Voltar para a comunidade</Link>
      </p>
      <div className="flex flex-wrap gap-1.5">
        <Badge variante={publicacao.tipo === "opiniao" ? "premium" : "neutro"}>
          {publicacao.tipo === "opiniao" ? "Opinião" : "Análise"}
        </Badge>
        {publicacao.categoria && <Badge variante="neutro">{publicacao.categoria}</Badge>}
      </div>

      {editando ? (
        <Card>
          <CardContent className="pt-6">
            <form onSubmit={salvarEdicao} className="space-y-4">
              <CampoTexto
                id="titulo-edicao"
                rotulo="Título"
                value={tituloEdicao}
                onChange={(e) => setTituloEdicao(e.target.value)}
                required
              />
              <CampoAreaTexto
                id="conteudo-edicao"
                rotulo="Conteúdo"
                rows={10}
                value={conteudoEdicao}
                onChange={(e) => setConteudoEdicao(e.target.value)}
                required
              />
              <div className="flex flex-wrap gap-2">
                <Button type="submit" carregando={editarMutacao.isPending}>
                  Salvar alterações
                </Button>
                <Button type="button" variante="secundaria" onClick={() => setEditando(false)}>
                  Cancelar
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      ) : (
        <>
          <h1 className="font-[var(--fonte-titulo)] text-2xl font-bold leading-tight tracking-[-0.02em] text-wrap-balance">{publicacao.titulo}</h1>
          <p className="flex flex-wrap items-center gap-2 text-sm text-[var(--cor-texto-suave)]">
            por <Link href={`/autor/${publicacao.autor}`} className="font-medium text-[var(--cor-primaria)] hover:underline">{publicacao.autor_nome}</Link>
            {ehAutor && (
              <>
                <span aria-hidden="true">—</span>
                <Button variante="fantasma" tamanho="pequeno" onClick={iniciarEdicao}>
                  Editar
                </Button>
              </>
            )}
            {podeExcluirPub && (
              <>
                <span aria-hidden="true">—</span>
                <Button variante="perigo" tamanho="pequeno" carregando={excluirPubMutacao.isPending} onClick={() => void excluirPublicacao()}>
                  Excluir
                </Button>
              </>
            )}
          </p>
          <div className="whitespace-pre-wrap break-words text-[15px] leading-relaxed text-[var(--cor-texto)]">{publicacao.conteudo}</div>
        </>
      )}

<section className="space-y-3 secao-bloco secao-titulo cartao-meta" aria-label="Comentários">
        <div className="flex items-baseline gap-3 border-b-2 border-[var(--cor-borda)] pb-3 secao-cabecalho cartao">
          <h2 className="font-[var(--fonte-titulo)] text-lg font-bold tracking-tight">Comentários ({comentarios.length})</h2>
        </div>
        <div aria-live="polite" className="space-y-3">
          {comentarios.length === 0 ? (
            <p className="text-sm text-[var(--cor-texto-suave)]">Seja o primeiro a comentar.</p>
          ) : (
            comentarios.map((comentario) => (
              <Card key={comentario.id} className={cn(comentario.id < 0 && "opacity-60")}>
                <CardContent className="space-y-2 p-4">
                  <div className="flex flex-wrap items-center gap-2 text-sm">
                    <strong className="text-[var(--cor-texto)]">{comentario.autor_nome}</strong>
                    <span className="text-xs text-[var(--cor-texto-suave)]">
                      <time dateTime={comentario.criado_em}>{formatarData(comentario.criado_em)}</time>
                    </span>
                    {comentario.id < 0 && <span className="text-xs text-[var(--cor-texto-suave)]">Enviando…</span>}
                    {comentario.id > 0 && podeExcluirComentario(comentario.autor) && (
                      <Button variante="fantasma" tamanho="pequeno" className="ml-auto" onClick={() => void excluirComentario(comentario.id)}>
                        Excluir
                      </Button>
                    )}
                  </div>
                  <p className="whitespace-pre-wrap break-words text-sm leading-relaxed">{comentario.conteudo}</p>
                </CardContent>
              </Card>
            ))
          )}
        </div>
      </section>

      {token ? (
        <form onSubmit={aoComentar} className="space-y-3">
          <CampoAreaTexto
            id="novo-comentario"
            rotulo="Deixe seu comentário"
            rows={3}
            placeholder="Escreva um comentário respeitoso…"
            value={novoComentario}
            onChange={(e) => setNovoComentario(e.target.value)}
          />
          <Button type="submit" carregando={comentarMutacao.isPending} disabled={!novoComentario.trim()}>
            Comentar
          </Button>
        </form>
      ) : (
        <p className="text-sm text-[var(--cor-texto-suave)]">
          <Link href="/login" className="font-medium text-[var(--cor-primaria)] hover:underline">Entre</Link> para comentar.
        </p>
      )}
    </article>
  );
}
