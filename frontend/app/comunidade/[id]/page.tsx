"use client";

import { useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { useToast } from "@/components/ToastProvider";
import * as api from "@/lib/api";

const ID_TEMPORARIO_BASE = -1;

export default function PaginaDetalhePublicacao({ params }: { params: { id: string } }) {
  const { token, usuario } = useAuth();
  const { notificar } = useToast();
  const publicacaoId = Number(params.id);

  const [publicacao, setPublicacao] = useState<api.Publicacao | null>(null);
  const [comentarios, setComentarios] = useState<api.Comentario[]>([]);
  const [novoComentario, setNovoComentario] = useState("");
  const [carregando, setCarregando] = useState(true);
  const [naoEncontrada, setNaoEncontrada] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [enviandoComentario, setEnviandoComentario] = useState(false);

  const [editando, setEditando] = useState(false);
  const [tituloEdicao, setTituloEdicao] = useState("");
  const [conteudoEdicao, setConteudoEdicao] = useState("");
  const [salvandoEdicao, setSalvandoEdicao] = useState(false);

  function carregarComentarios() {
    api
      .obterComentarios({ publicacao: publicacaoId })
      .then(setComentarios)
      .catch(() => {
        // comentários são um extra da tela — falha silenciosa aqui não impede ler a publicação
      });
  }

  useEffect(() => {
    setCarregando(true);
    api
      .obterPublicacao(token, publicacaoId)
      .then((pub) => {
        if (!pub) {
          setNaoEncontrada(true);
        } else {
          setPublicacao(pub);
        }
      })
      .catch((e: unknown) => {
        setErro(e instanceof api.ApiError ? e.message : "Não foi possível carregar a publicação.");
      })
      .finally(() => setCarregando(false));
    carregarComentarios();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [publicacaoId, token]);

  // Comentário aparece na hora (otimista) enquanto a chamada real acontece
  // em segundo plano; se falhar, o comentário provisório é removido e o
  // texto volta para a caixa para o usuário tentar de novo.
  async function aoComentar(evento: FormEvent) {
    evento.preventDefault();
    const conteudo = novoComentario.trim();
    if (!token || !conteudo || !usuario) return;

    const idTemporario = ID_TEMPORARIO_BASE - comentarios.length;
    const comentarioOtimista: api.Comentario = {
      id: idTemporario,
      autor: usuario.id,
      autor_email: usuario.email,
      conteudo,
      publicacao: publicacaoId,
      news_item: null,
      resposta_de: null,
      criado_em: new Date().toISOString(),
    };

    setComentarios((atual) => [...atual, comentarioOtimista]);
    setNovoComentario("");
    setEnviandoComentario(true);

    try {
      await api.comentar(token, { conteudo, publicacao: publicacaoId });
      carregarComentarios();
    } catch (e) {
      setComentarios((atual) => atual.filter((c) => c.id !== idTemporario));
      setNovoComentario(conteudo);
      notificar(e instanceof api.ApiError ? e.message : "Não foi possível comentar.", "erro");
    } finally {
      setEnviandoComentario(false);
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
    setSalvandoEdicao(true);
    try {
      const atualizada = await api.editarPublicacao(token, publicacaoId, {
        titulo: tituloEdicao,
        conteudo: conteudoEdicao,
      });
      setPublicacao(atualizada);
      setEditando(false);
      notificar("Publicação atualizada.", "sucesso");
    } catch (e) {
      notificar(e instanceof api.ApiError ? e.message : "Não foi possível salvar a edição.", "erro");
    } finally {
      setSalvandoEdicao(false);
    }
  }

  if (carregando) return <p className="texto-suave">Carregando...</p>;
  if (naoEncontrada) {
    return <p className="mensagem-erro">Esta publicação não foi encontrada ou não está disponível.</p>;
  }
  if (erro || !publicacao) {
    return <p className="mensagem-erro">{erro || "Não foi possível carregar a publicação."}</p>;
  }

  const ehAutor = usuario?.id === publicacao.autor;

  return (
    <article>
      <div className="cartao-meta">
        <span className="badge-categoria">{publicacao.tipo === "opiniao" ? "Opinião" : "Análise"}</span>
        {publicacao.categoria && <span className="badge-categoria">{publicacao.categoria}</span>}
      </div>

      {editando ? (
        <form onSubmit={salvarEdicao} className="formulario">
          <div className="campo">
            <label htmlFor="titulo-edicao">Título</label>
            <input
              id="titulo-edicao"
              type="text"
              value={tituloEdicao}
              onChange={(e) => setTituloEdicao(e.target.value)}
              required
            />
          </div>
          <div className="campo">
            <label htmlFor="conteudo-edicao">Conteúdo</label>
            <textarea
              id="conteudo-edicao"
              rows={10}
              value={conteudoEdicao}
              onChange={(e) => setConteudoEdicao(e.target.value)}
              required
            />
          </div>
          <button type="submit" className="botao" disabled={salvandoEdicao}>
            {salvandoEdicao ? "Salvando..." : "Salvar alterações"}
          </button>{" "}
          <button type="button" className="botao botao-secundario" onClick={() => setEditando(false)}>
            Cancelar
          </button>
        </form>
      ) : (
        <>
          <h1>{publicacao.titulo}</h1>
          <p className="texto-suave">
            por <Link href={`/autor/${publicacao.autor}`}>{publicacao.autor_email}</Link>
            {ehAutor && (
              <>
                {" — "}
                <button
                  type="button"
                  onClick={iniciarEdicao}
                  style={{
                    background: "none",
                    border: "none",
                    padding: 0,
                    textDecoration: "underline",
                    cursor: "pointer",
                    color: "inherit",
                    font: "inherit",
                  }}
                >
                  Editar
                </button>
              </>
            )}
          </p>
          <div style={{ whiteSpace: "pre-wrap" }}>{publicacao.conteudo}</div>
        </>
      )}

      <h2 style={{ fontSize: "1rem", marginTop: "1.5rem" }}>Comentários ({comentarios.length})</h2>
      {comentarios.map((comentario) => (
        <div
          key={comentario.id}
          className="cartao"
          style={comentario.id < 0 ? { opacity: 0.6 } : undefined}
        >
          <div className="cartao-meta">
            <strong>{comentario.autor_email}</strong>
            {comentario.id < 0 && <span className="texto-suave">Enviando...</span>}
          </div>
          <p>{comentario.conteudo}</p>
        </div>
      ))}

      {token ? (
        <form onSubmit={aoComentar} style={{ marginTop: "1rem" }}>
          <div className="campo">
            <textarea
              rows={3}
              placeholder="Escreva um comentário respeitoso..."
              value={novoComentario}
              onChange={(e) => setNovoComentario(e.target.value)}
            />
          </div>
          <button type="submit" className="botao" disabled={enviandoComentario || !novoComentario.trim()}>
            {enviandoComentario ? "Enviando..." : "Comentar"}
          </button>
        </form>
      ) : (
        <p className="texto-suave">
          <Link href="/login">Entre</Link> para comentar.
        </p>
      )}
    </article>
  );
}
