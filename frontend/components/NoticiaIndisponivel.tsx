import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

/**
 * Página de notícia sem conteúdo real, com o código de correlação.
 *
 * Usada por `noticia/[id]`, `noticia/cluster/[id]` e `noticia/item/[id]`
 * quando o backend está indisponível (5xx, timeout, recusa de conexão). É
 * deliberadamente uma RENDERIZAÇÃO DA PRÓPRIA PÁGINA, e não um throw:
 *
 *  - `/noticia/[id]` é uma rota gerada por demanda (ISR). Quando a primeira
 *    geração falha, não existe página em cache para o Next servir, e o
 *    resultado é a página de erro genérica do Next — sem `reset()`, sem
 *    código de suporte e sem nenhuma informação útil. Lançar a exceção
 *    degrada a falha conhecida para uma falha opaca.
 *  - "A notícia não existe" continua sendo 404 de verdade (`notFound()`), e
 *    falha de transporte nunca vira 404: isso mandaria o leitor e o crawler
 *    concluírem que a URL foi removida.
 */
export function NoticiaIndisponivel({
  requestId,
  mensagem,
}: {
  requestId: string | null;
  mensagem: string;
}) {
  return (
    <div className="mx-auto max-w-2xl py-12" role="alert">
      <Card className="bento border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
        <CardContent className="space-y-4 p-8 text-center">
          <div className="hud-line" aria-hidden />
          <p className="text-xs tracking-widest text-[var(--cor-texto-suave)]">NOTÍCIA</p>
          <h1 className="text-2xl font-bold text-[var(--cor-texto)]">
            Não conseguimos carregar esta notícia
          </h1>
          <p className="text-sm text-[var(--cor-texto-suave)]">{mensagem}</p>
          <p className="text-sm text-[var(--cor-texto-suave)]">
            Não exibimos uma notícia de exemplo no lugar da real. Tente novamente em alguns
            instantes.
          </p>
          {requestId ? (
            <div className="rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-3">
              <p className="text-xs text-[var(--cor-texto-suave)]">
                Código de suporte (requisição) — cite ao falar com o suporte:
              </p>
              <p className="mt-1 break-all font-mono text-sm text-[var(--cor-texto)]">{requestId}</p>
            </div>
          ) : null}
          <div className="flex flex-wrap justify-center gap-2">
            <Button asChild className="min-h-[44px] bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]">
              <Link href="/">Voltar ao início</Link>
            </Button>
            <Button asChild variant="outline" className="min-h-[44px] border-[var(--cor-borda)]">
              <Link href="/arquivo">Ver arquivo</Link>
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
