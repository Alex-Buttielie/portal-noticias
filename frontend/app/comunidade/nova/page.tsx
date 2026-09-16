"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { useToast } from "@/components/ToastProvider";
import * as api from "@/lib/api";
import { usePublicarAnalise } from "@/lib/queries";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ErrorState } from "@/components/ui/Estados";
import { cn } from "@/lib/utils";

interface ErrosForm {
  tipo?: string;
  titulo?: string;
  categoria?: string;
  conteudo?: string;
}

export default function PaginaNovaPublicacao() {
  const router = useRouter();
  const { token, carregando: carregandoAuth } = useAuth();
  const { notificar } = useToast();
  const publicar = usePublicarAnalise();

  const [titulo, setTitulo] = useState("");
  const [conteudo, setConteudo] = useState("");
  const [tipo, setTipo] = useState<api.TipoPublicacao>("analise");
  const [categoria, setCategoria] = useState("");
  const [erros, setErros] = useState<ErrosForm>({});
  const [erroEnvio, setErroEnvio] = useState<string | null>(null);
  const [sucesso, setSucesso] = useState(false);

  const refTitulo = useRef<HTMLInputElement>(null);
  const refCategoria = useRef<HTMLInputElement>(null);
  const refConteudo = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (!carregandoAuth && !token) {
      router.push("/login");
    }
  }, [carregandoAuth, token, router]);

  function validar(): ErrosForm {
    const e: ErrosForm = {};
    if (!titulo.trim()) e.titulo = "Dê um título à sua publicação.";
    else if (titulo.trim().length < 10) e.titulo = "O título precisa de pelo menos 10 caracteres.";
    if (!conteudo.trim()) e.conteudo = "Escreva o conteúdo da sua análise.";
    else if (conteudo.trim().length < 50) e.conteudo = "Desenvolva um pouco mais — mínimo de 50 caracteres.";
    if (categoria.trim().length > 60) e.categoria = "Categoria com no máximo 60 caracteres.";
    return e;
  }

  function focarPrimeiroErro(e: ErrosForm) {
    if (e.titulo) refTitulo.current?.focus();
    else if (e.categoria) refCategoria.current?.focus();
    else if (e.conteudo) refConteudo.current?.focus();
  }

  async function aoSubmeter(evento: FormEvent) {
    evento.preventDefault();
    if (!token) return;
    const e = validar();
    setErros(e);
    if (Object.keys(e).length > 0) {
      focarPrimeiroErro(e);
      return;
    }
    setErroEnvio(null);
    try {
      await publicar.mutateAsync({ titulo: titulo.trim(), conteudo: conteudo.trim(), tipo, categoria: categoria.trim() });
      setSucesso(true);
      notificar("Sua análise foi publicada na comunidade.", "sucesso");
    } catch (err) {
      setErroEnvio(
        err instanceof api.ApiError
          ? err.message
          : "Não foi possível publicar. Confirme que seu credenciamento está aprovado."
      );
    }
  }

  if (sucesso) {
    return (
      <div className="mx-auto min-w-0 max-w-[640px] space-y-4">
        <p className="text-xs font-bold uppercase tracking-[0.14em] text-[var(--cor-primaria)]">Comunidade</p>
        <h1 className="break-words font-[var(--fonte-titulo)] text-2xl font-bold tracking-tight text-wrap-balance">
          Publicada!
        </h1>
        <p
          role="status"
          className="rounded-md border border-[var(--cor-sucesso)]/20 bg-[var(--cor-sucesso)]/10 px-3 py-2 text-sm text-[var(--cor-sucesso)]"
        >
          Sua análise já está visível para toda a comunidade.
        </p>
        <Button asChild>
          <Link href="/comunidade">Ver comunidade</Link>
        </Button>
      </div>
    );
  }

  return (
    <div className="mx-auto min-w-0 max-w-[640px] space-y-6">
      <header className="min-w-0 space-y-1">
        <p className="text-xs font-bold uppercase tracking-[0.14em] text-[var(--cor-primaria)]">Comunidade</p>
        <h1 className="break-words font-[var(--fonte-titulo)] text-2xl font-bold tracking-tight text-wrap-balance">
          Publique sua análise
        </h1>
        <p className="break-words text-sm text-[var(--cor-texto-suave)]">
          Disponível apenas para jornalistas credenciados —{" "}
          <Link href="/jornalista/status" className="font-medium text-[var(--cor-primaria)] hover:underline">
            ver status do credenciamento
          </Link>
          .
        </p>
      </header>
      {erroEnvio && <ErrorState mensagem={erroEnvio} />}
      <Card className="min-w-0">
        <CardContent className="space-y-4 pt-6">
          <form onSubmit={aoSubmeter} noValidate className="min-w-0 space-y-4">
            <div className="min-w-0 space-y-2">
              <Label htmlFor="nova-tipo">Tipo</Label>
              <Select value={tipo} onValueChange={(v) => setTipo(v as api.TipoPublicacao)}>
                <SelectTrigger id="nova-tipo" className="text-[16px] sm:text-sm">
                  <SelectValue placeholder="Escolha o tipo…" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="analise">Análise</SelectItem>
                  <SelectItem value="opiniao">Opinião</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="min-w-0 space-y-2">
              <Label htmlFor="nova-titulo">Título</Label>
              <Input
                ref={refTitulo}
                id="nova-titulo"
                name="titulo"
                type="text"
                required
                autoComplete="off"
                value={titulo}
                onChange={(e) => setTitulo(e.target.value)}
                placeholder="Título da publicação…"
                aria-invalid={Boolean(erros.titulo)}
                aria-describedby={erros.titulo ? "nova-titulo-erro" : undefined}
                className={cn("text-[16px] sm:text-sm", erros.titulo && "border-[var(--cor-erro)]")}
              />
              {erros.titulo && (
                <p id="nova-titulo-erro" role="alert" className="break-words text-sm font-medium text-[var(--cor-erro)]">
                  {erros.titulo}
                </p>
              )}
            </div>
            <div className="min-w-0 space-y-2">
              <Label htmlFor="nova-categoria">Categoria</Label>
              <Input
                ref={refCategoria}
                id="nova-categoria"
                name="categoria"
                type="text"
                autoComplete="off"
                value={categoria}
                onChange={(e) => setCategoria(e.target.value)}
                placeholder="Ex.: política, economia…"
                aria-invalid={Boolean(erros.categoria)}
                aria-describedby={erros.categoria ? "nova-categoria-erro" : undefined}
                className={cn("text-[16px] sm:text-sm", erros.categoria && "border-[var(--cor-erro)]")}
              />
              {erros.categoria && (
                <p id="nova-categoria-erro" role="alert" className="break-words text-sm font-medium text-[var(--cor-erro)]">
                  {erros.categoria}
                </p>
              )}
            </div>
            <div className="min-w-0 space-y-2">
              <Label htmlFor="nova-conteudo">Conteúdo</Label>
              <Textarea
                ref={refConteudo}
                id="nova-conteudo"
                name="conteudo"
                rows={12}
                required
                value={conteudo}
                onChange={(e) => setConteudo(e.target.value)}
                placeholder="Escreva sua análise respeitando as diretrizes editoriais…"
                aria-invalid={Boolean(erros.conteudo)}
                aria-describedby={erros.conteudo ? "nova-conteudo-erro" : undefined}
                className={cn("text-[16px] sm:text-sm", erros.conteudo && "border-[var(--cor-erro)]")}
              />
              {erros.conteudo && (
                <p id="nova-conteudo-erro" role="alert" className="break-words text-sm font-medium text-[var(--cor-erro)]">
                  {erros.conteudo}
                </p>
              )}
            </div>
            <Button type="submit" loading={publicar.isPending} className="w-full sm:w-auto">
              Publicar análise
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
