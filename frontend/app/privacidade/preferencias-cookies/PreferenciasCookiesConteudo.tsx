"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import { useToast } from "@/components/ToastProvider";
import * as consentimento from "@/lib/cookie-consent";
import { Button } from "@/components/ui/Button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/Cards";
import { Label } from "@/components/ui/FormField";
import { cn } from "@/lib/utils";

function formatarData(iso: string): string {
  try {
    return new Date(iso).toLocaleString("pt-BR", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
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

  useEffect(() => {
    const atual = consentimento.obterConsentimento();
    if (atual) {
      setAnalytics(atual.escolhas.analytics);
      setPersonalizacao(atual.escolhas.personalizacao);
      setRespondidoEm(atual.respondidoEm);
    }
  }, []);

  function salvar() {
    consentimento.definirEscolhas({ analytics, personalizacao });
    void consentimento.sincronizarComBackendSeAutenticado(token);
    setRespondidoEm(new Date().toISOString());
    notificar("Preferências de cookies salvas.", "sucesso");
  }

  function aceitarTodos() {
    setAnalytics(true);
    setPersonalizacao(true);
    consentimento.aceitarTodos();
    void consentimento.sincronizarComBackendSeAutenticado(token);
    setRespondidoEm(new Date().toISOString());
    notificar("Todos os cookies foram aceitos.", "sucesso");
  }

  function recusarNaoEssenciais() {
    setAnalytics(false);
    setPersonalizacao(false);
    consentimento.recusarNaoEssenciais();
    void consentimento.sincronizarComBackendSeAutenticado(token);
    setRespondidoEm(new Date().toISOString());
    notificar("Cookies não essenciais recusados.", "sucesso");
  }

  return (
<div className={cn("container mx-auto max-w-2xl px-4 py-8 sm:px-6")}>
      <Card className="shadow-sm secao-bloco banner-cookies-painel banner-cookies-painel--pagina campo-toggle banner-cookies-acoes">
        <CardHeader className="space-y-2">
          <p className="text-xs font-bold uppercase tracking-widest text-[var(--cor-primaria)] secao-eyebrow">Privacidade</p>
          <CardTitle id="cookies-titulo" className="text-2xl">
            Preferências de cookies
          </CardTitle>
          <CardDescription>
            Você controla seus dados: altere sua escolha quando quiser nesta página. Ela vale para este navegador e, se você
            estiver na sua conta, também fica salva no seu perfil.
          </CardDescription>
          {respondidoEm && <p className="text-xs text-[var(--cor-texto-suave)]">Última atualização: {formatarData(respondidoEm)}</p>}
        </CardHeader>
        <CardContent className="grid gap-6">
          <div className="grid gap-4 rounded-xl border border-[var(--cor-borda)] bg-[var(--cor-fundo)] p-4 container--estreito">
            <div className="flex items-center justify-between gap-4">
              <div>
                <p className="text-sm font-semibold text-[var(--cor-texto)]">Essenciais</p>
                <p className="text-xs text-[var(--cor-texto-suave)]">Mantêm o site funcionando. Estão sempre ativos.</p>
              </div>
              <input type="checkbox" checked disabled aria-label="Cookies essenciais (sempre ativos)" className="h-5 w-5 accent-[var(--cor-primaria)]" />
            </div>
            <div className="flex items-center justify-between gap-4">
              <div>
                <p className="text-sm font-semibold text-[var(--cor-texto)]">Analytics</p>
                <p className="text-xs text-[var(--cor-texto-suave)]">Mostram como o site é usado, sem identificar você.</p>
              </div>
              <input
                type="checkbox"
                checked={analytics}
                onChange={(e) => setAnalytics(e.target.checked)}
                aria-label="Cookies de análise"
                className="h-5 w-5 accent-[var(--cor-primaria)]"
              />
            </div>
            <div className="flex items-center justify-between gap-4">
              <div>
                <p className="text-sm font-semibold text-[var(--cor-texto)]">Personalização</p>
                <p className="text-xs text-[var(--cor-texto-suave)]">Adaptam conteúdo e recomendações ao seu perfil.</p>
              </div>
              <input
                type="checkbox"
                checked={personalizacao}
                onChange={(e) => setPersonalizacao(e.target.checked)}
                aria-label="Cookies de personalização"
                className="h-5 w-5 accent-[var(--cor-primaria)]"
              />
            </div>
          </div>

          <div className="flex flex-wrap gap-3">
            <Button variante="secundaria" onClick={recusarNaoEssenciais}>
              Recusar não essenciais
            </Button>
            <Button variante="secundaria" onClick={aceitarTodos}>
              Aceitar todos
            </Button>
            <Button onClick={salvar} className="ml-auto">
              Salvar preferências
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
