"use client";

import * as React from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/auth-context";
import {
  aceitarTodos,
  definirEscolhas,
  obterConsentimento,
  recusarNaoEssenciais,
  sincronizarComBackendSeAutenticado,
} from "@/lib/cookie-consent";

const CATEGORIAS = [
  {
    id: "analytics" as const,
    label: "Analytics",
    descricao: "Ajudam a entender como você interage com o portal.",
  },
  {
    id: "personalizacao" as const,
    label: "Personalização",
    descricao: "Permitem conteúdo e recomendações sob medida para você.",
  },
];

export function BannerConsentimentoCookies() {
  const { token } = useAuth();
  const [aberto, setAberto] = React.useState(false);
  const [analytics, setAnalytics] = React.useState(false);
  const [personalizacao, setPersonalizacao] = React.useState(false);

  React.useEffect(() => {
    const salvo = obterConsentimento();
    if (salvo) {
      setAnalytics(salvo.escolhas.analytics);
      setPersonalizacao(salvo.escolhas.personalizacao);
      setAberto(false);
    } else {
      setAberto(true);
    }
  }, []);

  function fechar() {
    setAberto(false);
    void sincronizarComBackendSeAutenticado(token);
  }

  function aoAceitarTodos() {
    aceitarTodos();
    setAnalytics(true);
    setPersonalizacao(true);
    fechar();
  }

  function aoRecusarNaoEssenciais() {
    recusarNaoEssenciais();
    setAnalytics(false);
    setPersonalizacao(false);
    fechar();
  }

  function aoSalvarPreferencias() {
    definirEscolhas({ analytics, personalizacao });
    fechar();
  }

  return (
    <Dialog open={aberto} onOpenChange={setAberto}>
      <DialogContent
        className={cn(
          "left-[50%] top-auto bottom-0 translate-x-[-50%] translate-y-0 rounded-b-none rounded-t-[var(--raio-lg)]",
          "data-[state=open]:slide-in-from-bottom data-[state=closed]:slide-out-to-bottom",
          "sm:left-auto sm:right-6 sm:top-auto sm:bottom-6 sm:translate-x-0 sm:rounded-[var(--raio-lg)]",
          "max-w-lg pb-[calc(1.5rem+env(safe-area-inset-bottom))] sm:pb-6"
        )}
        aria-describedby="cookies-descricao"
      >
        <DialogHeader className="text-left">
          <DialogTitle>Respeitamos sua privacidade</DialogTitle>
          <DialogDescription id="cookies-descricao">
            Usamos cookies essenciais para o portal funcionar e, com seu consentimento, cookies de
            analytics e personalização. Escolha como quer navegar.
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-3">
          <div className="flex items-start justify-between gap-4 rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo)] p-4 opacity-70">
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium text-[var(--cor-texto)]">
                Essenciais <span className="text-xs font-normal text-[var(--cor-texto-suave)]">(sempre ativos)</span>
              </p>
              <p className="mt-0.5 text-sm text-[var(--cor-texto-suave)]">
                Sessão, tema e o registro deste consentimento.
              </p>
            </div>
            <input
              type="checkbox"
              checked
              disabled
              name="cookie-essenciais"
              aria-label="Cookies essenciais (sempre ativos)"
              className="mt-1 h-4 w-4 shrink-0 cursor-not-allowed rounded border-[var(--cor-borda)] opacity-50"
            />
          </div>

          {CATEGORIAS.map((categoria) => {
            const ativo = categoria.id === "analytics" ? analytics : personalizacao;
            const alternar = categoria.id === "analytics" ? setAnalytics : setPersonalizacao;
            const inputId = `cookie-${categoria.id}`;
            return (
              <div
                key={categoria.id}
                className="flex items-start justify-between gap-4 rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo)] p-4"
              >
                <div className="min-w-0 flex-1">
                  <label htmlFor={inputId} className="cursor-pointer text-sm font-medium text-[var(--cor-texto)]">
                    {categoria.label}
                  </label>
                  <p className="mt-0.5 text-sm text-[var(--cor-texto-suave)]">{categoria.descricao}</p>
                </div>
                <input
                  id={inputId}
                  name={inputId}
                  type="checkbox"
                  checked={ativo}
                  onChange={(e) => alternar(e.target.checked)}
                  aria-label={`Cookies de ${categoria.label.toLowerCase()}`}
                  className={cn(
                    "mt-1 h-4 w-4 shrink-0 cursor-pointer rounded border-[var(--cor-borda)] accent-[var(--cor-primaria)]",
                    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] focus-visible:ring-offset-2"
                  )}
                />
              </div>
            );
          })}
        </div>

        <DialogFooter className="flex-col gap-2 sm:flex-row">
          <Button
            type="button"
            variant="outline"
            onClick={aoRecusarNaoEssenciais}
            className="w-full touch-manipulation min-h-[44px] sm:w-auto"
          >
            Recusar não essenciais
          </Button>
          <Button
            type="button"
            variant="secondary"
            onClick={aoSalvarPreferencias}
            className="w-full touch-manipulation min-h-[44px] sm:w-auto"
          >
            Salvar preferências
          </Button>
          <Button
            type="button"
            onClick={aoAceitarTodos}
            className="w-full touch-manipulation min-h-[44px] sm:w-auto"
          >
            Aceitar todos
          </Button>
        </DialogFooter>

        <p className="text-center text-xs text-[var(--cor-texto-suave)]">
          Altere quando quiser em{" "}
          <Link
            href="/privacidade/preferencias-cookies"
            className="rounded-sm underline underline-offset-2 hover:text-[var(--cor-primaria)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]"
          >
            Preferências de cookies
          </Link>
          .
        </p>
      </DialogContent>
    </Dialog>
  );
}
