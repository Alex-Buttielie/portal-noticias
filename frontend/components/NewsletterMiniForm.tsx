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
 *
 * OS TRÊS ESTADOS (o que mudou em 2026-10-02, com o double opt-in)
 * ==============================================================
 * Este é o MESMO formulário que a página `/newsletter` oferece, em miniatura, e
 * por isso ele mostra os mesmos três estados com as mesmas regras. A duplicação
 * de comportamento entre dois formulários é uma armadilha — e ela já aconteceu:
 * o texto desta caixa dizia "Inscrição confirmada. Bom leitura!" em TODO 2xx,
 * o que depois do double opt-in é uma afirmação falsa em toda inscrição nova.
 *
 * As duas decisões que COPIAM de propósito, e não que reimplementam:
 *
 *   - a cor da região de status sai de `classeDoEstadoNewsletter`
 *     (`lib/estado-newsletter.ts`), um lugar só para a regra visual;
 *   - o texto exibido é o `detail` do BACKEND, nunca uma string escrita aqui.
 *     Este arquivo não sabe o que aconteceu; ele mostra o que o servidor disse
 *     que aconteceu.
 *
 * O 503 por ausência de canal de e-mail não tem ramo próprio: cai no `catch`
 * como `ApiError`, e a mensagem do backend é mostrada como está — ela diz o que
 * falta e que nada foi gravado. Um tratamento local do 503 aqui seria uma
 * segunda tradução da mesma resposta, e as duas traduções divergiriam.
 */

import { useEffect, useId, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/lib/auth-context";
import * as api from "@/lib/api";
import { classeDoEstadoNewsletter } from "@/lib/estado-newsletter";

export default function NewsletterMiniForm() {
  const { token } = useAuth();
  const id = useId();
  const [email, setEmail] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  /**
   * O estado da inscrição, separado da mensagem — o mesmo motivo do formulário
   * grande: a cor e o rótulo do botão dependem do ESTADO, e nenhum dos dois
   * pode depender de um `includes` em texto português.
   */
  const [estado, setEstado] = useState<api.EstadoInscricaoNewsletter | null>(null);
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
    setOk(null);
    setEstado(null);
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
        const resposta = await api.inscreverNewsletter(token, { tipo: "padrao" });
        // "Inscrição confirmada. Bom leitura!" aqui seria mentira em toda
        // inscrição nova: com double opt-in, um 201 significa PENDENTE.
        setEstado(resposta.estado ?? (resposta.confirmada ? "confirmada" : "pendente"));
        setOk(resposta.detail?.trim() || null);
      } else {
        await api.assinarNewsletterPublica(limpo, "geral");
        // O caminho público é a lista de espera (`landing/`), que não tem
        // double opt-in e não envia newsletter. O cadastro é a resposta final.
        setEstado("confirmada");
        setOk("Cadastro registrado. Se você entrar com este e-mail, a newsletter é ativada na sua conta.");
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
          {enviando
            ? "Assinando..."
            : estado === "pendente"
              ? "Reenviar"
              : "Assinar"}
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
        <div
          ref={refMsg}
          role="status"
          aria-live="polite"
          tabIndex={-1}
          className={`rounded-md border px-2 py-1.5 text-xs ${classeDoEstadoNewsletter(estado)}`}
        >
          {ok}
          {estado === "pendente" && (
            <span className="mt-1 block text-[var(--cor-texto-suave)]">
              A newsletter só começa a chegar depois de confirmar pelo e-mail.
            </span>
          )}
        </div>
      )}
    </form>
  );
}
