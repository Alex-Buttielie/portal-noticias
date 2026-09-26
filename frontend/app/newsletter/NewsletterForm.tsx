"use client";

/**
 * Formulário de assinatura da newsletter + descadastro.
 *
 * Antes: `frontend/app/newsletter/page.tsx:17` tinha `<form>` sem `onSubmit`,
 * um único `<Input>` sem `name`, `<Button type="submit">` inerte e editorias
 * desenhadas como `<Badge cursor-pointer>` sem `onClick` (nada era selecionável).
 * Clicar recarregava a página e o e-mail digitado era perdido.
 *
 * Endpoints usados (ambos reais, conferidos nos `urls.py` de cada app):
 *
 * 1. Visitário AUTENTICADO → `POST /api/newsletter/inscrever/`
 *    - rota:     backend/newsletter/urls.py:8
 *    - mounted:  backend/config/urls.py:23 (`path("api/newsletter/", ...)`)
 *    - view:     backend/newsletter/views.py:9-21 — `IsAuthenticated`;
 *                corpo `{tipo, categorias, periodo}`; 201
 *                `{tipo, periodo, ativa}`; 403 com `{"detail": ...}` quando
 *                `tipo="personalizada"` sem o recurso Premium
 *                (newsletter/services.py:22-25). Só oferecemos `padrao` e
 *                `categoria`, que não são gated.
 *
 * 2. Visitante ANÔNIMO → `POST /api/landing/lista-espera/`
 *    - rota:     backend/landing/urls.py:8
 *    - mounted:  backend/config/urls.py:21
 *    - view:     backend/landing/views.py:10-34 — `AllowAny`; este é o ÚNICO
 *                registro público de e-mail que o backend expõe, já que
 *                `newsletter/inscrever/` exige token. Contrato em
 *                backend/landing/serializers.py:4-17: `nome` e `email`
 *                obrigatórios, `interesses` lista de str, `aceite_comunicacao`
 *                obrigatório.
 *
 * 3. Descadastro → `POST /api/newsletter/descadastrar/`
 *    - rota:     backend/newsletter/urls.py:9
 *    - view:     backend/newsletter/views.py:23-31 — `AllowAny`, token no corpo
 *                ou na query; 400 `{"detail": "Token inválido."}` quando não
 *                casa, o que torna o caminho de erro verificável.
 *
 * O caminho público NÃO envia `periodo`: esse campo só existe em
 * `newsletter/inscrever/` (backend/newsletter/models.py:28-32), então a
 * seleção de período só aparece para quem tem conta — nada é escolhido e
 * descartado em silêncio.
 */

import { useEffect, useId, useRef, useState } from "react";import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/lib/auth-context";
import * as api from "@/lib/api";

const CATS = ["geral", "política", "economia", "tecnologia", "esportes", "cultura", "saúde", "mundo", "cidades"];

function validarEmail(bruto: string): string | null {
  const email = bruto.trim();
  if (!email) return "Informe seu e-mail.";
  if (email.length > 254) return "E-mail muito longo.";
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return "Informe um e-mail válido.";
  return null;
}

export default function NewsletterForm() {
  const { token } = useAuth();
  const idEmail = useId();
  const idNome = useId();

  const [email, setEmail] = useState("");
  const [nome, setNome] = useState("");
  const [cats, setCats] = useState<string[]>([]);
  const [periodo, setPeriodo] = useState<api.PeriodoNewsletter>("manha");

  const [erroEmail, setErroEmail] = useState<string | null>(null);
  const [erroNome, setErroNome] = useState<string | null>(null);
  const [erroGeral, setErroGeral] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  const emVoo = useRef(false);
  const refEmail = useRef<HTMLInputElement>(null);
  const refNome = useRef<HTMLInputElement>(null);
  const refGeral = useRef<HTMLParagraphElement>(null);
  const refSucesso = useRef<HTMLParagraphElement>(null);

  // Foco da região de status em `useEffect`, não logo após o `setState`: o ref
  // só existe a partir do render que monta a mensagem, então `.focus()` dentro
  // do handler veria `null` e o foco não se moveria.
  useEffect(() => {
    if (erroGeral) refGeral.current?.focus();
  }, [erroGeral]);
  useEffect(() => {
    if (ok) refSucesso.current?.focus();
  }, [ok]);

  const alternarCategoria = (c: string) => {
    if (enviando) return;
    setCats((atuais) => (atuais.includes(c) ? atuais.filter((i) => i !== c) : [...atuais, c]));
  };

  async function enviar(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (emVoo.current) return; // duplo clique → uma requisição só

    setOk(null);
    setErroGeral(null);
    setErroEmail(null);
    setErroNome(null);

    const erroDeEmail = validarEmail(email);
    if (erroDeEmail) {
      setErroEmail(erroDeEmail);
      refEmail.current?.focus();
      return;
    }
    // `nome` só é exigido no caminho público, porque é o
    // `landing/serializers.py:5` que o torna obrigatório.
    const precisaNome = !token;
    const nomeLimpo = nome.trim();
    if (precisaNome && !nomeLimpo) {
      setErroNome("Informe seu nome.");
      refNome.current?.focus();
      return;
    }
    if (nomeLimpo.length > 150) {
      setErroNome("Use no máximo 150 caracteres.");
      refNome.current?.focus();
      return;
    }

    emVoo.current = true;
    setEnviando(true);
    try {
      if (token) {
        await api.inscreverNewsletter(token, {
          tipo: cats.length > 0 ? "categoria" : "padrao",
          categorias: cats,
          periodo,
        });
        setOk("Inscrição confirmada. Bom leitura!");
      } else {
        const resposta = await api.inscreverListaEspera({
          nome: nomeLimpo,
          email: email.trim(),
          interesses: cats,
          aceite_comunicacao: true,
        });
        // 201 "Cadastro ... realizado." ou 200 "Este e-mail já está na lista
        // de espera." — nos dois casos o backend confirmou, então a mensagem
        // mostrada é a dele.
        setOk(
          resposta?.detail
            ? `${resposta.detail} Se você entrar com este e-mail, a newsletter é ativada na sua conta.`
            : "Cadastro registrado. Se você entrar com este e-mail, a newsletter é ativada na sua conta."
        );
      }
      // Só limpa depois da confirmação real do servidor.
      setEmail("");
      setNome("");
      setCats([]);
    } catch (erro) {
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
      {/*
        `nome` só aparece (e só é obrigatório) no caminho público: com conta
        logada, `newsletter/inscrever/` vincula a inscrição ao usuário e o
        nome vem do cadastro.
      */}
      {!token && (
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
            className="bg-[var(--cor-fundo-card)]"
          />
          {erroNome && (
            <p id={`${idNome}-erro`} className="text-xs text-[var(--cor-erro)]">
              {erroNome}
            </p>
          )}
        </div>
      )}

      <div className="space-y-2">
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
          disabled={enviando}
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

      <fieldset className="space-y-1.5" disabled={enviando}>
        <legend className="text-sm font-medium text-[var(--cor-texto)]">
          Editorias (opcional)
        </legend>
        <div className="flex flex-wrap gap-1.5">
          {CATS.map((c) => {
            const marcada = cats.includes(c);
            return (
              <button
                key={c}
                type="button"
                onClick={() => alternarCategoria(c)}
                aria-pressed={marcada}
                className={`rounded-full border px-2.5 py-0.5 text-xs font-medium capitalize transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] ${
                  marcada
                    ? "border-[var(--cor-primaria)] bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]"
                    : "border-[var(--cor-borda)] text-[var(--cor-texto)] hover:bg-[var(--cor-primaria-suave)]"
                }`}
              >
                {c}
              </button>
            );
          })}
        </div>
        <p className="text-xs text-[var(--cor-texto-suave)]">
          Sem seleção você recebe o resumo geral.
        </p>
      </fieldset>

      {/* `periodo` existe só em `newsletter/inscrever/` (modelo da newsletter),
          não no registro público — por isso some para visitante anônimo em vez
          de aceitar uma escolha que seria jogada fora. */}
      {token && (
        <fieldset className="space-y-1.5" disabled={enviando}>
          <legend className="text-sm font-medium text-[var(--cor-texto)]">
            Horário de envio
          </legend>
          <div className="flex gap-1.5">
            {(["manha", "noite"] as const).map((p) => (
              <button
                key={p}
                type="button"
                onClick={() => setPeriodo(p)}
                aria-pressed={periodo === p}
                className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] ${
                  periodo === p
                    ? "border-[var(--cor-primaria)] bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]"
                    : "border-[var(--cor-borda)] text-[var(--cor-texto)] hover:bg-[var(--cor-primaria-suave)]"
                }`}
              >
                {p === "manha" ? "Manhã" : "Noite"}
              </button>
            ))}
          </div>
        </fieldset>
      )}

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
        {enviando ? "Enviando..." : "Quero receber"}
      </Button>
    </form>
  );
}

/**
 * Descadastro pelo token do link de descadastro do envio
 * (`POST /api/newsletter/descadastrar/`, backend/newsletter/urls.py:9). Sem
 * isso, o e-mail recebido na prática não tinha caminho de saída pela UI.
 */
export function DescadastrarForm() {
  const idToken = useId();
  const [tokenDesc, setTokenDesc] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);
  const emVoo = useRef(false);
  const refToken = useRef<HTMLInputElement>(null);
  const refMsg = useRef<HTMLParagraphElement>(null);

  // Mesmo motivo do formulário acima: o foco precisa acontecer depois que a
  // mensagem é montada, não no meio do handler.
  useEffect(() => {
    if (erro || ok) refMsg.current?.focus();
  }, [erro, ok]);

  // O link de descadastro chega como `?token=...`. Lido em `useEffect` (e não
  // com `useSearchParams`) para não exigir boundary de Suspense na build.
  useEffect(() => {
    try {
      const vindo = new URLSearchParams(window.location.search).get("token");
      if (vindo) setTokenDesc(vindo);
    } catch {
      /* query string inválida: segue com o campo em branco */
    }
  }, []);

  async function enviar(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (emVoo.current) return;
    setOk(null);
    setErro(null);

    const limpo = tokenDesc.trim();
    if (!limpo) {
      setErro("Cole o token do link de descadastro ou informe seu e-mail de inscrição.");
      refToken.current?.focus();
      return;
    }

    emVoo.current = true;
    setEnviando(true);
    try {
      const resposta = await api.descadastrarNewsletter(limpo);
      setOk(resposta?.detail || "Descadastro realizado.");
      setTokenDesc("");
    } catch (erro) {
      // 400 "Token inválido." chega como ApiError — erro real do backend.
      const mensagem =
        erro instanceof api.ApiError
          ? erro.message
          : "Não foi possível concluir agora. Tente novamente.";
      setErro(mensagem);
    } finally {
      emVoo.current = false;
      setEnviando(false);
    }
  }

  return (
    <form onSubmit={enviar} noValidate className="space-y-2" aria-busy={enviando}>
      <div className="space-y-2">
        <Label htmlFor={idToken}>Token de descadastro</Label>
        <Input
          id={idToken}
          ref={refToken}
          name="token_descadastro"
          value={tokenDesc}
          onChange={(e) => setTokenDesc(e.target.value)}
          placeholder="token do link de descadastro"
          autoComplete="off"
          disabled={enviando}
          className="bg-[var(--cor-fundo-card)]"
        />
      </div>
      {erro && (
        <p
          ref={refMsg}
          role="alert"
          tabIndex={-1}
          className="rounded-md border border-[var(--cor-erro)] bg-[var(--cor-erro-suave)] px-3 py-2 text-sm text-[var(--cor-erro)]"
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
        {enviando ? "Descadastrando..." : "Descadastrar"}
      </Button>
    </form>
  );
}
