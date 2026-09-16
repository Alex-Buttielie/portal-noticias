"use client";

import { useState, type FormEvent } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import * as api from "@/lib/api";
import { Button } from "@/components/ui/button";
import { CampoTexto } from "@/components/ui/FormField";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Card, CardContent, CardDescription, CardHeader } from "@/components/ui/card";
import { CheckCircle2 } from "lucide-react";

export default function RedefinirSenhaConteudo() {
  const searchParams = useSearchParams();
  const uid = searchParams.get("uid");
  const token = searchParams.get("token");

  const [novaSenha, setNovaSenha] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [erroCampo, setErroCampo] = useState<string | undefined>(undefined);
  const [erroEnvio, setErroEnvio] = useState<string | null>(null);
  const [sucesso, setSucesso] = useState(false);

  async function aoSubmeter(evento: FormEvent) {
    evento.preventDefault();
    setErroEnvio(null);
    if (!uid || !token) {
      setErroEnvio("Link de redefinição inválido — faltam parâmetros na URL.");
      return;
    }
    if (!novaSenha) {
      setErroCampo("Crie uma nova senha.");
      document.getElementById("nova-senha")?.focus();
      return;
    }
    if (novaSenha.length < 8) {
      setErroCampo("A senha precisa de no mínimo 8 caracteres.");
      document.getElementById("nova-senha")?.focus();
      return;
    }
    setErroCampo(undefined);
    setEnviando(true);
    try {
      await api.redefinirSenha(uid, token, novaSenha);
      setSucesso(true);
    } catch (e) {
      setErroEnvio(e instanceof api.ApiError ? e.message : "Não foi possível redefinir a senha.");
    } finally {
      setEnviando(false);
    }
  }

  if (sucesso) {
    return (
      <div className="mx-auto w-full max-w-md px-4 py-10 sm:px-6">
        <Card>
          <CardHeader>
            <h1 className="font-[var(--fonte-titulo)] text-2xl font-bold tracking-tight text-balance text-[var(--cor-texto)]">
              Senha atualizada
            </h1>
            <CardDescription>Sua senha foi alterada com sucesso. Entre com a nova senha.</CardDescription>
          </CardHeader>
          <CardContent>
            <div aria-live="polite">
              <Alert variant="success">
                <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
                <AlertTitle>Tudo certo</AlertTitle>
                <AlertDescription>Agora é só entrar com a nova senha.</AlertDescription>
              </Alert>
            </div>
            <Button asChild tamanho="grande" className="mt-4 w-full">
              <Link href="/login">Ir para o login</Link>
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-md px-4 py-10 sm:px-6">
      <Card>
        <CardHeader>
          <h1 className="font-[var(--fonte-titulo)] text-2xl font-bold tracking-tight text-balance text-[var(--cor-texto)]">
            Crie uma nova senha
          </h1>
          <CardDescription>Escolha uma senha forte, com no mínimo 8 caracteres.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-6">
          {(!uid || !token) && (
            <Alert variant="destructive">
              <AlertTitle>Link inválido</AlertTitle>
              <AlertDescription>Este link parece inválido. Peça uma nova redefinição de senha.</AlertDescription>
            </Alert>
          )}
          {erroEnvio && (
            <Alert variant="destructive">
              <AlertTitle>Não foi possível salvar</AlertTitle>
              <AlertDescription>{erroEnvio}</AlertDescription>
            </Alert>
          )}
          <form onSubmit={aoSubmeter} noValidate className="grid gap-4">
            <CampoTexto
              id="nova-senha"
              name="nova-senha"
              rotulo="Nova senha"
              type="password"
              required
              minLength={8}
              autoComplete="new-password"
              placeholder="Mínimo de 8 caracteres…"
              value={novaSenha}
              erro={erroCampo}
              onChange={(e) => setNovaSenha(e.target.value)}
            />
            <Button type="submit" tamanho="grande" loading={enviando} className="w-full">
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
