"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import { useToast } from "@/components/ToastProvider";
import * as consentimento from "@/lib/cookie-consent";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { CheckCircle2 } from "lucide-react";

function formatarData(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return new Intl.DateTimeFormat("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" }).format(d);
}

/**
 * Página de gestão de preferências de cookies (implementation-contract.md
 * run 20260903-1134-seo-lgpd-design-system, escopo B — critério de aceite 4
 * do task-plan.md: "acessível a qualquer momento", diferente do banner (que
 * só aparece antes da primeira escolha). Lê/atualiza o mesmo armazenamento
 * (`lib/cookie-consent.ts`) usado pelo `BannerConsentimentoCookies`.
 */
export default function PreferenciasCookiesConteudo() {
  const { token } = useAuth();
  const { notificar } = useToast();
  const [analytics, setAnalytics] = useState(false);
  const [personalizacao, setPersonalizacao] = useState(false);
  const [respondidoEm, setRespondidoEm] = useState<string | null>(null);
  const [salvando, setSalvando] = useState(false);
  const [confirmacao, setConfirmacao] = useState<string | null>(null);

  useEffect(() => {
    const atual = consentimento.obterConsentimento();
    if (atual) {
      setAnalytics(atual.escolhas.analytics);
      setPersonalizacao(atual.escolhas.personalizacao);
      setRespondidoEm(atual.respondidoEm);
    }
  }, []);

  async function persistir(escolhas: { analytics: boolean; personalizacao: boolean }, mensagem: string) {
    setSalvando(true);
    try {
      consentimento.definirEscolhas(escolhas);
      await consentimento.sincronizarComBackendSeAutenticado(token);
      setRespondidoEm(new Date().toISOString());
      setConfirmacao(mensagem);
      notificar(mensagem, "sucesso");
    } finally {
      setSalvando(false);
    }
  }

  function salvar() {
    void persistir({ analytics, personalizacao }, "Preferências de cookies salvas.");
  }

  function aceitarTodos() {
    setAnalytics(true);
    setPersonalizacao(true);
    consentimento.aceitarTodos();
    void persistir({ analytics: true, personalizacao: true }, "Todos os cookies foram aceitos.");
  }

  function recusarNaoEssenciais() {
    setAnalytics(false);
    setPersonalizacao(false);
    consentimento.recusarNaoEssenciais();
    void persistir({ analytics: false, personalizacao: false }, "Cookies não essenciais recusados.");
  }

  return (
    <div className="mx-auto w-full max-w-2xl px-4 py-8 sm:px-6">
      <Card>
        <CardHeader>
          <h1 className="font-[var(--fonte-titulo)] text-2xl font-bold tracking-tight text-balance text-[var(--cor-texto)]">
            Preferências de cookies
          </h1>
          <CardDescription>
            Você controla seus dados: altere sua escolha quando quiser nesta página. Ela vale para este navegador e,
            se você estiver na sua conta, também fica salva no seu perfil.
          </CardDescription>
          {respondidoEm && <p className="text-xs text-[var(--cor-texto-suave)]">Última atualização: {formatarData(respondidoEm)}</p>}
        </CardHeader>
        <CardContent className="grid gap-6">
          <div aria-live="polite">
            {confirmacao && (
              <Alert variant="success">
                <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
                <AlertTitle>Preferência registrada</AlertTitle>
                <AlertDescription>{confirmacao}</AlertDescription>
              </Alert>
            )}
          </div>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              salvar();
            }}
            className="grid gap-4"
          >
            <fieldset className="grid gap-4 rounded-xl border border-[var(--cor-borda)] bg-[var(--cor-fundo)] p-4">
              <legend className="sr-only">Categorias de cookies</legend>
              <div className="flex items-center justify-between gap-4">
                <div>
                  <p className="text-sm font-semibold text-[var(--cor-texto)]">Essenciais</p>
                  <p className="text-xs text-[var(--cor-texto-suave)]">Mantêm o site funcionando. Estão sempre ativos.</p>
                </div>
                <Switch checked disabled aria-label="Cookies essenciais (sempre ativos)" />
              </div>
              <div className="flex items-center justify-between gap-4">
                <Label htmlFor="cookies-analytics" className="grid flex-1 cursor-pointer gap-0.5">
                  <span className="text-sm font-semibold text-[var(--cor-texto)]">Analytics</span>
                  <span className="text-xs font-normal text-[var(--cor-texto-suave)]">Mostram como o site é usado, sem identificar você.</span>
                </Label>
                <Switch id="cookies-analytics" checked={analytics} onCheckedChange={setAnalytics} disabled={salvando} />
              </div>
              <div className="flex items-center justify-between gap-4">
                <Label htmlFor="cookies-personalizacao" className="grid flex-1 cursor-pointer gap-0.5">
                  <span className="text-sm font-semibold text-[var(--cor-texto)]">Personalização</span>
                  <span className="text-xs font-normal text-[var(--cor-texto-suave)]">Adaptam conteúdo e recomendações ao seu perfil.</span>
                </Label>
                <Switch id="cookies-personalizacao" checked={personalizacao} onCheckedChange={setPersonalizacao} disabled={salvando} />
              </div>
            </fieldset>

            <div className="flex flex-wrap gap-3">
              <Button type="button" variante="secundaria" onClick={recusarNaoEssenciais} disabled={salvando}>
                Recusar não essenciais
              </Button>
              <Button type="button" variante="secundaria" onClick={aceitarTodos} disabled={salvando}>
                Aceitar todos
              </Button>
              <Button type="submit" loading={salvando} className="sm:ml-auto">
                Salvar preferências
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
