"use client";

/**
 * Caixa de assinatura da newsletter da Home.
 *
 * Antes: `frontend/components/HomeClient.tsx:429` tinha
 * `<form action="/newsletter">` com um `<Input>` SEM `name`. Como o atributo
 * `action` faz o navegador navegar para `/newsletter`, o e-mail digitado era
 * descartado e o usuário caía na página da newsletter sem nada preenchido —
 * feedback nenhum e dado perdido.
 *
 * Endpoints (reais, conferidos no backend):
 *   - com sessão:  `POST /api/newsletter/inscrever/` (backend/newsletter/urls.py:8)
 *   - anônimo:     `POST /api/landing/lista-espera/` (backend/landing/urls.py:8),
 *                  o único registro público de e-mail do backend, alcançado
 *                  por `assinarNewsletterPublica` (frontend/lib/api.ts:298).
 *
 * Sucesso, erro de validação, erro do servidor e erro de rede têm todos região
 * de status visível e anunciada; o campo só é limpo quando o servidor confirma.
 */

import { useEffect, useId, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/lib/auth-context";
import * as api from "@/lib/api";

export default function NewsletterMiniForm() {
  const { token } = useAuth();
  const id = useId();
  const [email, setEmail] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [ok, setOk] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const emVoo = useRef(false);
  const refInput = useRef<HTMLInputElement>(null);
  const refMsg = useRef<HTMLParagraphElement>(null);

  // Foco após a montagem da mensagem (o ref ainda é `null` durante o handler).
  useEffect(() => {
    if (erro || ok) refMsg.current?.focus();
  }, [erro, ok]);

  async function enviar(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (emVoo.current) return; // duplo clique → uma requisição só
    setOk(false);
    setErro(null);

    const limpo = email.trim();
    // Validação real em JS antes de qualquer fetch: nada de requisição vazia.
    if (!limpo) {
      setErro("Informe seu e-mail.");
      refInput.current?.focus();
      return;
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(limpo)) {
      setErro("Informe um e-mail válido.");
      refInput.current?.focus();
      return;
    }

    emVoo.current = true;
    setEnviando(true);
    try {
      if (token) {
        await api.inscreverNewsletter(token, { tipo: "padrao" });
        setOk(true);
      } else {
        await api.assinarNewsletterPublica(limpo, "geral");
        setOk(true);
      }
      // Limpa só depois da confirmação real do servidor.
      setEmail("");
    } catch (e) {
      // Preserva o e-mail digitado para o usuário não perder o que escreveu.
      const mensagem =
        e instanceof api.ApiError
          ? e.message
          : "Não foi possível assinar agora. Tente novamente.";
      setErro(mensagem);
    } finally {
      emVoo.current = false;
      setEnviando(false);
    }
  }

  return (
    <form onSubmit={enviar} noValidate className="mt-3 flex flex-col gap-2" aria-busy={enviando}>
      <div className="flex gap-2">
        <Input
          id={id}
          ref={refInput}
          name="email"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="seu@email.com"
          autoComplete="email"
          maxLength={254}
          disabled={enviando}
          aria-label="Email para newsletter"
          aria-invalid={erro ? true : undefined}
          className="h-9 bg-[var(--cor-fundo-card)]"
        />
        <Button
          type="submit"
          disabled={enviando}
          className="h-9 shrink-0 bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)] hover:bg-[var(--cor-primaria-hover)]"
        >
          {enviando ? "Assinando..." : "Assinar"}
        </Button>
      </div>
      {erro && (
        <p
          ref={refMsg}
          role="alert"
          tabIndex={-1}
          className="text-xs text-[var(--cor-erro)]"
        >
          {erro}
        </p>
      )}
      {ok && (
        <p
          ref={refMsg}
          role="status"
          aria-live="polite"
          tabIndex={-1}
          className="text-xs text-[var(--cor-sucesso)]"
        >
          Inscrição confirmada. Bom leitura!
        </p>
      )}
    </form>
  );
}
