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
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Cards";
import { cn } from "@/lib/utils";

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
<div className="mx-auto max-w-[640px] space-y-4 formulario botao--primaria botao--medio">
        <p className="text-xs font-bold uppercase tracking-[0.14em] text-[var(--cor-primaria)] secao-eyebrow">Comunidade</p>
        <h1 className="font-[var(--fonte-titulo)] text-2xl font-bold tracking-tight">Publicado!</h1>
        <p className="rounded-md border border-[var(--cor-sucesso)]/20 bg-[var(--cor-sucesso)]/10 px-3 py-2 text-sm text-[var(--cor-sucesso)]">Sua análise foi publicada na comunidade.</p>
        <Link href="/comunidade" className={cn("inline-flex h-10 items-center justify-center rounded-md bg-[var(--cor-primaria)] px-4 text-sm font-semibold text-white hover:bg-[var(--cor-primaria-hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]")}>
          Ver comunidade
        </Link>
      </div>
    );
  }

  return (
<div className="mx-auto max-w-[640px] space-y-6 formulario">
      <header className="space-y-1">
        <p className="text-xs font-bold uppercase tracking-[0.14em] text-[var(--cor-primaria)] secao-eyebrow">Comunidade</p>
        <h1 className="font-[var(--fonte-titulo)] text-2xl font-bold tracking-tight">Nova publicação</h1>
        <p className="text-sm text-[var(--cor-texto-suave)]">
          Disponível apenas para jornalistas credenciados —{" "}
          <Link href="/jornalista/status" className="font-medium text-[var(--cor-primaria)] hover:underline">ver status do credenciamento</Link>.
        </p>
      </header>
      {erro && <ErrorState mensagem={erro} />}
      <Card>
        <CardContent className="pt-6">
          <form onSubmit={aoSubmeter} className="space-y-4">
            <CampoSelecao id="tipo" rotulo="Tipo" value={tipo} onChange={(e) => setTipo(e.target.value as api.TipoPublicacao)}>
              <option value="analise">Análise</option>
              <option value="opiniao">Opinião</option>
            </CampoSelecao>
            <CampoTexto id="titulo" rotulo="Título" required value={titulo} onChange={(e) => setTitulo(e.target.value)} placeholder="Título da publicação…" />
            <CampoTexto id="categoria" rotulo="Categoria" value={categoria} onChange={(e) => setCategoria(e.target.value)} placeholder="Ex: política, economia…" />
            <CampoAreaTexto
              id="conteudo"
              rotulo="Conteúdo"
              rows={12}
              required
              value={conteudo}
              onChange={(e) => setConteudo(e.target.value)}
              placeholder="Escreva sua análise respeitando as diretrizes editoriais…"
            />
            <Button type="submit" carregando={publicar.isPending} className="w-full sm:w-auto">
              Publicar
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
