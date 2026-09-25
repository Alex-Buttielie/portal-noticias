"use client";

import { useEffect } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ApiError } from "@/lib/api";
import { consentimentoTecnico } from "@/lib/cookie-consent";
import { capturarErroTecnico } from "@/lib/sentry-cliente";

/**
 * Error boundary da rota (critério 4).
 *
 * O App Router não tinha NENHUM error boundary: qualquer exceção de render
 * subia até o `global-error`... que também não existia, o que devolve a página
 * de erro genérica do Next, sem nenhum caminho de recuperação e sem nenhum
 * código de correlação para o usuário citar.
 *
 * HONESTIDADE DO TEXTO (critérios 5 e 27): a tela só afirma que o erro foi
 * registrado se o visitante tiver concedido a categoria de diagnóstico técnico
 * — e mesmo assim o registro acontece por instrumentos que ainda não estão
 * instalados (Sentry é do Bloco B2). Prometer "já estamos analisando" sem que
 * exista envio seria exatamente o tipo de promessa que a telemetria não
 * sustenta. O texto padrão diz só o que é verdade: a tela quebrou, dá para
 * tentar de novo, e o código ajuda se ele contato o suporte.
 */
export default function ErroDeRota({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // `console.error` aqui é intencional: é o único caminho de diagnóstico que
    // existe sem o Sentry carregado (e continua sendo o que funciona quando o
    // visitante não autorizou diagnóstico). Não leva o erro cru com dados de
    // usuário — só nome, mensagem e código de correlação.
    console.error("[erro-de-rota]", {
      nome: error?.name,
      mensagem: error?.message,
      digest: error?.digest ?? null,
      requestId: error instanceof ApiError ? error.requestId : null,
    });
    // Envio ao Sentry **somente** com consentimento técnico
    // (`capturarErroTecnico` é fail-closed e devolve `false` quando nada foi
    // enviado). O `requestId` viaja como tag, o que amarra o erro do browser ao
    // mesmo id que está no log do Django e na borda.
    void capturarErroTecnico(error, { origem: "error.tsx" });
  }, [error]);

  const ehApi = error instanceof ApiError;
  const requestId = ehApi ? error.requestId : null;
  // O texto abaixo precisa refletir o que ACONTECEU, não o que existe em
  // teoria: `enviado` é o retorno de `capturarErroTecnico` na prática? Não —
  // o envio é assíncrono e happen depois do render. O que decide o texto é a
  // mesma condição que decide o envio (o consentimento), então a frase continua
  // verdadeira, e `capturarErroTecnico` é quem garante que a afirmação não
  // vire promessa vazia.
  // O `digest` é o hash do erro no servidor, não um request id: só é exibido
  // como código de suporte quando existe e quando NÃO há id de requisição
  // melhor, para não sugerir uma correlação que não existe.
  const codigo = requestId ?? error?.digest ?? null;
  const origemCodigo = requestId ? "requisição" : "servidor";
  const diagnosticoAutorizado = consentimentoTecnico();

  return (
    <div className="mx-auto max-w-2xl py-12">
      <Card className="bento border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
        <CardContent className="space-y-4 p-8 text-center">
          <div className="hud-line" aria-hidden />
          <p className="text-xs tracking-widest text-[var(--cor-texto-suave)]">ERRO</p>
          <h1 className="text-2xl font-bold text-[var(--cor-texto)]">Não conseguimos carregar esta página</h1>
          <p className="text-sm text-[var(--cor-texto-suave)]">
            Algo quebrou ao montar o conteúdo. Você pode tentar de novo — nada foi alterado.
          </p>

          {codigo ? (
            <div className="rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-3">
              <p className="text-xs text-[var(--cor-texto-suave)]">
                Código de suporte ({origemCodigo}) — cite ao falar com o suporte:
              </p>
              <p className="mt-1 break-all font-mono text-sm text-[var(--cor-texto)]">{codigo}</p>
            </div>
          ) : null}

          {ehApi && error.status > 0 ? (
            <p className="text-xs text-[var(--cor-texto-suave)]">
              O servidor respondeu com o status {error.status}.
            </p>
          ) : null}

          <p className="text-xs text-[var(--cor-texto-suave)]">
            {diagnosticoAutorizado
              ? "O diagnóstico técnico está autorizado nas suas preferências, então este erro pode ser analisado pela equipe."
              : "Se você preferir, pode autorizar o envio de dados técnicos de diagnóstico nas preferências de cookies — sem isso nada deste erro é registrado."}
          </p>

          <div className="flex flex-wrap justify-center gap-2">
            <Button onClick={() => reset()} className="min-h-[44px] bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]">
              Tentar de novo
            </Button>
            <Button asChild variant="outline" className="min-h-[44px] border-[var(--cor-borda)]">
              <Link href="/">Voltar ao início</Link>
            </Button>
            <Button asChild variant="outline" className="min-h-[44px] border-[var(--cor-borda)]">
              <Link href="/contato">Falar com o suporte</Link>
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
