"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import * as api from "@/lib/api";
import { ErrorState, LoadingSpinner } from "@/components/ui/Estados";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/Cards";
import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/utils";

export default function VerificarEmailConteudo() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token");
  const [estado, setEstado] = useState<"carregando" | "sucesso" | "erro">("carregando");
  const [mensagem, setMensagem] = useState("");

  useEffect(() => {
    if (!token) {
      setEstado("erro");
      setMensagem("Link de verificação inválido — token não encontrado na URL.");
      return;
    }
    api
      .verificarEmail(token)
      .then((resposta) => {
        setEstado("sucesso");
        setMensagem(resposta.detail);
      })
      .catch((e: unknown) => {
        setEstado("erro");
        setMensagem(
          e instanceof api.ApiError ? e.message : "Não foi possível verificar o e-mail."
        );
      });
  }, [token]);

  return (
<div className={cn("container mx-auto max-w-md px-4 py-10 sm:px-6")}>
      <Card className="shadow-lg secao-bloco mensagem-sucesso botao botao--primaria botao--medio">
        <CardHeader className="space-y-2">
          <p className="text-xs font-bold uppercase tracking-widest text-[var(--cor-primaria)] secao-eyebrow">Confirmação de conta</p>
          <CardTitle id="verificar-titulo" className="text-2xl">
            Verificação de e-mail
          </CardTitle>
          <CardDescription>Confirme seu endereço para ativar a conta.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-6">
          {estado === "carregando" && <LoadingSpinner rotulo="Verificando…" />}
          {estado === "sucesso" && (
            <div className="grid gap-3 container--estreito">
              <div className="rounded-md border border-[var(--cor-sucesso)]/20 bg-[var(--cor-sucesso)]/10 px-4 py-3 text-sm text-[var(--cor-sucesso)]">
                {mensagem}
              </div>
              <p className="text-sm text-[var(--cor-texto-suave)]">Sua conta está ativa. Entre para começar a ler.</p>
              <Button asChild className="w-full" tamanho="grande">
                <Link href="/login">Ir para o login</Link>
              </Button>
            </div>
          )}
          {estado === "erro" && (
            <div className="grid gap-3">
              <ErrorState mensagem={mensagem} />
              <p className="text-center text-sm text-[var(--cor-texto-suave)]">
                O link expirou ou já foi usado?{" "}
                <Link href="/cadastro" className="font-medium text-[var(--cor-primaria)] hover:underline">
                  Crie outra conta
                </Link>{" "}
                ou{" "}
                <Link href="/login" className="font-medium text-[var(--cor-primaria)] hover:underline">
                  tente entrar
                </Link>
                .
              </p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
