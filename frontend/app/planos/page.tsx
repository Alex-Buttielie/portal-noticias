"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Check } from "lucide-react";
import { useAuth } from "@/lib/auth-context";
import { useToast } from "@/components/ToastProvider";
import * as api from "@/lib/api";
import { useAssinarPlano, usePlanos } from "@/lib/queries";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { EmptyState, ErrorState, SkeletonLista } from "@/components/ui/Estados";
import { cn } from "@/lib/utils";

function formatarPreco(preco: string): string {
  const numero = Number(preco);
  if (Number.isNaN(numero)) return preco;
  return numero.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

const formatoDuracao = new Intl.NumberFormat("pt-BR");

const RECURSOS_PREMIUM = [
  "Navegue sem anúncios em todo o portal",
  "Personalize seu feed por interesses e localidade",
  "Receba a evolução dos assuntos no Radar",
  "Salve notícias para ler depois, em qualquer dispositivo",
  "Apoie o jornalismo independente brasileiro",
];

const PERGUNTAS_FREQUENTES = [
  {
    pergunta: "Posso cancelar quando quiser?",
    resposta: "Sim. O cancelamento é imediato e você mantém o acesso até o fim do período já pago.",
  },
  {
    pergunta: "Como funciona o pagamento?",
    resposta: "A cobrança é feita no cartão cadastrado a cada ciclo do plano. Você recebe o comprovante por e-mail.",
  },
  {
    pergunta: "Existe teste grátis?",
    resposta: "Novos assinantes começam com um período de teste — o status da sua assinatura mostra exatamente onde você está.",
  },
];

export default function PaginaPlanos() {
  const router = useRouter();
  const { token, usuario } = useAuth();
  const { notificar } = useToast();
  const planosQuery = usePlanos();
  const assinar = useAssinarPlano();
  const ehPremium = usuario?.papel === "premium";

  async function assinarPlano(planoId: number, nomePlano: string) {
    if (!token) {
      router.push("/login");
      return;
    }
    if (!window.confirm(`Assinar o plano ${nomePlano}? A cobrança começa agora.`)) return;
    try {
      const assinatura = await assinar.mutateAsync(planoId);
      notificar(
        assinatura.status === "ativa"
          ? "Assinatura ativada — aproveite seu Premium!"
          : "Assinatura criada — aguardando confirmação do pagamento.",
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
    <div className="min-w-0 w-full max-w-full space-y-8 overflow-hidden">
      <header className="mx-auto min-w-0 max-w-[62ch] space-y-2 overflow-hidden text-center">
        <p className="text-xs font-bold uppercase tracking-[0.14em] text-[var(--cor-primaria)]">Premium</p>
        <h1 className="break-words font-[var(--fonte-titulo)] text-3xl font-extrabold tracking-tight text-wrap-balance sm:text-4xl">
          Assine Premium e leia sem limites
        </h1>
        <p className="break-words text-sm leading-relaxed text-[var(--cor-texto-suave)] sm:text-base">
          Sem anúncios, com feed personalizado e Radar completo — e você ainda sustenta a cobertura que lê todo dia.
        </p>
      </header>

      <div aria-live="polite" aria-busy={planosQuery.isLoading || undefined} className="min-w-0">
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
          {planosQuery.data.map((plano, indice) => {
            const popular = indice === 0;
            return (
              <Card
                key={plano.id}
                className={cn(
                  "relative flex min-w-0 flex-col overflow-hidden break-words pt-4",
                  popular && "border-[var(--cor-primaria)] shadow-[var(--sombra-2)]"
                )}
              >
                {popular && (
                  <div className="absolute left-1/2 top-2 z-10 -translate-x-1/2">
                    <Badge variant="default" className="min-h-0">
                      Mais popular
                    </Badge>
                  </div>
                )}
                <CardHeader className="min-w-0 space-y-2 overflow-hidden break-words pb-2 pt-4 text-center">
                  <CardTitle className="break-words text-center text-lg text-wrap-balance">{plano.nome}</CardTitle>
                  <p className="break-words text-3xl font-bold tracking-tight text-[var(--cor-texto)]">
                    {formatarPreco(plano.preco)}
                  </p>
                  <p className="break-words text-xs text-[var(--cor-texto-suave)]">
                    a cada {formatoDuracao.format(plano.duracao_dias)} dias
                  </p>
                  {ehPremium && (
                    <div className="flex justify-center">
                      <Badge variant="success" className="min-h-0">
                        Você já é Premium
                      </Badge>
                    </div>
                  )}
                </CardHeader>
                <CardContent className="mt-auto flex min-w-0 flex-col gap-4 overflow-hidden pt-2">
                  <ul className="min-w-0 flex-1 space-y-3 text-left">
                    {RECURSOS_PREMIUM.map((recurso) => (
                      <li key={recurso} className="flex min-w-0 items-start gap-3">
                        <Check className="mt-0.5 h-5 w-5 shrink-0 text-[var(--cor-sucesso)]" aria-hidden="true" />
                        <span className="min-w-0 break-words text-sm text-[var(--cor-texto)]">{recurso}</span>
                      </li>
                    ))}
                  </ul>
                  <Button
                    disabled={assinar.isPending || ehPremium}
                    loading={assinar.isPending}
                    onClick={() => void assinarPlano(plano.id, plano.nome)}
                    aria-label={ehPremium ? "Você já é Premium" : `Assinar Premium — ${plano.nome} por ${formatarPreco(plano.preco)}`}
                    className="w-full min-w-0"
                  >
                    {ehPremium ? "Você já é Premium" : "Assinar Premium"}
                  </Button>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      <section className="mx-auto min-w-0 w-full max-w-[720px]" aria-label="Perguntas frequentes">
        <h2 className="break-words font-[var(--fonte-titulo)] text-2xl font-bold tracking-tight text-wrap-balance">
          Perguntas frequentes
        </h2>
        <Accordion type="single" collapsible className="mt-4 w-full min-w-0">
          {PERGUNTAS_FREQUENTES.map((item, indice) => (
            <AccordionItem key={item.pergunta} value={`faq-${indice}`}>
              <AccordionTrigger className="min-w-0 text-left font-medium">
                <span className="min-w-0 break-words">{item.pergunta}</span>
              </AccordionTrigger>
              <AccordionContent>
                <p className="break-words text-sm leading-relaxed text-[var(--cor-texto-suave)]">{item.resposta}</p>
              </AccordionContent>
            </AccordionItem>
          ))}
        </Accordion>
        <p className="mt-6 break-words text-center text-sm text-[var(--cor-texto-suave)]">
          Prefere falar com a gente antes?{" "}
          <Link href="/empresa" className="font-medium text-[var(--cor-primaria)] hover:underline">
            Conheça os planos para empresas
          </Link>
          .
        </p>
      </section>
    </div>
  );
}
