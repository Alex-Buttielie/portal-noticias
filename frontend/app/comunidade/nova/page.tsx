"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import * as api from "@/lib/api";

export default function PaginaNovaPublicacao() {
  const router = useRouter();
  const { token, carregando: carregandoAuth } = useAuth();

  const [titulo, setTitulo] = useState("");
  const [conteudo, setConteudo] = useState("");
  const [tipo, setTipo] = useState<api.TipoPublicacao>("analise");
  const [categoria, setCategoria] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [sucesso, setSucesso] = useState(false);

  useEffect(() => {
    if (!carregandoAuth && !token) {
      router.push("/login");
    }
  }, [carregandoAuth, token, router]);

  async function aoSubmeter(evento: FormEvent) {
    evento.preventDefault();
    if (!token) return;
    setErro(null);
    setEnviando(true);
    try {
      const rascunho = await api.criarRascunhoPublicacao(token, { titulo, conteudo, tipo, categoria });
      await api.enviarPublicacao(token, rascunho.id);
      setSucesso(true);
    } catch (e) {
      setErro(
        e instanceof api.ApiError
          ? e.message
          : "Não foi possível publicar. Confirme que seu credenciamento está aprovado."
      );
    } finally {
      setEnviando(false);
    }
  }

  if (sucesso) {
    return (
      <div className="formulario">
        <h1>Publicado!</h1>
        <p className="mensagem-sucesso">Sua análise foi publicada na comunidade.</p>
        <a href="/comunidade" className="botao">
          Ver comunidade
        </a>
      </div>
    );
  }

  return (
    <div className="formulario" style={{ maxWidth: 640 }}>
      <h1>Nova publicação</h1>
      <p className="texto-suave">
        Disponível apenas para jornalistas credenciados —{" "}
        <a href="/jornalista/status">ver status do credenciamento</a>.
      </p>
      {erro && <p className="mensagem-erro">{erro}</p>}
      <form onSubmit={aoSubmeter}>
        <div className="campo">
          <label htmlFor="tipo">Tipo</label>
          <select id="tipo" value={tipo} onChange={(e) => setTipo(e.target.value as api.TipoPublicacao)}>
            <option value="analise">Análise</option>
            <option value="opiniao">Opinião</option>
          </select>
        </div>
        <div className="campo">
          <label htmlFor="titulo">Título</label>
          <input id="titulo" type="text" required value={titulo} onChange={(e) => setTitulo(e.target.value)} />
        </div>
        <div className="campo">
          <label htmlFor="categoria">Categoria</label>
          <input id="categoria" type="text" value={categoria} onChange={(e) => setCategoria(e.target.value)} />
        </div>
        <div className="campo">
          <label htmlFor="conteudo">Conteúdo</label>
          <textarea
            id="conteudo"
            rows={12}
            required
            value={conteudo}
            onChange={(e) => setConteudo(e.target.value)}
          />
        </div>
        <button type="submit" className="botao" disabled={enviando}>
          {enviando ? "Publicando..." : "Publicar"}
        </button>
      </form>
    </div>
  );
}
