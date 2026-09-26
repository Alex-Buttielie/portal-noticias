"use client";

/**
 * Formulário da lista de espera.
 *
 * Antes: `frontend/app/lista-de-espera/page.tsx:9` tinha `<form>` sem
 * `onSubmit`, `<Input>` sem `name` e um `<Button type="submit">` que apenas
 * recarregava a página — o usuário preenchia tudo e a mensagem sumia sem
 * nenhum feedback (pior caso de "submissão vazia").
 *
 * Endpoint usado: `POST /api/landing/lista-espera/`
 *   - rota:    backend/landing/urls.py:8  (`path("lista-espera/", views.ListaEsperaView...)`)
 *   - mounted: backend/config/urls.py:21 (`path("api/landing/", include("landing.urls"))`)
 *   - view:    backend/landing/views.py:10 (POST, `AllowAny`)
 *   - contrato:backend/landing/serializers.py:4-17 — `nome` (obrig., <=150),
 *               `email` (obrig., EmailField), `interesses` (lista de str,
 *               opcional), `aceite_comunicacao` (bool OBRIGATÓRIO e validado
 *               como `True` em `validate_aceite_comunicacao`)
 *   - respostas: 201 `{"detail": "Cadastro na lista de espera realizado."}`,
 *               200 `{"detail": "Este e-mail já está na lista de espera."}`
 *               (idempotente, não é erro), 400 validação, 429 throttle
 *               (20/min — backend/config/throttling.py:24-34,
 *               backend/config/settings.py:371).
 *
 * Não há `alert()` nem `console.log` como feedback: todo caminho (sucesso,
 * erro de validação, erro do servidor, erro de rede) renderiza uma região de
 * status visível e anunciada.
 */

import { useEffect, useId, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import * as api from "@/lib/api";

const INTERESSES = ["geral", "política", "economia", "tecnologia", "esportes", "cultura"];

// Validação em JS: existe de verdade (não é `required` nativo disfarçado), por
// isso o formulário pode usar `noValidate` eivir o validador do navegador sem
// perder a checagem — a mensagem de erro é nossa e vai para a região de status.
function validarEmail(bruto: string): string | null {
  const email = bruto.trim();
  if (!email) return "Informe seu e-mail.";
  if (email.length > 254) return "E-mail muito longo.";
  // Aceita o mesmo subconjunto que o EmailField do DRF considera válido o
  // bastante (backend/landing/serializers.py:7) sem exigir unicidade.
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return "Informe um e-mail válido.";
  return null;
}

export default function ListaEsperaForm() {
  const idNome = useId();
  const idEmail = useId();
  const idAceite = useId();

  const [nome, setNome] = useState("");
  const [email, setEmail] = useState("");
  const [aceite, setAceite] = useState(false);
  const [interesses, setInteresses] = useState<string[]>([]);

  const [erroNome, setErroNome] = useState<string | null>(null);
  const [erroEmail, setErroEmail] = useState<string | null>(null);
  const [erroAceite, setErroAceite] = useState<string | null>(null);
  const [erroGeral, setErroGeral] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  // Guarda síncrona de "já está em voo": o `disabled` sozinho não fecha a
  // janela entre dois cliques (o estado do React só chega ao DOM no próximo
  // render), então o duplo clique viraria duas requisições.
  const emVoo = useRef(false);

  const refNome = useRef<HTMLInputElement>(null);
  const refEmail = useRef<HTMLInputElement>(null);
  const refGeral = useRef<HTMLParagraphElement>(null);
  const refSucesso = useRef<HTMLParagraphElement>(null);

  // O foco da região de status vai num `useEffect`, e não logo depois do
  // `setState`: o ref só é preenchido quando o elemento é montado no render
  // seguinte, então chamar `.focus()` dentro do handler encontraria `null` e o
  // foco nunca se moveria (foi o que a prova de UI pegou).
  useEffect(() => {
    if (erroGeral) refGeral.current?.focus();
  }, [erroGeral]);
  useEffect(() => {
    if (ok) refSucesso.current?.focus();
  }, [ok]);

  const alternarInteresse = (v: string) => {
    if (enviando) return;
    setInteresses((atuais) =>
      atuais.includes(v) ? atuais.filter((i) => i !== v) : [...atuais, v]
    );
  };

  async function enviar(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (emVoo.current) return; // segunda submissão do duplo clique: ignorada

    setOk(null);
    setErroGeral(null);
    setErroNome(null);
    setErroEmail(null);
    setErroAceite(null);

    // Validação ANTES de qualquer fetch: nenhuma requisição pode sair vazia.
    const problemas: { campo: "nome" | "email" | "aceite"; mensagem: string }[] = [];
    const nomeLimpo = nome.trim();
    if (!nomeLimpo) problemas.push({ campo: "nome", mensagem: "Informe seu nome." });
    else if (nomeLimpo.length > 150)
      problemas.push({ campo: "nome", mensagem: "Use no máximo 150 caracteres." });
    const erroDeEmail = validarEmail(email);
    if (erroDeEmail) problemas.push({ campo: "email", mensagem: erroDeEmail });
    if (!aceite)
      problemas.push({
        campo: "aceite",
        mensagem: "É necessário aceitar receber comunicações para entrar na lista.",
      });

    if (problemas.length > 0) {
      // Foco no primeiro campo inválido (mensagem do próprio serializer).
      if (problemas[0].campo === "nome") {
        setErroNome(problemas[0].mensagem);
        refNome.current?.focus();
      } else if (problemas[0].campo === "email") {
        setErroEmail(problemas[0].mensagem);
        refEmail.current?.focus();
      } else {
        setErroAceite(problemas[0].mensagem);
        refGeral.current?.focus();
      }
      const outros = problemas.slice(1);
      if (outros.some((p) => p.campo === "nome")) setErroNome(outros.find((p) => p.campo === "nome")!.mensagem);
      if (outros.some((p) => p.campo === "email")) setErroEmail(outros.find((p) => p.campo === "email")!.mensagem);
      if (outros.some((p) => p.campo === "aceite")) setErroAceite(outros.find((p) => p.campo === "aceite")!.mensagem);
      return;
    }

    emVoo.current = true;
    setEnviando(true);
    try {
      const resposta = await api.inscreverListaEspera({
        nome: nomeLimpo,
        email: email.trim(),
        interesses,
        aceite_comunicacao: true,
      });
      // Sucesso confirmado pelo servidor (201 criado ou 200 "já está na
      // lista") — a mensagem exibida é a do próprio backend, não um texto
      // inventado aqui. Só agora os campos são limpos.
      setOk(resposta?.detail || "Cadastro na lista de espera realizado.");
      setNome("");
      setEmail("");
      setAceite(false);
      setInteresses([]);
    } catch (erro) {
      // Erro do servidor (400 validação / 429 throttle) ou de rede (fetch
      // falhou — api.ts traduz para uma mensagem legível). O que o usuário
      // digitado é PRESERVADO para ele não perder nada.
      const mensagem =
        erro instanceof api.ApiError
          ? erro.message
          : "Não foi possível concluir agora. Tente novamente.";
      setErroGeral(mensagem);
    } finally {
      emVoo.current = false;
      setEnviando(false);
    }
  }

  return (
    <form onSubmit={enviar} noValidate className="space-y-3" aria-busy={enviando}>
      <div className="space-y-2">
        <Label htmlFor={idNome}>Nome</Label>
        <Input
          id={idNome}
          ref={refNome}
          name="nome"
          value={nome}
          onChange={(e) => setNome(e.target.value)}
          placeholder="Seu nome..."
          autoComplete="name"
          maxLength={150}
          disabled={enviando}
          aria-invalid={erroNome ? true : undefined}
          aria-describedby={erroNome ? `${idNome}-erro` : undefined}
        />
        {erroNome && (
          <p id={`${idNome}-erro`} className="text-xs text-[var(--cor-erro)]">
            {erroNome}
          </p>
        )}
      </div>

      <div className="space-y-2">
        <Label htmlFor={idEmail}>Email</Label>
        <Input
          id={idEmail}
          ref={refEmail}
          name="email"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="voce@exemplo.com"
          autoComplete="email"
          maxLength={254}
          disabled={enviando}
          aria-invalid={erroEmail ? true : undefined}
          aria-describedby={erroEmail ? `${idEmail}-erro` : undefined}
        />
        {erroEmail && (
          <p id={`${idEmail}-erro`} className="text-xs text-[var(--cor-erro)]">
            {erroEmail}
          </p>
        )}
      </div>

      <fieldset className="space-y-1.5" disabled={enviando}>
        <legend className="text-sm font-medium text-[var(--cor-texto)]">
          Temas de interesse (opcional)
        </legend>
        <div className="flex flex-wrap gap-1.5">
          {INTERESSES.map((tema) => {
            const marcado = interesses.includes(tema);
            return (
              <button
                key={tema}
                type="button"
                onClick={() => alternarInteresse(tema)}
                aria-pressed={marcado}
                className={`rounded-full border px-2.5 py-0.5 text-xs font-medium capitalize transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] ${
                  marcado
                    ? "border-[var(--cor-primaria)] bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]"
                    : "border-[var(--cor-borda)] text-[var(--cor-texto)] hover:bg-[var(--cor-primaria-suave)]"
                }`}
              >
                {tema}
              </button>
            );
          })}
        </div>
      </fieldset>

      {/* `aceite_comunicacao` é obrigatório no serializer
          (backend/landing/serializers.py:16) — sem este checkbox toda
          submissão tomaria 400. */}
      <div className="space-y-1.5">
        <div className="flex items-start gap-2">
          <Checkbox
            id={idAceite}
            checked={aceite}
            onCheckedChange={(v) => setAceite(v === true)}
            disabled={enviando}
            aria-invalid={erroAceite ? true : undefined}
            aria-describedby={erroAceite ? `${idAceite}-erro` : undefined}
            className="mt-0.5"
          />
          <Label htmlFor={idAceite} className="text-sm font-normal leading-snug text-[var(--cor-texto-suave)]">
            Aceito receber comunicações do portal por e-mail.
          </Label>
        </div>
        {erroAceite && (
          <p id={`${idAceite}-erro`} className="text-xs text-[var(--cor-erro)]">
            {erroAceite}
          </p>
        )}
      </div>

      {/* Região de status: erros em `role="alert"` (anunciado imediatamente),
          sucesso em `aria-live="polite"`. O foco vai para cá para que o
          leitor de tela e a navegação por teclado encontrem a mensagem. */}
      {erroGeral && (
        <p
          ref={refGeral}
          role="alert"
          tabIndex={-1}
          className="rounded-md border border-[var(--cor-erro)] bg-[var(--cor-erro-suave)] px-3 py-2 text-sm text-[var(--cor-erro)]"
        >
          {erroGeral}
        </p>
      )}
      {ok && (
        <p
          ref={refSucesso}
          role="status"
          aria-live="polite"
          tabIndex={-1}
          className="rounded-md border border-[var(--cor-sucesso)] bg-[var(--cor-sucesso-suave)] px-3 py-2 text-sm text-[var(--cor-sucesso)]"
        >
          {ok}
        </p>
      )}

      <Button
        type="submit"
        disabled={enviando}
        className="min-h-[44px] bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]"
      >
        {enviando ? "Enviando..." : "Entrar na lista"}
      </Button>
      <p className="text-xs text-[var(--cor-texto-suave)]">
        Deixe seu e-mail e avisaremos quando liberar.
      </p>
    </form>
  );
}
