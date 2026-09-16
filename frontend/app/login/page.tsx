"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { useToast } from "@/components/ToastProvider";
import { ApiError } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { CampoTexto } from "@/components/ui/FormField";
import { ErrorState } from "@/components/ui/Estados";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/Cards";
import { cn } from "@/lib/utils";

export default function PaginaLogin() {
  const router = useRouter();
  const { fazerLogin } = useAuth();
  const { notificar } = useToast();
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  async function aoSubmeter(evento: FormEvent) {
    evento.preventDefault();
    setErro(null);
    setEnviando(true);
    try {
      await fazerLogin(email, senha);
      notificar("Login realizado com sucesso. Bem-vindo de volta!", "sucesso");
      router.push("/");
    } catch (e) {
      setErro(e instanceof ApiError ? e.message : "Não foi possível entrar.");
    } finally {
      setEnviando(false);
    }
  }

  return (
<div className={cn("container mx-auto max-w-md px-4 py-10 sm:px-6")}>
      <Card className="shadow-lg secao-bloco formulario">
        <CardHeader className="space-y-2">
          <p className="text-xs font-bold uppercase tracking-widest text-[var(--cor-primaria)] secao-eyebrow">Acesse sua conta</p>
          <CardTitle id="login-titulo" className="text-2xl">
            Entrar
          </CardTitle>
          <CardDescription>Entre para ler sem limites, salvar matérias e acompanhar seus temas.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-6">
          {erro && <ErrorState mensagem={erro} />}
          <form onSubmit={aoSubmeter} className="grid gap-4">
            <CampoTexto
              id="email"
              name="email"
              rotulo="E-mail"
              type="email"
              required
              autoComplete="email"
              placeholder="voce@exemplo.com…"
              autoFocus
              value={email}
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
              onChange={(e) => setSenha(e.target.value)}
            />
            <Button type="submit" tamanho="grande" carregando={enviando} className="w-full">
              Entrar
            </Button>
          </form>
          <div className="flex flex-col gap-2 border-t border-[var(--cor-borda)] pt-4 text-sm text-[var(--cor-texto-suave)] container--estreito">
            <p>
              Esqueceu a senha?{" "}
              <Link href="/recuperar-senha" className="font-medium text-[var(--cor-primaria)] underline-offset-4 hover:underline">
                Recupere o acesso
              </Link>
            </p>
            <p>
              Ainda não tem conta?{" "}
              <Link href="/cadastro" className="font-medium text-[var(--cor-primaria)] underline-offset-4 hover:underline">
                Crie a sua grátis
              </Link>
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
