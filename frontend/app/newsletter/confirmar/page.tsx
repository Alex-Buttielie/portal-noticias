"use client";

/**
 * Confirmação da inscrição por link (double opt-in).
 *
 * POR QUE A PESSOA NÃO VÊ NADA DIFERENTE QUANDO CONFERMA
 * =======================================================
 * A resposta de `POST /api/newsletter/confirmar/` é a MESMA para token válido,
 * inválido, expirado e já usado, e esta tela mostra o corpo dela sem
 * adaptar. Isso é deliberado e não é uma limitação da tela:
 *
 * O endpoint é `AllowAny` e aceita um segredo. Se a resposta distinguisse
 * "confirmou" de "token inválido", qualquer pessoa com um link — ou quem
 * chute tokens — transformaria o clique numa consulta de "esta pessoa está
 * inscrita no portal?", que é dado do titular (LGPD art. 8º, V) e não
 * informação pública. O mesmo desenho já é usado por `/descadastrar/`, e a
 * razão é idêntica.
 *
 * O texto do backend é escrito para ser verdadeiro nos dois casos ("se o link
 * que você abriu era válido, a inscrição está confirmada"), e esta tela não
 * tenta ser mais esperta que ele.
 *
 * O QUE ESTA TELA FAZ, ALÉM DE MOSTRAR
 * =====================================
 * Ela **não confirma sozinha no carregamento**. Um GET que confirma é um GET
 * que confirma — e a pessoa pode carregar a página duas vezes (recarregar, abrir
 * o link em outro dispositivo, o pré-carregador do cliente de e-mail). Com um
 * botão, cada confirmação é um ato deliberado; e a idempotência do servidor
 * (`test_confirmar_e_idempotente`) faz o resto ser inofensivo de qualquer jeito.
 *
 * Sem token na URL, a tela diz isso e não faz requisição nenhuma — porque um
 * token vazio é 400 do backend, e uma requisição que já se sabe que vai
 * falhar só gasta rede e mostra um erro que a pessoa não caused.
 */

import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import * as api from "@/lib/api";

function tokenDaUrl(): string {
  try {
    return new URLSearchParams(window.location.search).get("token") ?? "";
  } catch {
    /* query string inválida: segue com o campo em branco */
    return "";
  }
}

export default function ConfirmarPage() {
  const [token, setToken] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);
  const emVoo = useRef(false);
  const refMsg = useRef<HTMLParagraphElement>(null);

  // Lê o token da URL. `useEffect` (e não `useSearchParams`) pelo mesmo motivo
  // do `DescadastrarForm`: não exigir boundary de Suspense na build.
  useEffect(() => {
    setToken(tokenDaUrl());
  }, []);

  // Foco depois que a mensagem é montada — durante o handler o ref é `null`.
  useEffect(() => {
    if (msg || erro) refMsg.current?.focus();
  }, [msg, erro]);

  async function confirmar() {
    if (emVoo.current) return; // duplo clique → uma requisição só
    setMsg(null);
    setErro(null);
    const limpo = token.trim();
    if (!limpo) {
      setErro("Abra o link que chegou no e-mail de confirmação. Se ele não estiver no navegador, copie o token e cole abaixo.");
      return;
    }
    emVoo.current = true;
    setEnviando(true);
    try {
      // O corpo da resposta é o que o backend diz, sem adaptação. Ver o
      // cabeçalho: adaptá-lo aqui reabriria o oráculo que a resposta única
      // fecha.
      const resposta = await api.confirmarInscricaoNewsletter(limpo);
      setMsg(resposta?.detail?.trim() || "Pedido de confirmação processado.");
    } catch (e) {
      // Só o 400 de "nenhum token" chega aqui — a resposta é 200 para todo o
      // resto, inclusive token inválido. A mensagem do backend é mostrada como
      // está.
      setErro(e instanceof api.ApiError ? e.message : "Não foi possível confirmar agora. Tente novamente.");
    } finally {
      emVoo.current = false;
      setEnviando(false);
    }
  }

  return (
    <div className="mx-auto max-w-xl space-y-4 py-6">
      <div className="hud-line" aria-hidden />
      <Card className="bento border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
        <CardHeader>
          <CardTitle className="text-[var(--cor-texto)]">Confirmar newsletter</CardTitle>
          <CardDescription className="text-[var(--cor-texto-suave)]">
            Um passo para começar a receber o resumo.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-sm text-[var(--cor-texto-suave)]">
            Você pediu para receber a newsletter. A inscrição só vale depois que este link é
            aberto — até lá, nenhum resumo é enviado para o seu endereço.
          </p>

          {!token && !msg && !erro && (
            <p className="text-sm text-[var(--cor-texto-suave)]">
              O link de confirmação não está nesta URL. Abra o e-mail e clique no link, ou
              cole o token abaixo.
            </p>
          )}

          <div className="space-y-2">
            <label htmlFor="token-confirmacao" className="text-sm font-medium text-[var(--cor-texto)]">
              Token de confirmação
            </label>
            <input
              id="token-confirmacao"
              name="token_confirmacao"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              placeholder="token do link de confirmação"
              autoComplete="off"
              disabled={enviando}
              className="w-full rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] px-3 py-2 text-sm text-[var(--cor-texto)]"
            />
          </div>

          {msg && (
            <p
              ref={refMsg}
              role="status"
              aria-live="polite"
              tabIndex={-1}
              className="rounded-md border border-[var(--cor-sucesso)] bg-[var(--cor-sucesso-suave)] px-3 py-2 text-sm text-[var(--cor-sucesso)]"
            >
              {msg}
            </p>
          )}
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

          <Button
            type="button"
            onClick={confirmar}
            disabled={enviando}
            className="min-h-[44px] w-full bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]"
          >
            {enviando ? "Confirmando..." : "Confirmar inscrição"}
          </Button>

          <p className="text-xs text-[var(--cor-texto-suave)]">
            Não foi você? Nada acontece: a inscrição só vale depois deste clique. Se preferir
            não receber, use o link de cancelamento que também veio no e-mail.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}