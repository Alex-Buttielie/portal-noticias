"use client";

import { useCallback, useEffect, useId, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import * as consentimento from "@/lib/cookie-consent";

/**
 * Banner de consentimento de cookies (implementation-contract.md run
 * 20260903-1134-seo-lgpd-design-system, escopo B — LGPD, critérios de
 * aceite 3 e 4 do task-plan.md).
 *
 * Aparece para qualquer visitante sem escolha registrada (`localStorage`,
 * ver `lib/cookie-consent.ts`) e oferece três ações: "Aceitar todos",
 * "Recusar não essenciais" e "Gerenciar preferências" (expande um painel
 * com um toggle por categoria opcional — "essenciais" é sempre ativa e
 * aparece só como informação, não como controle). Nenhum script de
 * analytics/personalização deste projeto pode inicializar antes de uma
 * dessas ações — hoje não há nenhum desses scripts implementados ainda
 * (ver implementation-history.md), então este componente é a peça de
 * bloqueio que qualquer script futuro dessas categorias deve consultar via
 * `consentimento.permiteCategoria`.
 */
export default function BannerConsentimentoCookies() {
  const { token } = useAuth();
  const [visivel, setVisivel] = useState(false);
  const [gerenciando, setGerenciando] = useState(false);
  const [analyticsRascunho, setAnalyticsRascunho] = useState(false);
  const [personalizacaoRascunho, setPersonalizacaoRascunho] = useState(false);
  const painelId = useId();

  const atualizarVisibilidade = useCallback(() => {
    setVisivel(!consentimento.consentimentoRespondido());
  }, []);

  useEffect(() => {
    atualizarVisibilidade();
    window.addEventListener(consentimento.EVENTO_CONSENTIMENTO_ALTERADO, atualizarVisibilidade);
    return () =>
      window.removeEventListener(consentimento.EVENTO_CONSENTIMENTO_ALTERADO, atualizarVisibilidade);
  }, [atualizarVisibilidade]);

  useEffect(() => {
    if (!gerenciando) return;
    function aoPressionarTecla(evento: KeyboardEvent) {
      if (evento.key === "Escape") setGerenciando(false);
    }
    document.addEventListener("keydown", aoPressionarTecla);
    return () => document.removeEventListener("keydown", aoPressionarTecla);
  }, [gerenciando]);

  if (!visivel) return null;

  function aoAceitarTodos() {
    consentimento.aceitarTodos();
    void consentimento.sincronizarComBackendSeAutenticado(token);
  }

  function aoRecusarNaoEssenciais() {
    consentimento.recusarNaoEssenciais();
    void consentimento.sincronizarComBackendSeAutenticado(token);
  }

  function abrirGerenciar() {
    setAnalyticsRascunho(false);
    setPersonalizacaoRascunho(false);
    setGerenciando(true);
  }

  function aoSalvarPreferencias() {
    consentimento.definirEscolhas({
      analytics: analyticsRascunho,
      personalizacao: personalizacaoRascunho,
    });
    void consentimento.sincronizarComBackendSeAutenticado(token);
    setGerenciando(false);
  }

  return (
    <div className="banner-cookies" role="region" aria-label="Aviso de cookies">
      <div className="banner-cookies-conteudo">
        <p>
          Usamos cookies essenciais para o funcionamento do site. Com o seu consentimento,
          também usamos cookies de análise e personalização para melhorar sua experiência.
          Veja nossa{" "}
          <Link href="/privacidade/politica">política de privacidade</Link>.
        </p>
        <div className="banner-cookies-acoes">
          <button type="button" className="botao botao-secundario" onClick={abrirGerenciar}>
            Gerenciar preferências
          </button>
          <button type="button" className="botao botao-secundario" onClick={aoRecusarNaoEssenciais}>
            Recusar não essenciais
          </button>
          <button type="button" className="botao" onClick={aoAceitarTodos}>
            Aceitar todos
          </button>
        </div>
      </div>

      {gerenciando && (
        <div id={painelId} className="banner-cookies-painel" role="dialog" aria-label="Gerenciar preferências de cookies">
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
              checked={analyticsRascunho}
              onChange={(e) => setAnalyticsRascunho(e.target.checked)}
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
              checked={personalizacaoRascunho}
              onChange={(e) => setPersonalizacaoRascunho(e.target.checked)}
              aria-label="Cookies de personalização"
            />
          </div>
          <div className="banner-cookies-acoes">
            <button type="button" className="botao botao-secundario" onClick={() => setGerenciando(false)}>
              Cancelar
            </button>
            <button type="button" className="botao" onClick={aoSalvarPreferencias}>
              Salvar preferências
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
