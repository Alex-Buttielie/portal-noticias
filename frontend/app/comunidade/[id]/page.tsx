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

const ID_TEMPORARIO_BASE = -1;

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
    <article className="secao-bloco">
      <div className="cartao-meta">
        <Badge variante={publicacao.tipo === "opiniao" ? "premium" : "neutro"}>
          {publicacao.tipo === "opiniao" ? "Opinião" : "Análise"}
        </Badge>
        {publicacao.categoria && <Badge variante="neutro">{publicacao.categoria}</Badge>}
      </div>

      {editando ? (
        <form onSubmit={salvarEdicao}>
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
          <Button type="submit" carregando={editarMutacao.isPending}>
            Salvar alterações
          </Button>{" "}
          <Button variante="secundaria" onClick={() => setEditando(false)}>
            Cancelar
          </Button>
        </form>
      ) : (
        <>
          <h1 className="secao-titulo">{publicacao.titulo}</h1>
          <p className="texto-suave">
            por <Link href={`/autor/${publicacao.autor}`}>{publicacao.autor_nome}</Link>
            {ehAutor && (
              <>
                {" — "}
                <Button variante="fantasma" tamanho="pequeno" onClick={iniciarEdicao}>
                  Editar
                </Button>
              </>
            )}
            {podeExcluirPub && (
              <>
                {" — "}
                <Button variante="perigo" tamanho="pequeno" carregando={excluirPubMutacao.isPending} onClick={() => void excluirPublicacao()}>
                  Excluir
                </Button>
              </>
            )}
          </p>
          <div style={{ whiteSpace: "pre-wrap" }}>{publicacao.conteudo}</div>
        </>
      )}

      <div className="secao-cabecalho">
        <h2 className="secao-titulo">Comentários ({comentarios.length})</h2>
      </div>
      {comentarios.map((comentario) => (
        <div key={comentario.id} className="cartao" style={comentario.id < 0 ? { opacity: 0.6 } : undefined}>
          <div className="cartao-meta">
            <strong>{comentario.autor_nome}</strong>
            {comentario.id < 0 && <span className="texto-suave">Enviando...</span>}
            {comentario.id > 0 && podeExcluirComentario(comentario.autor) && (
              <Button variante="fantasma" tamanho="pequeno" onClick={() => void excluirComentario(comentario.id)}>
                Excluir
              </Button>
            )}
          </div>
          <p>{comentario.conteudo}</p>
        </div>
      ))}

      {token ? (
        <form onSubmit={aoComentar} style={{ marginTop: "1rem" }}>
          <CampoAreaTexto
            id="novo-comentario"
            rotulo="Deixe seu comentário"
            rows={3}
            placeholder="Escreva um comentário respeitoso..."
            value={novoComentario}
            onChange={(e) => setNovoComentario(e.target.value)}
          />
          <Button type="submit" carregando={comentarMutacao.isPending} disabled={!novoComentario.trim()}>
            Comentar
          </Button>
        </form>
      ) : (
        <p className="texto-suave">
          <Link href="/login">Entre</Link> para comentar.
        </p>
      )}
    </article>
  );
}
