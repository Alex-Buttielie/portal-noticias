"use client";

/**
 * Botão "Continuar com Google" na tela de login (P1-05b).
 *
 * TRÊS ESTADOS, e o terceiro é o que importa:
 *
 *  - `ocioso`    — botão visível, clicável.
 *  - `carregando`— nonce emitido, script do Google a caminho, ou popup do Google
 *                  aberto esperando a credencial. Botão travado, sem estado
 *                  "meio logado": enquanto a credencial não voltou, ninguém
 *                  está autenticado.
 *  - `erro`      — mensagem renderizada em `role="alert"`, com o botão de novo.
 *                  NÃO existe estado de sucesso aqui: quem redireciona é o
 *                  pai, e só depois que `POST /api/auth/google/` devolveu
 *                  token (ver `lib/google-oauth.ts`).
 *
 * POR QUE UM PASSO EXTRA (o botão do Google aparece depois do nosso)
 * O botão do Google Identity Services só existe DEPOIS que o script do Google
 * carrega, e o script só carrega no clique (é a regra de privacidade: nada sai
 * antes de a pessoa agir). Não há como ter o botão do Google na tela antes
 * disso. Então: o clique em "Continuar com Google" emite o nonce e carrega o
 * script; o botão do Google entra no lugar; o segundo clique é o consentimento
 * no popup. É a consequência honesta da regra, e ela está escrita no texto de
 * ajuda em vez de escondida atrás de um clique automático.
 */

import { useCallback, useRef, useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import {
  classificarErroGoogle,
  googleDisponivel,
  iniciarFluxoGoogle,
  novoErroGoogle,
  type CodigoErroGoogle,
} from "@/lib/google-oauth";
import type { RespostaLoginGoogle } from "@/lib/api";

type EstadoBotao = "ocioso" | "carregando" | "erro";

interface ErroApresentavel {
  codigo: CodigoErroGoogle;
  mensagem: string;
}

/** Sem `NEXT_PUBLIC_GOOGLE_OAUTH_CLIENT_ID` não há botão do Google para
 *  mostrar; o texto é o mesmo que a UI mostraria se a pessoa clicasse. */
const ERRO_NAO_CONFIGURADO = classificarErroGoogle(novoErroGoogle("nao_configurado"));

export function BotaoGoogle({
  aoConcluir,
}: {
  /** Chamado SÓ depois do `POST /api/auth/google/` devolver token. */
  aoConcluir: (resposta: RespostaLoginGoogle) => void | Promise<void>;
}) {
  // O estado nasce em `erro` quando o ambiente não tem `client_id`: um botão
  // que leva a uma parede é pior que uma explicação. O botão continua na tela
  // (e clicável) para o caso de o bundle ser refeito com a variável presente.
  const [estado, setEstado] = useState<EstadoBotao>(() =>
    googleDisponivel() ? "ocioso" : "erro"
  );
  const [erro, setErro] = useState<ErroApresentavel | null>(() =>
    googleDisponivel() ? null : ERRO_NAO_CONFIGURADO
  );
  const [aceite, setAceite] = useState(false);
  const [botaoGoogleVisivel, setBotaoGoogleVisivel] = useState(false);
  const refGoogle = useRef<HTMLDivElement | null>(null);

  const registrarErro = useCallback((bruto: unknown) => {
    setBotaoGoogleVisivel(false);
    setErro(classificarErroGoogle(bruto));
    setEstado("erro");
  }, []);

  const aoClicar = useCallback(async () => {
    const container = refGoogle.current;
    if (!container) {
      registrarErro(undefined);
      return;
    }
    setErro(null);
    setEstado("carregando");
    setBotaoGoogleVisivel(false);
    try {
      const resposta = await iniciarFluxoGoogle({
        aceiteTermos: aceite,
        container,
        aoExibirBotaoGoogle: () => setBotaoGoogleVisivel(true),
        aoExpirarNonce: () => {
          setBotaoGoogleVisivel(false);
          setErro({
            codigo: "nonce_expirado",
            mensagem:
              "A janela do login com Google passou do tempo. Clique de novo para recomeçar.",
          });
          setEstado("erro");
        },
      });
      // Único caminho de sucesso: o POST final voltou com token. O pai adota a
      // sessão e redireciona; aqui não se marca nada como "logado".
      await aoConcluir(resposta);
    } catch (bruto) {
      registrarErro(bruto);
    }
  }, [aceite, aoConcluir, registrarErro]);

  const carregando = estado === "carregando";

  return (
    <div className="space-y-3">
      <div className="relative">
        <Button
          type="button"
          onClick={aoClicar}
          disabled={carregando}
          aria-busy={carregando}
          className="w-full min-h-[44px] border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] text-[var(--cor-texto)] hover:bg-[var(--cor-fundo-card)]"
        >
          {carregando ? "Conectando ao Google…" : "Continuar com Google"}
        </Button>
        {/* O botão do Google entra aqui, por cima do nosso, só depois que o
            script carregou. Fica sempre montado (e escondido) para que o
            `ref` exista no momento do clique. */}
        <div
          ref={refGoogle}
          data-estado-google={botaoGoogleVisivel ? "visivel" : "oculto"}
          className={
            botaoGoogleVisivel
              ? "flex w-full justify-center [&>div]:w-full"
              : "hidden"
          }
        />
      </div>

      {/* A dica aparece QUANDO o botão do Google já está na tela — inclusive
          durante o `carregando`, que é precisamente o momento em que a pessoa
          precisa saber que há um segundo botão para apertar. Esconder a dica
          nesse estado (era o que a primeira versão fazia) deixava a tela
          travada num "Conectando ao Google…" sem explicação. */}
      {botaoGoogleVisivel ? (
        <p className="text-center text-xs text-[var(--cor-texto-suave)]">
          Agora clique no botão do Google para escolher a conta.
        </p>
      ) : null}

      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={aceite}
          onChange={(evento) => setAceite(evento.target.checked)}
          className="h-4 w-4 rounded border-[var(--cor-borda)]"
        />
        Aceito os{" "}
        <Link href="/termos" className="text-[var(--cor-primaria)] underline">
          termos de uso
        </Link>{" "}
        e a{" "}
        <Link href="/privacidade" className="text-[var(--cor-primaria)] underline">
          política de privacidade
        </Link>
      </label>

      {erro ? (
        <p
          role="alert"
          data-erro-google={erro.codigo}
          className="rounded-md border border-[var(--cor-erro)] bg-[var(--cor-erro-suave)] px-3 py-2 text-sm text-[var(--cor-erro)]"
        >
          {erro.mensagem}
        </p>
      ) : null}
    </div>
  );
}
