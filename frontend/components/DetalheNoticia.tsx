"use client";

import { useEffect, useState } from "react";
import * as api from "@/lib/api";
import * as intencao from "@/lib/intent";
import { obterVisualCategoria } from "@/lib/categoryVisuals";
import CartaoEsqueleto from "@/components/CartaoEsqueleto";
import Badge from "@/components/Badge";
import { useToast } from "@/components/ToastProvider";

function formatarData(timestamp: string): string {
  try {
    return new Date(timestamp).toLocaleString("pt-BR", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return timestamp;
  }
}

const PALAVRAS_POR_MINUTO = 200;

function estimarTempoLeitura(detalhe: api.FeedDetalhe): number {
  const palavras = detalhe.fontes.reduce(
    (total, fonte) => total + fonte.resumo.split(/\s+/).filter(Boolean).length,
    detalhe.titulo.split(/\s+/).filter(Boolean).length
  );
  return Math.max(1, Math.round(palavras / PALAVRAS_POR_MINUTO));
}

/** Barra fina no topo mostrando o quanto já foi rolado do artigo. */
function useProgressoLeitura(): number {
  const [progresso, setProgresso] = useState(0);

  useEffect(() => {
    function aoRolar() {
      const alturaTotal = document.documentElement.scrollHeight - window.innerHeight;
      const percentual = alturaTotal > 0 ? (window.scrollY / alturaTotal) * 100 : 0;
      setProgresso(Math.min(100, Math.max(0, percentual)));
    }
    aoRolar();
    window.addEventListener("scroll", aoRolar, { passive: true });
    window.addEventListener("resize", aoRolar);
    return () => {
      window.removeEventListener("scroll", aoRolar);
      window.removeEventListener("resize", aoRolar);
    };
  }, []);

  return progresso;
}

export default function DetalheNoticia({
  tipo,
  id,
}: {
  tipo: "cluster" | "item";
  id: string;
}) {
  const { notificar } = useToast();
  const [detalhe, setDetalhe] = useState<api.FeedDetalhe | null>(null);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState<string | null>(null);
  const [naoEncontrada, setNaoEncontrada] = useState(false);
  const progresso = useProgressoLeitura();

  useEffect(() => {
    let cancelado = false;
    setCarregando(true);
    setErro(null);
    setNaoEncontrada(false);

    const buscar = tipo === "cluster" ? api.obterDetalheCluster : api.obterDetalheItem;

    buscar(id)
      .then((resposta) => {
        if (!cancelado) {
          setDetalhe(resposta);
          intencao.registrarLeitura(resposta.categoria);
        }
      })
      .catch((e: unknown) => {
        if (cancelado) return;
        if (e instanceof api.ApiError && e.status === 404) {
          setNaoEncontrada(true);
        } else {
          setErro(
            e instanceof api.ApiError ? e.message : "Não foi possível carregar esta notícia."
          );
        }
      })
      .finally(() => {
        if (!cancelado) setCarregando(false);
      });

    return () => {
      cancelado = true;
    };
  }, [tipo, id]);

  async function compartilhar() {
    try {
      await navigator.clipboard.writeText(window.location.href);
      notificar("Link copiado para a área de transferência.", "sucesso");
    } catch {
      notificar("Não foi possível copiar o link.", "erro");
    }
  }

  if (carregando) {
    return (
      <div aria-live="polite" aria-busy="true">
        <span className="sr-only">Carregando notícia…</span>
        <CartaoEsqueleto />
      </div>
    );
  }
  if (naoEncontrada) {
    return (
      <p className="mensagem-erro" role="alert">
        Esta notícia não foi encontrada ou não está disponível.
      </p>
    );
  }
  if (erro || !detalhe) {
    return (
      <p className="mensagem-erro" role="alert">
        {erro || "Não foi possível carregar esta notícia."}
      </p>
    );
  }

  const visual = obterVisualCategoria(detalhe.categoria);

  return (
    <>
      {/* Fora do <article> de propósito: o `transform` da animação de
          entrada abaixo cria um novo "containing block" para descendentes
          `position: fixed` (mesmo com translateY(0) no fim da animação),
          o que faria esta barra se posicionar relativa ao artigo em vez da
          viewport. */}
      <div
        className="barra-progresso-leitura"
        style={{ width: `${progresso}%` }}
        role="progressbar"
        aria-label="Progresso de leitura"
        aria-valuenow={Math.round(progresso)}
        aria-valuemin={0}
        aria-valuemax={100}
      />
      <article style={{ animation: "entrada-suave var(--duracao-lenta) var(--curva-padrao) both" }}>
      {detalhe.exibir_publicidade && (
        <div className="faixa-publicidade">
          Espaço publicitário — assine o Premium para navegar sem anúncios.
        </div>
      )}
      <div className="cartao-meta">
        {detalhe.urgente && <Badge variante="erro">Urgente</Badge>}
        {detalhe.categoria && (
          <Badge variante="neutro">
            <span className="cartao-emoji" aria-hidden="true">
              {visual.emoji}
            </span>
            {detalhe.categoria}
          </Badge>
        )}
        <span>{formatarData(detalhe.timestamp)}</span>
      </div>
      <h1>{detalhe.titulo}</h1>

      <div className="info-leitura">
        <span>{estimarTempoLeitura(detalhe)} min de leitura</span>
        <span aria-hidden="true">·</span>
        <button type="button" className="botao-compartilhar" onClick={compartilhar}>
          <span aria-hidden="true">🔗</span> Copiar link
        </button>
      </div>

      <h2 style={{ fontSize: "1rem", marginTop: "1.5rem" }}>
        Fontes ({detalhe.fontes.length})
      </h2>
      {detalhe.fontes.map((fonte, indice) => (
        <div className="cartao cartao-acento" style={{ ["--acento" as string]: visual.cor }} key={`${fonte.url_fonte_original}-${indice}`}>
          <div className="cartao-meta">
            <strong>{fonte.nome_fonte}</strong>
          </div>
          <p className="artigo-corpo" style={{ fontSize: "1rem" }}>
            {fonte.resumo}
          </p>
          <a href={fonte.url_fonte_original} target="_blank" rel="noopener noreferrer">
            Ler matéria original em {fonte.nome_fonte} →
          </a>
        </div>
      ))}
      </article>
    </>
  );
}
