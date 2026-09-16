"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import * as api from "@/lib/api";
import { Button } from "@/components/ui/button";
import { CampoTexto } from "@/components/ui/FormField";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Card, CardContent, CardDescription, CardHeader } from "@/components/ui/card";
import { CheckCircle2 } from "lucide-react";

export default function PaginaRecuperarSenha() {
  const [email, setEmail] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [mensagem, setMensagem] = useState<string | null>(null);
  const [erroEmail, setErroEmail] = useState<string | undefined>(undefined);
  const [erroEnvio, setErroEnvio] = useState<string | null>(null);

  async function aoSubmeter(evento: FormEvent) {
    evento.preventDefault();
    setErroEnvio(null);
    if (!email.trim()) {
      setErroEmail("Informe o e-mail da sua conta.");
      document.getElementById("email")?.focus();
      return;
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
      setErroEmail("Esse e-mail parece inválido.");
      document.getElementById("email")?.focus();
      return;
    }
    setErroEmail(undefined);
    setEnviando(true);
    try {
      const resposta = await api.recuperarSenha(email.trim());
      setMensagem(resposta.detail);
    } catch (e) {
      setErroEnvio(e instanceof api.ApiError ? e.message : "Não foi possível processar o pedido.");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div className="mx-auto w-full max-w-md px-4 py-10 sm:px-6">
      <Card>
        <CardHeader>
          <h1 className="font-[var(--fonte-titulo)] text-2xl font-bold tracking-tight text-balance text-[var(--cor-texto)]">
            Recupere sua senha
          </h1>
          <CardDescription>Informe seu e-mail e enviaremos as instruções para criar uma nova senha.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-6">
          {erroEnvio && (
            <Alert variant="destructive">
              <AlertTitle>Algo não saiu como esperado</AlertTitle>
              <AlertDescription>{erroEnvio}</AlertDescription>
            </Alert>
          )}
          {mensagem ? (
            <div className="grid gap-4" aria-live="polite">
              <Alert variant="success">
                <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
                <AlertTitle>E-mail enviado</AlertTitle>
                <AlertDescription>{mensagem}</AlertDescription>
              </Alert>
              <Button asChild variant="outline" className="w-full">
                <Link href="/login">Voltar para o login</Link>
              </Button>
            </div>
          ) : (
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
              <Button type="submit" tamanho="grande" loading={enviando} className="w-full">
                Enviar instruções
              </Button>
            </form>
          )}
          {!mensagem && (
            <p className="text-center text-sm text-[var(--cor-texto-suave)]">
              Lembrou a senha?{" "}
              <Link href="/login" className="font-medium text-[var(--cor-primaria)] hover:underline">
                Entre aqui
              </Link>
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
