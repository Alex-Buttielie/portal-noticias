"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import * as api from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { CampoTexto } from "@/components/ui/FormField";
import { ErrorState } from "@/components/ui/Estados";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/Cards";
import { cn } from "@/lib/utils";

export default function PaginaRecuperarSenha() {
  const [email, setEmail] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [mensagem, setMensagem] = useState<string | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  async function aoSubmeter(evento: FormEvent) {
    evento.preventDefault();
    setErro(null);
    setEnviando(true);
    try {
      const resposta = await api.recuperarSenha(email);
      setMensagem(resposta.detail);
    } catch (e) {
      setErro(
        e instanceof api.ApiError ? e.message : "Não foi possível processar o pedido."
      );
    } finally {
      setEnviando(false);
    }
  }

  return (
<div className={cn("container mx-auto max-w-md px-4 py-10 sm:px-6")}>
      <Card className="shadow-lg secao-bloco mensagem-sucesso botao botao--secundaria botao--medio formulario">
        <CardHeader className="space-y-2">
          <p className="text-xs font-bold uppercase tracking-widest text-[var(--cor-primaria)] secao-eyebrow">Acesso à conta</p>
          <CardTitle id="recuperar-titulo" className="text-2xl">
            Recuperar senha
          </CardTitle>
          <CardDescription>Informe seu e-mail e enviaremos as instruções para criar uma nova senha.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-6">
          {erro && <ErrorState mensagem={erro} />}
          {mensagem ? (
            <div className="grid gap-4 container--estreito">
              <div className="rounded-md border border-[var(--cor-sucesso)]/20 bg-[var(--cor-sucesso)]/10 px-4 py-3 text-sm text-[var(--cor-sucesso)]">
                {mensagem}
              </div>
              <Link href="/login" className={cn("inline-flex h-10 items-center justify-center rounded-md border border-[var(--cor-borda)] bg-white px-6 text-sm font-medium hover:bg-[var(--cor-primaria-suave)]")}>
                Voltar para o login
              </Link>
            </div>
          ) : (
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
              <Button type="submit" tamanho="grande" carregando={enviando} className="w-full">
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
