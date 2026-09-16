"use client";

import * as React from "react";
import { Check } from "lucide-react";
import { cn } from "@/lib/utils";
import Badge from "@/components/Badge";
import { Button } from "./button";
import { Card, CardContent, CardHeader, CardTitle } from "./Cards";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "./accordion";

interface PricingPlan {
  id: number;
  nome: string;
  preco: string;
  duracao_dias: number;
  popular?: boolean;
  features: string[];
  ctaText: string;
  ctaHref: string;
  variant?: "default" | "premium";
}

interface PricingTableProps {
  plans: PricingPlan[];
  faq?: { pergunta: string; resposta: string }[];
}

export function PricingTable({ plans, faq }: PricingTableProps) {
  return (
    <div className="space-y-8">
      <div className="grid w-full max-w-full grid-cols-1 gap-4 overflow-hidden lg:grid-cols-2">
        {plans.map((plano) => (
          <Card
            key={plano.id}
            className={cn(
              "flex min-w-0 flex-col overflow-hidden break-words relative",
              plano.popular && "border-[var(--cor-premium)]/40 shadow-[0_0_0_1px_var(--cor-premium)]"
            )}
          >
            {plano.popular && (
              <div className="absolute -top-3 left-1/2 -translate-x-1/2 z-10">
                <Badge variante="premium">Mais popular</Badge>
              </div>
            )}
            <CardHeader className="min-w-0 space-y-2 overflow-hidden break-words pb-2 text-center">
              <CardTitle className="break-words text-center text-lg">{plano.nome}</CardTitle>
              <p className="break-words text-2xl font-bold tracking-tight text-[var(--cor-texto)]">
                R$ {Number(plano.preco).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}
              </p>
              <p className="break-words text-xs text-[var(--cor-texto-suave)]">
                a cada {plano.duracao_dias} dias
              </p>
            </CardHeader>
            <CardContent className="mt-auto flex min-w-0 flex-col gap-4 overflow-hidden pt-2">
              <ul className="flex-1 space-y-3 text-left" role="list">
                {plano.features.map((feature, i) => (
                  <li key={i} className="flex items-start gap-3 min-w-0">
                    <Check
                      className="shrink-0 mt-0.5 h-5 w-5 text-[var(--cor-sucesso)]"
                      aria-hidden="true"
                    />
                    <span className="min-w-0 break-words text-sm text-[var(--cor-texto)]">{feature}</span>
                  </li>
                ))}
              </ul>
              <Button
                variant={plano.variant === "premium" ? "default" : "outline"}
                className="w-full min-w-0"
                asChild
              >
                <a href={plano.ctaHref}>{plano.ctaText}</a>
              </Button>
            </CardContent>
          </Card>
        ))}
      </div>

      {faq && faq.length > 0 && (
        <section aria-label="Perguntas frequentes">
          <h2 className="font-[var(--fonte-titulo)] text-2xl font-bold tracking-tight mb-6">
            Perguntas frequentes
          </h2>
          <Accordion type="single" collapsible className="w-full space-y-2">
            {faq.map((item, index) => (
              <AccordionItem key={index} value={`faq-${index}`}>
                <AccordionTrigger className="text-left font-medium">
                  {item.pergunta}
                </AccordionTrigger>
                <AccordionContent>
                  <p className="text-sm text-[var(--cor-texto-suave)] leading-relaxed">{item.resposta}</p>
                </AccordionContent>
              </AccordionItem>
            ))}
          </Accordion>
        </section>
      )}
    </div>
  );
}