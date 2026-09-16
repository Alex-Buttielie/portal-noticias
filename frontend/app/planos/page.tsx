"use client";

import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { useToast } from "@/components/ToastProvider";
import * as api from "@/lib/api";
import { useAssinarPlano, usePlanos } from "@/lib/queries";
import Badge from "@/components/Badge";
import { Button } from "@/components/ui/Button";
import { EmptyState, ErrorState, SkeletonLista } from "@/components/ui/Estados";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Cards";
import { cn } from "@/lib/utils";

function formatarPreco(preco: string): string {
  const numero = Number(preco);
  if (Number.isNaN(numero)) return preco;
  return numero.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

const formatoDuracao = new Intl.NumberFormat("pt-BR");

export default function PaginaPlanos() {
  const router = useRouter();
  const { token, usuario } = useAuth();
  const { notificar } = useToast();
  const planosQuery = usePlanos();
  const assinar = useAssinarPlano();

  async function assinarPlano(planoId: number) {
    if (!token) {
      router.push("/login");
      return;
    }
    try {
      const assinatura = await assinar.mutateAsync(planoId);
      notificar(
        assinatura.status === "ativa"
          ? "Assinatura ativada com sucesso! Aproveite o Premium."
          : "Assinatura criada — aguardando confirmação de pagamento.",
        "sucesso"
      );
    } catch (e) {
      notificar(
        e instanceof api.ApiError ? e.message : "Não foi possível assinar este plano.",
        "erro"
      );
    }
  }

  return (
    <div className="min-w-0 w-full max-w-full space-y-6 overflow-hidden">
      <header className="min-w-0 space-y-1 overflow-hidden">
        <h1 className="break-words font-[var(--fonte-titulo)] text-3xl font-extrabold tracking-[-0.03em] text-wrap-balance">Planos Premium</h1>
        <p className="max-w-[62ch] break-words text-sm text-[var(--cor-texto-suave)]">Sem anúncios e com recursos completos de personalização.</p>
      </header>

      <div aria-live="polite" aria-busy={planosQuery.isLoading || undefined}>
        {planosQuery.isLoading && <SkeletonLista quantidade={3} />}
        {planosQuery.isError && (
          <ErrorState
            mensagem="Não foi possível carregar os planos."
            aoTentarNovamente={() => void planosQuery.refetch()}
          />
        )}
        {!planosQuery.isLoading && !planosQuery.isError && (planosQuery.data?.length ?? 0) === 0 && (
          <EmptyState titulo="Nenhum plano disponível" descricao="Volte em breve." />
        )}
      </div>

      {planosQuery.data && planosQuery.data.length > 0 && (
        <div className="grid w-full max-w-full grid-cols-1 gap-4 overflow-hidden sm:grid-cols-2 lg:grid-cols-3">
          {planosQuery.data.map((plano) => (
            <Card key={plano.id} className={cn("flex min-w-0 flex-col overflow-hidden break-words text-center", usuario?.papel === "premium" && "border-[var(--cor-premium)]/40")}>
              <CardHeader className="min-w-0 space-y-2 overflow-hidden break-words pb-2">
                <CardTitle className="break-words text-center text-lg">{plano.nome}</CardTitle>
                <p className="break-words text-2xl font-bold tracking-tight text-[var(--cor-texto)]">{formatarPreco(plano.preco)}</p>
                <p className="break-words text-xs text-[var(--cor-texto-suave)]">a cada {formatoDuracao.format(plano.duracao_dias)} dias</p>
                {usuario?.papel === "premium" && <div className="flex justify-center"><Badge variante="premium">Você já é Premium</Badge></div>}
              </CardHeader>
              <CardContent className="mt-auto flex min-w-0 justify-center overflow-hidden pt-2">
                <Button
                  disabled={assinar.isPending || usuario?.papel === "premium"}
                  carregando={assinar.isPending}
                  onClick={() => void assinarPlano(plano.id)}
                  aria-label={usuario?.papel === "premium" ? "Você já é Premium" : `Assinar ${plano.nome} por ${formatarPreco(plano.preco)}`}
                  className="w-full min-w-0"
                >
                  {usuario?.papel === "premium" ? "Você já é Premium" : "Assinar"}
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
