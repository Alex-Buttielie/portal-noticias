"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { useToast } from "@/components/ToastProvider";
import { ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { CampoTexto } from "@/components/ui/FormField";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Card, CardContent, CardDescription, CardHeader } from "@/components/ui/card";

export default function PaginaLogin() {
  const router = useRouter();
  const { fazerLogin } = useAuth();
  const { notificar } = useToast();
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [erroEmail, setErroEmail] = useState<string | undefined>(undefined);
  const [erroSenha, setErroSenha] = useState<string | undefined>(undefined);
  const [erroEnvio, setErroEnvio] = useState<string | null>(null);

  async function aoSubmeter(evento: FormEvent) {
    evento.preventDefault();
    setErroEnvio(null);
    let primeiroInvalido: string | null = null;
    if (!email.trim()) {
      setErroEmail("Informe seu e-mail.");
      primeiroInvalido ??= "email";
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
      setErroEmail("Esse e-mail parece inválido.");
      primeiroInvalido ??= "email";
    } else {
      setErroEmail(undefined);
    }
    if (!senha) {
      setErroSenha("Informe sua senha.");
      primeiroInvalido ??= "senha";
    } else {
      setErroSenha(undefined);
    }
    if (primeiroInvalido) {
      document.getElementById(primeiroInvalido)?.focus();
      return;
    }
    setEnviando(true);
    try {
      await fazerLogin(email.trim(), senha);
      notificar("Login realizado com sucesso. Bem-vindo de volta!", "sucesso");
      router.push("/");
    } catch (e) {
      setErroEnvio(e instanceof ApiError ? e.message : "Não foi possível entrar.");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div className="mx-auto w-full max-w-md px-4 py-10 sm:px-6">
      <Card>
        <CardHeader>
          <h1 className="font-[var(--fonte-titulo)] text-2xl font-bold tracking-tight text-balance text-[var(--cor-texto)]">
            Entre na sua conta
          </h1>
          <CardDescription>Leia sem limites, salve matérias e acompanhe seus temas.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-6">
          {erroEnvio && (
            <Alert variant="destructive">
              <AlertTitle>Não foi possível entrar</AlertTitle>
              <AlertDescription>{erroEnvio}</AlertDescription>
            </Alert>
          )}
          <form onSubmit={aoSubmeter} noValidate className="grid gap-4">
            <CampoTexto
              id="email"
              name="email"
              rotulo="E-mail"
              type="email"
              required
              autoComplete="email"
              placeholder="voce@exemplo.com…"
              value={email}
              erro={erroEmail}
              onChange={(e) => setEmail(e.target.value)}
            />
            <CampoTexto
              id="senha"
              name="senha"
              rotulo="Senha"
              type="password"
              required
              autoComplete="current-password"
              placeholder="Sua senha…"
              value={senha}
              erro={erroSenha}
              onChange={(e) => setSenha(e.target.value)}
            />
            <Button type="submit" tamanho="grande" loading={enviando} className="w-full">
              Entrar
            </Button>
          </form>
          <div className="flex flex-col gap-2 border-t border-[var(--cor-borda)] pt-4 text-sm text-[var(--cor-texto-suave)]">
            <p>
              Esqueceu a senha?{" "}
              <Link
                href="/recuperar-senha"
                className="font-medium text-[var(--cor-primaria)] underline-offset-4 hover:underline"
              >
                Recupere o acesso
              </Link>
            </p>
            <p>
              Ainda não tem conta?{" "}
              <Link
                href="/cadastro"
                className="font-medium text-[var(--cor-primaria)] underline-offset-4 hover:underline"
              >
                Crie a sua grátis
              </Link>
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
