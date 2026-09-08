"use client";

import { useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { useToast } from "@/components/ToastProvider";
import * as api from "@/lib/api";
import { usePublicarAnalise } from "@/lib/queries";
import { Button } from "@/components/ui/Button";
import { CampoAreaTexto, CampoSelecao, CampoTexto } from "@/components/ui/FormField";
import { ErrorState } from "@/components/ui/Estados";

export default function PaginaNovaPublicacao() {
  const router = useRouter();
  const { token, carregando: carregandoAuth } = useAuth();
  const { notificar } = useToast();
  const publicar = usePublicarAnalise();

  const [titulo, setTitulo] = useState("");
  const [conteudo, setConteudo] = useState("");
  const [tipo, setTipo] = useState<api.TipoPublicacao>("analise");
  const [categoria, setCategoria] = useState("");
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
    try {
      await publicar.mutateAsync({ titulo, conteudo, tipo, categoria });
      setSucesso(true);
      notificar("Publicação enviada.", "sucesso");
    } catch (e) {
      setErro(
        e instanceof api.ApiError
          ? e.message
          : "Não foi possível publicar. Confirme que seu credenciamento está aprovado."
      );
    }
  }

  if (sucesso) {
    return (
      <div className="formulario">
        <h1>Publicado!</h1>
        <p className="mensagem-sucesso">Sua análise foi publicada na comunidade.</p>
        <Link href="/comunidade" className="botao botao--primaria botao--medio">
          Ver comunidade
        </Link>
      </div>
    );
  }

  return (
    <div className="formulario" style={{ maxWidth: 640 }}>
      <h1>Nova publicação</h1>
      <p className="texto-suave">
        Disponível apenas para jornalistas credenciados —{" "}
        <Link href="/jornalista/status">ver status do credenciamento</Link>.
      </p>
      {erro && <ErrorState mensagem={erro} />}
      <form onSubmit={aoSubmeter}>
        <CampoSelecao id="tipo" rotulo="Tipo" value={tipo} onChange={(e) => setTipo(e.target.value as api.TipoPublicacao)}>
          <option value="analise">Análise</option>
          <option value="opiniao">Opinião</option>
        </CampoSelecao>
        <CampoTexto id="titulo" rotulo="Título" required value={titulo} onChange={(e) => setTitulo(e.target.value)} />
        <CampoTexto id="categoria" rotulo="Categoria" value={categoria} onChange={(e) => setCategoria(e.target.value)} />
        <CampoAreaTexto
          id="conteudo"
          rotulo="Conteúdo"
          rows={12}
          required
          value={conteudo}
          onChange={(e) => setConteudo(e.target.value)}
        />
        <Button type="submit" carregando={publicar.isPending}>
          Publicar
        </Button>
      </form>
    </div>
  );
}
