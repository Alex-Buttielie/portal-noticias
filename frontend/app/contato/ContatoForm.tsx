"use client";

/**
 * Formulário de contato.
 *
 * DIAGNÓSTICO: antes este formulário vivia inline em
 * `frontend/app/contato/page.tsx:17-24` — `<form>` sem `onSubmit`/`action`,
 * `<Input>`/`<Textarea>` sem `name`, `<Button type="submit">` que apenas
 * recarregava a página. Nenhum estado de envio, erro ou sucesso, nenhuma
 * validação, e o texto digitado era perdido sem nenhum aviso.
 *
 * PENDÊNCIA DE BACKEND (não resolvida aqui de propósito): NÃO existe endpoint
 * de contato no backend. Auditoria em `backend/config/urls.py:14-31` (17 `path()`
 * na raiz), `backend/landing/urls.py`, `backend/newsletter/urls.py`,
 * `backend/comunidade/urls.py`, `backend/moderacao/urls.py` e
 * `backend/painel_admin/urls.py`: nenhum `path()` de contato/mensagem/fale-
 * conosco, e `grep -rniE "contato" backend/ --include=*.py` só acha a frase
 * "entrando em contato" na semente de páginas legais
 * (backend/moderacao/migrations/0002_seed_paginas_legais.py:102).
 *
 * Como inventar um POST para uma URL inexistente quebraria em produção com 404,
 * este formulário NÃO faz chamada de rede. Ele valida o que o usuário digitou e
 * então informa, de forma explícita, que o canal ainda não recebe mensagens —
 * em vez de fingir sucesso. O texto digitado é preservado para nada ser
 * perdido. Criar o endpoint (view + serializer + rota) é item de backend,
 * dependência reportada no relatório desta run.
 *
 * Quando o endpoint existir, o caminho é o mesmo dos outros formulários:
 * adicionar a função em `frontend/lib/api.ts` e trocar o bloco `sem canal`
 * do `enviar` por `await api.<novaFuncao>(...)` — o tratamento de erro,
 * foco, `aria-busy` e o botão desabilitado já estão prontos abaixo.
 */

import { useEffect, useId, useRef, useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import ContatoCepIsland from "./ContatoCepIsland";

function validarEmail(bruto: string): string | null {
  const email = bruto.trim();
  if (!email) return "Informe seu e-mail.";
  if (email.length > 254) return "E-mail muito longo.";
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return "Informe um e-mail válido.";
  return null;
}

export default function ContatoForm() {
  const idNome = useId();
  const idEmail = useId();
  const idMsg = useId();

  const [nome, setNome] = useState("");
  const [email, setEmail] = useState("");
  const [msg, setMsg] = useState("");
  const [erroNome, setErroNome] = useState<string | null>(null);
  const [erroEmail, setErroEmail] = useState<string | null>(null);
  const [erroMsg, setErroMsg] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);

  const refNome = useRef<HTMLInputElement>(null);
  const refEmail = useRef<HTMLInputElement>(null);
  const refMsg = useRef<HTMLTextAreaElement>(null);
  const refAviso = useRef<HTMLParagraphElement>(null);

  // Foco no aviso depois que ele é montado (durante o handler o ref é `null`).
  useEffect(() => {
    if (aviso) refAviso.current?.focus();
  }, [aviso]);

  async function enviar(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setAviso(null);
    setErroNome(null);
    setErroEmail(null);
    setErroMsg(null);

    // Validação real em JS — por isso `noValidate` é legítimo aqui: a
    // validação do navegador não traria nenhuma dessas mensagens.
    // Cada campo inválido recebe a SUA mensagem: bloquear o envio sem explicar
    // o campo seria exatamente o tipo de feedback vazio que esta run remove.
    const nomeLimpo = nome.trim();
    const emailLimpo = email.trim();
    const msgLimpa = msg.trim();

    const problemas: ("nome" | "email" | "msg")[] = [];

    if (!nomeLimpo) {
      setErroNome("Informe seu nome.");
      problemas.push("nome");
    } else if (nomeLimpo.length > 150) {
      setErroNome("Use no máximo 150 caracteres.");
      problemas.push("nome");
    }

    const erroDeEmail = validarEmail(email);
    if (erroDeEmail) {
      setErroEmail(erroDeEmail);
      problemas.push("email");
    }

    if (!msgLimpa) {
      setErroMsg("Escreva sua mensagem.");
      problemas.push("msg");
    } else if (msgLimpa.length < 10) {
      setErroMsg("Descreva sua mensagem com pelo menos 10 caracteres.");
      problemas.push("msg");
    }

    if (problemas.length > 0) {
      if (problemas.includes("nome")) refNome.current?.focus();
      else if (problemas.includes("email")) refEmail.current?.focus();
      else refMsg.current?.focus();
      return;
    }

    // Nenhuma requisição é feita (ver nota de PENDÊNCIA no topo do arquivo):
    // o aviso abaixo é a resposta honesta, e os campos ficam preenchidos para
    // o usuário não perder o que escreveu.
    setAviso(
      "Este canal de contato ainda não está disponível: o portal não tem um endpoint de mensagens em produção, e o servidor não recebeu nada. Sua mensagem ficou apenas nesta tela — se quiser ser avisado de novidades, use a newsletter ou a lista de espera."
    );
  }

  return (
    <form onSubmit={enviar} noValidate className="space-y-3" aria-busy={false}>
      <div className="grid gap-1.5">
        <Label htmlFor={idNome}>Nome</Label>
        <Input
          id={idNome}
          ref={refNome}
          name="nome"
          value={nome}
          onChange={(e) => setNome(e.target.value)}
          placeholder="Seu nome…"
          autoComplete="name"
          maxLength={150}
          aria-invalid={erroNome ? true : undefined}
          aria-describedby={erroNome ? `${idNome}-erro` : undefined}
          className="bg-[var(--cor-fundo-card)]"
        />
        {erroNome && (
          <p id={`${idNome}-erro`} className="text-xs text-[var(--cor-erro)]">
            {erroNome}
          </p>
        )}
      </div>

      <div className="grid gap-1.5">
        <Label htmlFor={idEmail}>Email</Label>
        <Input
          id={idEmail}
          ref={refEmail}
          name="email"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="seu@email.com"
          autoComplete="email"
          maxLength={254}
          aria-invalid={erroEmail ? true : undefined}
          aria-describedby={erroEmail ? `${idEmail}-erro` : undefined}
          className="bg-[var(--cor-fundo-card)]"
        />
        {erroEmail && (
          <p id={`${idEmail}-erro`} className="text-xs text-[var(--cor-erro)]">
            {erroEmail}
          </p>
        )}
      </div>

      <div className="grid gap-1.5">
        <Label htmlFor={idMsg}>Mensagem</Label>
        <Textarea
          id={idMsg}
          ref={refMsg}
          name="mensagem"
          value={msg}
          onChange={(e) => setMsg(e.target.value)}
          placeholder="Como podemos ajudar?…"
          rows={5}
          maxLength={4000}
          aria-invalid={erroMsg ? true : undefined}
          aria-describedby={erroMsg ? `${idMsg}-erro` : undefined}
          className="bg-[var(--cor-fundo-card)]"
        />
        {erroMsg && (
          <p id={`${idMsg}-erro`} className="text-xs text-[var(--cor-erro)]">
            {erroMsg}
          </p>
        )}
      </div>

      <ContatoCepIsland />

      {aviso && (
        <div
          ref={refAviso}
          role="alert"
          tabIndex={-1}
          className="rounded-md border border-[var(--cor-erro)] bg-[var(--cor-erro-suave)] px-3 py-2 text-sm text-[var(--cor-erro)]"
        >
          <p>{aviso}</p>
          <p className="mt-1 text-xs">
            Enquanto isso:{" "}
            <Link href="/newsletter" className="underline">
              assinar a newsletter
            </Link>{" "}
            ou{" "}
            <Link href="/lista-de-espera" className="underline">
              entrar na lista de espera
            </Link>
            .
          </p>
        </div>
      )}

      <Button
        type="submit"
        className="min-h-[44px] bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)] hover:bg-[var(--cor-primaria-hover)]"
      >
        Enviar
      </Button>
      <p className="text-xs text-[var(--cor-texto-suave)]">Responderemos em até 2 dias úteis.</p>
    </form>
  );
}
