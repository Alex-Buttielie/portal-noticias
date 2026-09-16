"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import * as api from "@/lib/api";
import { useCadastrar } from "@/lib/queries";
import { Button } from "@/components/ui/Button";
import { CampoTexto } from "@/components/ui/FormField";
import { ErrorState } from "@/components/ui/Estados";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/Cards";
import { Label } from "@/components/ui/FormField";
import { cn } from "@/lib/utils";

export default function PaginaCadastro() {
  const cadastrar = useCadastrar();
  const [email, setEmail] = useState("");
  const [nome, setNome] = useState("");
  const [senha, setSenha] = useState("");
  const [aceiteTermos, setAceiteTermos] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [sucesso, setSucesso] = useState(false);

  async function aoSubmeter(evento: FormEvent) {
    evento.preventDefault();
    setErro(null);

    if (!aceiteTermos) {
      setErro("É necessário aceitar os termos de uso e a política de privacidade.");
      return;
    }

    try {
      await cadastrar.mutateAsync({ email, nome, senha, aceite_termos: aceiteTermos });
      setSucesso(true);
    } catch (e) {
      setErro(e instanceof api.ApiError ? e.message : "Não foi possível concluir o cadastro.");
    }
  }

  if (sucesso) {
    return (
<div className={cn("container mx-auto max-w-md px-4 py-10 sm:px-6 container--estreito")}>
        <Card className="shadow-lg secao-bloco">
          <CardHeader className="space-y-2">
            <p className="text-xs font-bold uppercase tracking-widest text-[var(--cor-sucesso)] secao-eyebrow">Conta criada</p>
            <CardTitle id="cadastro-ok-titulo" className="text-2xl">
              Confirme seu e-mail
            </CardTitle>
            <CardDescription>
              Enviamos um e-mail de confirmação para <strong className="text-[var(--cor-texto)]">{email}</strong>. Abra sua
              caixa de entrada e clique no link para ativar sua conta.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Link href="/login" className={cn("inline-flex h-10 items-center justify-center rounded-md bg-[var(--cor-primaria)] px-6 text-sm font-semibold text-white shadow-sm hover:bg-[var(--cor-primaria-hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]")}>
              Ir para o login
            </Link>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
<div className={cn("container mx-auto max-w-md px-4 py-10 sm:px-6 container--estreito")}>
      <Card className="shadow-lg secao-bloco formulario">
        <CardHeader className="space-y-2">
          <p className="text-xs font-bold uppercase tracking-widest text-[var(--cor-primaria)] secao-eyebrow">Comece grátis</p>
          <CardTitle id="cadastro-titulo" className="text-2xl">
            Criar conta
          </CardTitle>
          <CardDescription>Crie sua conta em segundos e receba o melhor do dia no seu e-mail.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-6">
          {erro && <ErrorState mensagem={erro} />}
          <form onSubmit={aoSubmeter} className="grid gap-4">
            <CampoTexto
              id="nome"
              name="nome"
              rotulo="Nome"
              type="text"
              autoComplete="name"
              placeholder="Como podemos te chamar…"
              autoFocus
              value={nome}
              onChange={(e) => setNome(e.target.value)}
            />
            <CampoTexto
              id="email"
              name="email"
              rotulo="E-mail"
              type="email"
              required
              autoComplete="email"
              placeholder="voce@exemplo.com…"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
            <CampoTexto
              id="senha"
              name="senha"
              rotulo="Senha"
              type="password"
              required
              minLength={8}
              autoComplete="new-password"
              placeholder="Mínimo de 8 caracteres…"
              value={senha}
              onChange={(e) => setSenha(e.target.value)}
              dica="Mínimo de 8 caracteres."
            />
            <div className="flex items-start gap-2 rounded-lg border border-[var(--cor-borda)] bg-[var(--cor-fundo)] p-3">
              <input
                id="aceite-termos"
                type="checkbox"
                checked={aceiteTermos}
                onChange={(e) => setAceiteTermos(e.target.checked)}
                className="mt-1 h-4 w-4 rounded border-[var(--cor-borda)] accent-[var(--cor-primaria)]"
              />
              <Label htmlFor="aceite-termos" className="text-sm font-normal leading-relaxed">
                Li e aceito os{" "}
                <Link href="/paginas/termos-de-uso" target="_blank" rel="noopener noreferrer" className="font-medium text-[var(--cor-primaria)] underline-offset-4 hover:underline">
                  termos de uso
                </Link>{" "}
                e a{" "}
                <Link href="/privacidade/politica" target="_blank" rel="noopener noreferrer" className="font-medium text-[var(--cor-primaria)] underline-offset-4 hover:underline">
                  política de privacidade
                </Link>
                .
              </Label>
            </div>
            <Button type="submit" tamanho="grande" carregando={cadastrar.isPending} className="w-full">
              Criar minha conta
            </Button>
          </form>
          <p className="text-center text-sm text-[var(--cor-texto-suave)]">
            Já tem conta?{" "}
            <Link href="/login" className="font-medium text-[var(--cor-primaria)] underline-offset-4 hover:underline">
              Entre aqui
            </Link>
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
