"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import * as api from "@/lib/api";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Card, CardContent, CardDescription, CardHeader } from "@/components/ui/card";
import { LoadingSpinner } from "@/components/ui/Estados";
import { Button } from "@/components/ui/button";
import { CheckCircle2 } from "lucide-react";

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
        setMensagem(e instanceof api.ApiError ? e.message : "Não foi possível verificar o e-mail.");
      });
  }, [token]);

  return (
    <div className="mx-auto w-full max-w-md px-4 py-10 sm:px-6">
      <Card>
        <CardHeader>
          <h1 className="font-[var(--fonte-titulo)] text-2xl font-bold tracking-tight text-balance text-[var(--cor-texto)]">
            Verificação de e-mail
          </h1>
          <CardDescription>Confirme seu endereço para ativar a conta.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-6">
          {estado === "carregando" && <LoadingSpinner rotulo="Verificando…" />}
          <div aria-live="polite">
            {estado === "sucesso" && (
              <div className="grid gap-3">
                <Alert variant="success">
                  <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
                  <AlertTitle>Conta ativada</AlertTitle>
                  <AlertDescription>{mensagem}</AlertDescription>
                </Alert>
                <p className="text-sm text-[var(--cor-texto-suave)]">Sua conta está ativa. Entre para começar a ler.</p>
                <Button asChild tamanho="grande" className="w-full">
                  <Link href="/login">Ir para o login</Link>
                </Button>
              </div>
            )}
            {estado === "erro" && (
              <div className="grid gap-3">
                <Alert variant="destructive">
                  <AlertTitle>Não foi possível verificar</AlertTitle>
                  <AlertDescription>{mensagem}</AlertDescription>
                </Alert>
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
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
