"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import * as api from "@/lib/api";
import { useCadastrar } from "@/lib/queries";
import { Button } from "@/components/ui/button";
import { CampoTexto } from "@/components/ui/FormField";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { CheckCircle2 } from "lucide-react";

interface Erros {
  nome?: string;
  email?: string;
  senha?: string;
  termos?: string;
}

function validar(nome: string, email: string, senha: string, aceiteTermos: boolean): Erros {
  const erros: Erros = {};
  if (!email.trim()) {
    erros.email = "Informe seu e-mail.";
  } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
    erros.email = "Esse e-mail parece inválido. Confira e tente de novo.";
  }
  if (!senha) {
    erros.senha = "Crie uma senha.";
  } else if (senha.length < 8) {
    erros.senha = "A senha precisa de no mínimo 8 caracteres.";
  }
  if (!aceiteTermos) {
    erros.termos = "É necessário aceitar os termos de uso e a política de privacidade.";
  }
  return erros;
}

export default function PaginaCadastro() {
  const cadastrar = useCadastrar();
  const [nome, setNome] = useState("");
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [aceiteTermos, setAceiteTermos] = useState(false);
  const [erros, setErros] = useState<Erros>({});
  const [erroEnvio, setErroEnvio] = useState<string | null>(null);
  const [sucesso, setSucesso] = useState(false);

  function focarPrimeiroErro(novos: Erros) {
    const mapa: Record<string, string> = { nome: "nome", email: "email", senha: "senha", termos: "aceite-termos" };
    for (const campo of Object.keys(mapa)) {
      if (novos[campo as keyof Erros]) {
        document.getElementById(mapa[campo])?.focus();
        break;
      }
    }
  }

  async function aoSubmeter(evento: FormEvent) {
    evento.preventDefault();
    setErroEnvio(null);
    const novos = validar(nome, email, senha, aceiteTermos);
    setErros(novos);
    if (Object.keys(novos).length > 0) {
      focarPrimeiroErro(novos);
      return;
    }
    try {
      await cadastrar.mutateAsync({ email: email.trim(), nome: nome.trim(), senha, aceite_termos: aceiteTermos });
      setSucesso(true);
    } catch (e) {
      setErroEnvio(e instanceof api.ApiError ? e.message : "Não foi possível concluir o cadastro.");
    }
  }

  if (sucesso) {
    return (
      <div className="mx-auto w-full max-w-md px-4 py-10 sm:px-6">
        <Card>
          <CardHeader>
            <CardTitle className="font-[var(--fonte-titulo)] text-2xl">Confirme seu e-mail</CardTitle>
            <CardDescription>
              Enviamos um e-mail de confirmação para{" "}
              <strong className="text-[var(--cor-texto)]">{email}</strong>. Abra sua caixa de entrada e clique no
              link para ativar sua conta.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div aria-live="polite">
              <Alert variant="success">
                <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
                <AlertTitle>Conta criada</AlertTitle>
                <AlertDescription>Falta só a confirmação do e-mail para você entrar.</AlertDescription>
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
            Crie sua conta grátis
          </h1>
          <CardDescription>Leva segundos — depois você personaliza seu feed de notícias.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-6">
          {erroEnvio && (
            <Alert variant="destructive">
              <AlertTitle>Não foi possível criar a conta</AlertTitle>
              <AlertDescription>{erroEnvio}</AlertDescription>
            </Alert>
          )}
          <form onSubmit={aoSubmeter} noValidate className="grid gap-4">
            <CampoTexto
              id="nome"
              name="nome"
              rotulo="Nome"
              type="text"
              autoComplete="name"
              placeholder="Como podemos te chamar…"
              value={nome}
              erro={erros.nome}
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
              erro={erros.email}
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
              erro={erros.senha}
              dica="Mínimo de 8 caracteres."
              onChange={(e) => setSenha(e.target.value)}
            />
            <div className="flex items-start gap-3 rounded-lg border border-[var(--cor-borda)] bg-[var(--cor-fundo)] p-3">
              <Checkbox
                id="aceite-termos"
                checked={aceiteTermos}
                onCheckedChange={(v) => setAceiteTermos(v === true)}
                aria-describedby={erros.termos ? "aceite-termos-erro" : undefined}
                aria-invalid={Boolean(erros.termos)}
              />
              <div className="grid gap-1">
                <Label htmlFor="aceite-termos" className="text-sm font-normal leading-relaxed">
                  Li e aceito os{" "}
                  <Link
                    href="/paginas/termos-de-uso"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="font-medium text-[var(--cor-primaria)] underline-offset-4 hover:underline"
                  >
                    termos de uso
                  </Link>{" "}
                  e a{" "}
                  <Link
                    href="/privacidade/politica"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="font-medium text-[var(--cor-primaria)] underline-offset-4 hover:underline"
                  >
                    política de privacidade
                  </Link>
                  .
                </Label>
                {erros.termos && (
                  <p id="aceite-termos-erro" role="alert" className="text-xs font-medium text-[var(--cor-erro)]">
                    {erros.termos}
                  </p>
                )}
              </div>
            </div>
            <Button type="submit" tamanho="grande" loading={cadastrar.isPending} className="w-full">
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
