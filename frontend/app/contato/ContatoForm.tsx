"use client";

/**
 * Formulário de contato — ligado ao endpoint que existe (item O1 / P1-15c).
 *
 * HISTÓRICO (por que este arquivo mudou): antes o `enviar` NÃO fazia nenhuma
 * chamada de rede. Ele validava o que o usuário digitava e exibia um texto fixo
 * — "o portal não tem um endpoint de mensagens em produção, e o servidor não
 * recebeu nada" — porque `POST /api/contato/` respondia 404. O endpoint foi
 * entregue depois, no item P1-15b (`backend/contato/`), e este arquivo é a
 * segunda metade do caminho: sem ele, o backend existe, está testado e é
 * inalcançável.
 *
 * Contrato usado (lido de `backend/contato/views.py` e
 * `backend/contato/serializers.py`, não adivinhado):
 *   rota:      backend/contato/urls.py:19
 *   mounted:   backend/config/urls.py:44
 *   view:      backend/contato/views.py:115 (POST, `AllowAny`, throttle
 *              `EscritaPublicaAnonThrottle` — 20/min por IP,
 *              config/settings.py:526)
 *   payload:   `{nome, email, mensagem}` + `website` (honeypot: vazio = humano;
 *              preenchido = 400 "Requisição rejeitada." SEM entregar nada)
 *   cliente:   `enviarContato` em `frontend/lib/api.ts`
 *
 * Os TRÊS desfechos que o endpoint entrega, e o que a UI faz com cada um:
 *
 * 1. 200 `{"detail", "id"}` — o provedor ACEITOU E ENTREGOU. Mostra o `detail`
 *    do próprio backend e o `id` (opaco; serve para a pessoa citar a mensagem
 *    depois). Só agora os campos são limpos. `role="status"`.
 * 2. 400 `{campo: ["..."]}` — erro de campo: a mensagem do serializer vai para
 *    baixo do `<Input>`/`<Textarea>` correspondente, com `aria-invalid` e
 *    `aria-describedby`, e o foco vai para o primeiro campo recusado. O texto
 *    digitado é PRESERVADO. O honeypot responde aqui como `non_field_errors`
 *    (a resposta é genérica de propósito), então cai na região geral sem dizer
 *    qual campo foi a armadilha.
 * 3. 503 `{"detail", "request_id"}` — NÃO foi entregue, e nada foi gravado. O
 *    `detail` do backend diz exatamente qual configuração falta (nome do
 *    setting, nunca o valor) e `extrairMensagemDeErro` acrescenta o
 *    `request_id` (frontend/lib/api.ts:57-77). Este é o caminho mais
 *    importante: é o que impede a impressão de sucesso falso. O texto fixo
 *    antigo foi REMOVIDO — a mensagem de indisponibilidade agora é derivada da
 *    resposta real e só aparece se a chamada realmente falhar. Campos
 *    preservados, nunca "enviada".
 *
 * 429 (`Retry-After`) e erro de rede (status 0, sem resposta) entram como
 * falha declarada, nunca como sucesso. `Retry-After` foi lido pelo cliente
 * (`ApiError.retryAfterSegundos`) para dizer por quanto tempo esperar.
 *
 * O que NÃO existe aqui: `alert()`, `console.log` como feedback, sucesso sem
 * confirmação do servidor, e limpeza de campo antes da resposta. O corpo leva
 * exatamente os quatro campos do contrato — `nome`, `email`, `mensagem` e
 * `website` (o honeypot, que vai vazio).
 */

import { useEffect, useId, useRef, useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import ContatoCepIsland from "./ContatoCepIsland";
import * as api from "@/lib/api";

/**
 * De onde veio a falha — muda o que a pessoa lê, não o texto dela:
 * - `validacao`: 400 sem campo reconhecido (honeypot → `non_field_errors`).
 * - `indisponivel`: 503. Havia canal, não houve entrega.
 * - `limite`: 429, com o `Retry-After` traduzido em espera.
 * - `rede`: não houve resposta (status 0).
 * - `servidor`: qualquer outro status (500, 502, 404 de rota, ...).
 */
type TipoDeFalha = "validacao" | "indisponivel" | "limite" | "rede" | "servidor";

interface Falha {
  tipo: TipoDeFalha;
  mensagem: string;
}

function validarEmail(bruto: string): string | null {
  const email = bruto.trim();
  if (!email) return "Informe seu e-mail.";
  if (email.length > 254) return "E-mail muito longo.";
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return "Informe um e-mail válido.";
  return null;
}

/** `Retry-After` (em segundos) virado em frase. `null` quando o header não veio. */
function esperaHumana(segundos: number | null): string | null {
  if (segundos === null) return null;
  if (segundos <= 1) return "Você pode tentar de novo agora.";
  if (segundos < 60) return `Tente de novo em ${segundos} segundos.`;
  const minutos = Math.ceil(segundos / 60);
  return `Tente de novo em cerca de ${minutos} ${minutos === 1 ? "minuto" : "minutos"}.`;
}

/**
 * Achata o corpo de um 400 do DRF (`{campo: ["msg", ...]}`) em
 * `[{campo, mensagem}]`. Também aceita um valor em string solta — o `detail`
 * do DRF é string, não lista —, para que uma chave inesperada não faça o
 * corpo ser engolido em silêncio.
 */
function errosDeCampo(corpo: unknown): { campo: string; mensagem: string }[] {
  if (!corpo || typeof corpo !== "object" || Array.isArray(corpo)) return [];
  return Object.entries(corpo as Record<string, unknown>)
    .map(([campo, valor]) => ({
      campo,
      mensagem: (Array.isArray(valor) ? valor : [valor])
        .filter((v): v is string => typeof v === "string")
        .join(" "),
    }))
    .filter((e) => e.mensagem.length > 0);
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
  const [falha, setFalha] = useState<Falha | null>(null);
  const [ok, setOk] = useState<api.RespostaContato | null>(null);
  const [enviando, setEnviando] = useState(false);
  // Campo que o SERVIDOR recusou num 400, para o foco ir até ele no effect
  // abaixo (não pode ser no handler: durante o envio os campos estão
  // `disabled`, e um `disabled` não recebe foco — o `.focus()` seria um no-op
  // silencioso).
  const [campoRecusado, setCampoRecusado] = useState<"nome" | "email" | "mensagem" | null>(null);

  const refNome = useRef<HTMLInputElement>(null);
  const refEmail = useRef<HTMLInputElement>(null);
  const refMsg = useRef<HTMLTextAreaElement>(null);
  const refFalha = useRef<HTMLDivElement>(null);
  const refOk = useRef<HTMLDivElement>(null);
  // Honeypot: lido por ref, sem estado — não há motivo para re-renderizar a
  // cada tecla de quem preenche um campo que não vê.
  const refArmadilha = useRef<HTMLInputElement>(null);

  // Guarda síncrona de "já está em voo": o `disabled` sozinho não fecha a
  // janela entre dois cliques (o estado do React só chega ao DOM no render
  // seguinte), então o duplo clique viraria duas mensagens para a redação.
  const emVoo = useRef(false);

  // Foco na região de status depois que ela é montada (durante o handler o ref
  // é `null` — `.focus()` ali não acharia o elemento).
  useEffect(() => {
    if (falha) refFalha.current?.focus();
  }, [falha]);
  useEffect(() => {
    if (ok) refOk.current?.focus();
  }, [ok]);
  // Declarado DEPOIS do foco da região geral para ganhar dela quando os dois
  // acontecem: um 400 com campo reconhecido deve levar a pessoa ao campo, e não
  // à caixa de mensagem. Zera o estado depois de focar, senão dois 400s
  // seguidos no mesmo campo não disparariam o effect (mesmo valor).
  useEffect(() => {
    if (!campoRecusado) return;
    if (campoRecusado === "nome") refNome.current?.focus();
    else if (campoRecusado === "email") refEmail.current?.focus();
    else refMsg.current?.focus();
    setCampoRecusado(null);
  }, [campoRecusado]);

  async function enviar(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (emVoo.current) return; // segunda submissão do duplo clique: ignorada

    setOk(null);
    setFalha(null);
    setCampoRecusado(null);
    setErroNome(null);
    setErroEmail(null);
    setErroMsg(null);

    // Validação ANTES de qualquer fetch: nenhuma requisição pode sair vazia, e
    // a mensagem é nossa (o navegador não traria nenhuma — daí `noValidate`).
    // Cada campo inválido recebe a SUA mensagem: bloquear o envio sem explicar
    // o campo seria feedback vazio.
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

    emVoo.current = true;
    setEnviando(true);
    try {
      const resposta = await api.enviarContato({
        nome: nomeLimpo,
        email: emailLimpo,
        mensagem: msgLimpa,
        // Honeypot: presente e VAZIO. Se vier preenchido, o backend descarta
        // a submissão e responde 400 sem entregar nada (serializers.py:69-84).
        website: refArmadilha.current?.value ?? "",
      });

      // 200 só existe depois de o provedor ter aceitado a entrega
      // (services.py:33-40, "NUNCA 2xx SEM ENTREGA"). A mensagem exibida é a
      // do backend, e o `id` vai à parte para a pessoa citar a mensagem.
      setOk({
        detail: resposta?.detail || "O servidor confirmou o recebimento da sua mensagem.",
        id: resposta?.id,
      });
      // Limpar SÓ aqui: enquanto o servidor não confirmou, o texto digitado
      // continua na tela.
      setNome("");
      setEmail("");
      setMsg("");
    } catch (erro) {
      // Nenhum caminho de erro limpa os campos: a pessoa não pode perder o que
      // escreveu por causa de uma falha que é do servidor ou da rede.
      if (!(erro instanceof api.ApiError)) {
        setFalha({
          tipo: "servidor",
          mensagem: "Não foi possível concluir agora. Tente novamente.",
        });
        return;
      }

      if (erro.status === 400) {
        // O DRF não devolve erro de campo e `non_field_errors` na mesma
        // resposta (`validate()` só levanta o não-nomeado depois de todos os
        // campos passarem), então dá para escolher um caminho só: campo
        // reconhecido → vai para o campo; nada reconhecido → vai para a
        // região geral, que é o caso do honeypot.
        const recados = errosDeCampo(erro.detail);
        const atrializados = new Set<string>();
        const semCampo: string[] = [];
        for (const { campo, mensagem } of recados) {
          if (campo === "nome" && !atrializados.has("nome")) {
            setErroNome(mensagem);
            atrializados.add("nome");
          } else if (campo === "email" && !atrializados.has("email")) {
            setErroEmail(mensagem);
            atrializados.add("email");
          } else if (campo === "mensagem" && !atrializados.has("mensagem")) {
            setErroMsg(mensagem);
            atrializados.add("mensagem");
          } else {
            // `non_field_errors` (honeypot) e qualquer chave inesperada: a
            // recusa é real e não pode ser engolida.
            semCampo.push(mensagem);
          }
        }
        const primeiroCampo = (["nome", "email", "mensagem"] as const).find((c) =>
          atrializados.has(c)
        );
        if (primeiroCampo) setCampoRecusado(primeiroCampo);
        else setFalha({ tipo: "validacao", mensagem: semCampo.join(" ") || erro.message });
        return;
      }

      if (erro.status === 503) {
        // O caminho que NÃO pode virar sucesso: nada foi entregue, nada foi
        // gravado, e o `detail` do backend diz qual configuração falta (com o
        // `request_id` acrescentado por `extrairMensagemDeErro`).
        setFalha({ tipo: "indisponivel", mensagem: erro.message });
        return;
      }

      if (erro.status === 429) {
        const espera = esperaHumana(erro.retryAfterSegundos);
        setFalha({
          tipo: "limite",
          mensagem: espera
            ? `O portal aceita poucas mensagens por vez e o limite de envios foi atingido. ${espera}`
            : "O portal aceita poucas mensagens por vez e o limite de envios foi atingido. Tente novamente em instantes.",
        });
        return;
      }

      if (erro.status === 0) {
        // Sem resposta do servidor: `request()` já traduziu para uma frase
        // sobre a conexão (frontend/lib/api.ts:99-105).
        setFalha({ tipo: "rede", mensagem: erro.message });
        return;
      }

      setFalha({ tipo: "servidor", mensagem: erro.message });
    } finally {
      emVoo.current = false;
      setEnviando(false);
    }
  }

  // O 503 e o 429 são "não saiu daqui": nas duas situações a região de status
  // oferece os caminhos que funcionam hoje. Um 400 não — ali o conserto é
  // corrigir o campo, e oferecer newsletter desvia de um erro que a pessoa
  // precisa ver.
  const mostrarAlternativas = falha !== null && falha.tipo !== "validacao";

  return (
    <form onSubmit={enviar} noValidate className="space-y-3" aria-busy={enviando}>
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
          disabled={enviando}
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

      {/* Honeypot. Contrato do backend (`serializers.py:39`, `views.py:45-51`):
          invisível para quem preenche, ignorado quando vazio e motivo de
          descarte quando preenchido. `hidden` + `tabIndex={-1}` +
          `autoComplete="off"` + `aria-hidden` é a combinação documentada em
          `views.py:64-67`; `name="website"` precisa existir para o nome do
          campo ser o que o serializer espera. */}
      <input
        ref={refArmadilha}
        type="text"
        name="website"
        tabIndex={-1}
        autoComplete="off"
        aria-hidden="true"
        className="hidden"
      />

      <ContatoCepIsland />

      {falha && (
        <div
          ref={refFalha}
          role="alert"
          tabIndex={-1}
          className="rounded-md border border-[var(--cor-erro)] bg-[var(--cor-erro-suave)] px-3 py-2 text-sm text-[var(--cor-erro)]"
        >
          <p>{falha.mensagem}</p>
          {mostrarAlternativas && (
            <p className="mt-1 text-xs">
              {falha.tipo === "indisponivel" &&
                "Nada foi gravado: sua mensagem continua aqui na tela. "}
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
          )}
        </div>
      )}

      {ok && (
        <div
          ref={refOk}
          role="status"
          aria-live="polite"
          tabIndex={-1}
          className="rounded-md border border-[var(--cor-sucesso)] bg-[var(--cor-sucesso-suave)] px-3 py-2 text-sm text-[var(--cor-sucesso)]"
        >
          <p>{ok.detail}</p>
          {ok.id && (
            <p className="mt-1 text-xs">
              Identificador da mensagem:{" "}
              <span className="font-mono break-all text-[var(--cor-texto)]">{ok.id}</span>
            </p>
          )}
        </div>
      )}

      <Button
        type="submit"
        disabled={enviando}
        className="min-h-[44px] bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)] hover:bg-[var(--cor-primaria-hover)]"
      >
        {enviando ? "Enviando..." : "Enviar"}
      </Button>
      <p className="text-xs text-[var(--cor-texto-suave)]">Responderemos em até 2 dias úteis.</p>
    </form>
  );
}
