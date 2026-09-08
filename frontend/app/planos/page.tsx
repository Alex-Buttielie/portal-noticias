"use client";

import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { useToast } from "@/components/ToastProvider";
import * as api from "@/lib/api";
import { useAssinarPlano, usePlanos } from "@/lib/queries";
import Badge from "@/components/Badge";
import { Button } from "@/components/ui/Button";
import { EmptyState, ErrorState, SkeletonLista } from "@/components/ui/Estados";

function formatarPreco(preco: string): string {
  const numero = Number(preco);
  if (Number.isNaN(numero)) return preco;
  return numero.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

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
    <div>
      <h1>Planos Premium</h1>
      <p className="texto-suave">Sem anúncios e com recursos completos de personalização.</p>

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

      {planosQuery.data?.map((plano) => (
        <div className="plano-cartao" key={plano.id}>
          <h2>{plano.nome}</h2>
          <p className="plano-preco">{formatarPreco(plano.preco)}</p>
          <p className="texto-suave">a cada {plano.duracao_dias} dias</p>
          {usuario?.papel === "premium" && <Badge variante="premium">Você já é Premium</Badge>}
          <div style={{ marginTop: "0.75rem" }}>
            <Button
              disabled={assinar.isPending || usuario?.papel === "premium"}
              carregando={assinar.isPending}
              onClick={() => void assinarPlano(plano.id)}
            >
              {usuario?.papel === "premium" ? "Você já é Premium" : "Assinar"}
            </Button>
          </div>
        </div>
      ))}
    </div>
  );
}
