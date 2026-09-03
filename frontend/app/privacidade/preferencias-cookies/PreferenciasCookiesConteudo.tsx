"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import { useToast } from "@/components/ToastProvider";
import * as consentimento from "@/lib/cookie-consent";

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
    <div>
      <h1>Preferências de cookies</h1>
      <p className="texto-suave">
        Você pode alterar sua escolha a qualquer momento nesta página. Ela vale para este
        navegador e, se você estiver conectado à sua conta, também é salva no seu perfil.
      </p>
      {respondidoEm && (
        <p className="texto-suave">Última atualização: {formatarData(respondidoEm)}</p>
      )}

      <div className="banner-cookies-painel banner-cookies-painel--pagina">
        <div className="campo-toggle">
          <div>
            <strong>Essenciais</strong>
            <p className="texto-suave">Necessários para o site funcionar. Sempre ativos.</p>
          </div>
          <input type="checkbox" checked disabled aria-label="Cookies essenciais (sempre ativos)" />
        </div>
        <div className="campo-toggle">
          <div>
            <strong>Analytics</strong>
            <p className="texto-suave">Nos ajudam a entender como o site é usado.</p>
          </div>
          <input
            type="checkbox"
            checked={analytics}
            onChange={(e) => setAnalytics(e.target.checked)}
            aria-label="Cookies de análise"
          />
        </div>
        <div className="campo-toggle">
          <div>
            <strong>Personalização</strong>
            <p className="texto-suave">Usados para adaptar conteúdo e recomendações ao seu perfil.</p>
          </div>
          <input
            type="checkbox"
            checked={personalizacao}
            onChange={(e) => setPersonalizacao(e.target.checked)}
            aria-label="Cookies de personalização"
          />
        </div>

        <div className="banner-cookies-acoes">
          <button type="button" className="botao botao-secundario" onClick={recusarNaoEssenciais}>
            Recusar não essenciais
          </button>
          <button type="button" className="botao botao-secundario" onClick={aceitarTodos}>
            Aceitar todos
          </button>
          <button type="button" className="botao" onClick={salvar}>
            Salvar preferências
          </button>
        </div>
      </div>
    </div>
  );
}
