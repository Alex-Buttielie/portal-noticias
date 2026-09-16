"use client";

import { useState, type FormEvent } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import * as api from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { CampoTexto } from "@/components/ui/FormField";
import { ErrorState } from "@/components/ui/Estados";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/Cards";
import { cn } from "@/lib/utils";

export default function RedefinirSenhaConteudo() {
  const searchParams = useSearchParams();
  const uid = searchParams.get("uid");
  const token = searchParams.get("token");

  const [novaSenha, setNovaSenha] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [sucesso, setSucesso] = useState(false);

  async function aoSubmeter(evento: FormEvent) {
    evento.preventDefault();
    setErro(null);

    if (!uid || !token) {
      setErro("Link de redefinição inválido — faltam parâmetros na URL.");
      return;
    }

    setEnviando(true);
    try {
      await api.redefinirSenha(uid, token, novaSenha);
      setSucesso(true);
    } catch (e) {
      setErro(
        e instanceof api.ApiError ? e.message : "Não foi possível redefinir a senha."
      );
    } finally {
      setEnviando(false);
    }
  }

  if (sucesso) {
    return (
<div className={cn("container mx-auto max-w-md px-4 py-10 sm:px-6")}>
        <Card className="shadow-lg container--estreito secao-bloco mensagem-sucesso botao botao--primaria botao--medio">
          <CardHeader className="space-y-2">
            <p className="text-xs font-bold uppercase tracking-widest text-[var(--cor-sucesso)] secao-eyebrow">Senha atualizada</p>
            <CardTitle id="redefinida-titulo" className="text-2xl">
              Senha redefinida
            </CardTitle>
            <CardDescription>Sua senha foi alterada com sucesso. Entre com a nova senha.</CardDescription>
          </CardHeader>
          <CardContent>
            <Link href="/login" className={cn("inline-flex h-10 items-center justify-center rounded-md bg-[var(--cor-primaria)] px-6 text-sm font-semibold text-white shadow-sm hover:bg-[var(--cor-primaria-hover)]")}>
              Ir para o login
            </Link>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
<div className={cn("container mx-auto max-w-md px-4 py-10 sm:px-6")}>
      <Card className="shadow-lg container--estreito secao-bloco formulario">
        <CardHeader className="space-y-2">
          <p className="text-xs font-bold uppercase tracking-widest text-[var(--cor-primaria)] secao-eyebrow">Acesso à conta</p>
          <CardTitle id="redefinir-titulo" className="text-2xl">
            Crie uma nova senha
          </CardTitle>
          <CardDescription>Escolha uma senha forte, com no mínimo 8 caracteres.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-6">
          {(!uid || !token) && <ErrorState mensagem="Este link parece inválido. Peça uma nova redefinição de senha." />}
          {erro && <ErrorState mensagem={erro} />}
          <form onSubmit={aoSubmeter} className="grid gap-4">
            <CampoTexto
              id="nova-senha"
              name="nova-senha"
              rotulo="Nova senha"
              type="password"
              required
              minLength={8}
              autoComplete="new-password"
              placeholder="Mínimo de 8 caracteres…"
              autoFocus
              value={novaSenha}
              onChange={(e) => setNovaSenha(e.target.value)}
            />
            <Button type="submit" tamanho="grande" carregando={enviando} disabled={!uid || !token} className="w-full">
              Salvar nova senha
            </Button>
          </form>
          <p className="text-center text-sm text-[var(--cor-texto-suave)]">
            Não recebeu o link?{" "}
            <Link href="/recuperar-senha" className="font-medium text-[var(--cor-primaria)] hover:underline">
              Peça outro e-mail
            </Link>
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
