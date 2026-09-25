import type { Metadata } from "next";
import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { SITE_NAME } from "@/lib/site";
import { obterUrgentes, type FeedEntrada } from "@/lib/api";
import { formatarDataHoraCompacta } from "@/lib/datas";

export const metadata: Metadata = { title: `Ao vivo — ${SITE_NAME}`, description: `Cobertura ao vivo no ${SITE_NAME} — urgentes em tempo real.` };

export const revalidate = 30;

/**
 * "Ao vivo" mostra SOMENTE o que o backend marcou como urgente.
 *
 * Antes, quando `obterUrgentes` devolvia lista vazia ou lançava, esta página
 * fabricava duas entradas de exemplo e as LIGAVA a `/noticia/11` e
 * `/noticia/12` — Notices com selo LIVE apontando para notícias que não
 * existem. É o pior caso de conteúdo fictício do portal: não é apenas texto de
 * demonstração, é uma manchete urgente falsa com link quebrado, e o rótulo
 * "Atualização contínua a cada 30 segundos" dizia o contrário do que acontecia.
 *
 * Estado vazio aqui é informação real (não há matteria urgente no momento) e é
 * apresentado como tal. Estado de erro também é apresentado como erro, com o
 * código de correlação para quem precisar falar com o suporte.
 */
export default async function Page() {
  let itens: FeedEntrada[] = [];
  let estado: "real" | "vazio" | "erro" = "real";
  let requestId: string | null = null;
  let motivoErro: string | null = null;
  try {
    itens = await obterUrgentes(12);
    if (!itens.length) estado = "vazio";
  } catch (erro) {
    estado = "erro";
    if (erro instanceof Error) {
      requestId = (erro as { requestId?: string | null }).requestId ?? null;
      motivoErro = erro.message;
    }
  }

  return (
    <div className="space-y-4">
      <div className="rounded-[var(--raio-lg)] border border-[var(--cor-sinal)] bg-[var(--cor-fundo-card)] p-4">
        <div className="flex items-center gap-2">
          <span className="h-2 w-2 animate-pulse rounded-full bg-[var(--cor-sinal)]" aria-hidden />
          <h1 className="text-xl font-bold tracking-tight text-[var(--cor-texto)]">Ao vivo</h1>
          <Badge className="bg-[var(--cor-sinal)] text-[var(--cor-texto-invertido)]">LIVE</Badge>
          <span className="ml-auto text-xs text-[var(--cor-texto-suave)]">
            {estado === "real" ? `${itens.length} urgentes` : "sem cobertura urgente"}
          </span>
        </div>
        <div className="hud-line mt-3" aria-hidden />
        <p className="mt-2 text-sm text-[var(--cor-texto-suave)]">
          Manchetes marcadas como urgentes pela redação, atualizadas a cada 30 segundos.
        </p>
      </div>

      {estado === "erro" && (
        <div role="alert" className="rounded-[var(--raio-lg)] border border-[var(--cor-erro)] bg-[var(--cor-erro-suave)] p-4">
          <p className="text-sm font-semibold text-[var(--cor-texto)]">Não foi possível carregar a cobertura urgente.</p>
          <p className="mt-1 text-sm text-[var(--cor-texto-suave)]">
            {motivoErro ?? "Tente novamente em alguns instantes."}
          </p>
          {requestId ? <p className="mt-2 text-xs text-[var(--cor-texto-suave)]">Código de suporte: {requestId}</p> : null}
          <Button asChild variant="outline" className="mt-3 min-h-[44px] border-[var(--cor-borda)]">
            <Link href="/">Ir para a página inicial</Link>
          </Button>
        </div>
      )}

      {estado === "vazio" && (
        <Card className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
          <CardContent className="p-6 text-center">
            <p className="text-sm font-medium text-[var(--cor-texto)]">Nenhuma matéria urgente agora.</p>
            <p className="mt-1 text-sm text-[var(--cor-texto-suave)]">
              A redação não marcou nada como urgente neste momento. As últimas notícias estão na{" "}
              <Link href="/" className="font-medium text-[var(--cor-primaria)] underline">página inicial</Link>.
            </p>
          </CardContent>
        </Card>
      )}

      {estado === "real" && itens.length > 0 && (
        <div className="grid gap-3 md:grid-cols-2">
          {itens.map((n) => (
            <Card key={`${n.tipo}-${n.id}`} className="bento border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
              <CardContent className="p-4">
                <div className="mb-2 flex items-center gap-2">
                  <Badge className="bg-[var(--cor-sinal)] text-[var(--cor-texto-invertido)]">urgente</Badge>
                  <Badge variant="outline" className="border-[var(--cor-borda)] capitalize">{n.categoria}</Badge>
                  <span className="ml-auto text-xs text-[var(--cor-texto-suave)]">{formatarDataHoraCompacta(n.timestamp)} • {n.numero_fontes} fontes</span>
                </div>
                <Link href={`/noticia/${n.id}`} className="font-bold leading-tight text-[var(--cor-texto)] hover:text-[var(--cor-primaria)]">{n.titulo}</Link>
                <p className="mt-1 text-sm text-[var(--cor-texto-suave)]">{n.resumo}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
