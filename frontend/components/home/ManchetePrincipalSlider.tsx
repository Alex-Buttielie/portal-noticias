"use client";
import { useCallback, useEffect, useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import type { FeedEntrada } from "@/lib/api";
import { proximoIndiceCircular } from "@/lib/slider";
import { cn } from "@/lib/utils";
import { NewsCard } from "./NewsCard";

const INTERVALO_AUTOPLAY_MS = 7000;

interface ManchetePrincipalSliderProps {
  /** Primeiras N manchetes (sugestão do contrato: 3-5) — a mais recente
   * (índice 0) é a exibida no primeiro paint (SSR-safe). */
  itens: FeedEntrada[];
  salvos: Set<string>;
  onToggleSalvar: (entrada: FeedEntrada) => void;
}

/** `true` quando o usuário pediu movimento reduzido no SO/navegador —
 * detectado só no cliente (SSR não tem `matchMedia`) e revisado se o
 * usuário mudar a preferência em runtime. */
function usePrefereMovimentoReduzido(): boolean {
  const [reduzido, setReduzido] = useState(false);
  useEffect(() => {
    if (typeof window === "undefined" || !window.matchMedia) return;
    const consulta = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReduzido(consulta.matches);
    const ouvir = (evento: MediaQueryListEvent) => setReduzido(evento.matches);
    consulta.addEventListener("change", ouvir);
    return () => consulta.removeEventListener("change", ouvir);
  }, []);
  return reduzido;
}

/**
 * H-01 — Slider automático da manchete principal da Home.
 *
 * Gira entre as primeiras N manchetes recebidas (troca automática a cada
 * `INTERVALO_AUTOPLAY_MS`), pausando em hover/foco/interação do teclado e
 * desativando o autoplay quando `prefers-reduced-motion: reduce` está
 * ativo. Navegação manual (setas + indicadores) sempre disponível,
 * independente de autoplay. Sem lib nova: CSS + `useEffect`/`setInterval`.
 */
export function ManchetePrincipalSlider({ itens, salvos, onToggleSalvar }: ManchetePrincipalSliderProps) {
  const total = itens.length;
  const [indice, setIndice] = useState(0);
  const [pausado, setPausado] = useState(false);
  // Incrementado em toda navegação manual — reinicia o `setInterval` do
  // autoplay (reseta a contagem do intervalo), para o clique do usuário não
  // ser imediatamente "desfeito" por uma troca automática na sequência.
  const [ciclo, setCiclo] = useState(0);
  const reduzido = usePrefereMovimentoReduzido();

  const irPara = useCallback(
    (novoIndice: number) => {
      setIndice(proximoIndiceCircular(novoIndice, total, 0));
      setCiclo((c) => c + 1);
    },
    [total]
  );

  useEffect(() => {
    if (total <= 1 || pausado || reduzido) return;
    const id = setInterval(() => {
      setIndice((i) => proximoIndiceCircular(i, total, 1));
    }, INTERVALO_AUTOPLAY_MS);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- `ciclo` só serve para reiniciar o timer
  }, [total, pausado, reduzido, ciclo]);

  if (total === 0) return null;

  const indiceSeguro = indice % total;
  const atual = itens[indiceSeguro];

  return (
    <div
      role="region"
      aria-roledescription="carrossel"
      aria-label="Manchete principal"
      className="flex flex-col gap-2"
      onMouseEnter={() => setPausado(true)}
      onMouseLeave={() => setPausado(false)}
      onFocus={() => setPausado(true)}
      onBlur={(evento) => {
        if (!evento.currentTarget.contains(evento.relatedTarget as Node)) setPausado(false);
      }}
    >
      {/* Anúncio da troca para leitor de tela — texto, não o card inteiro,
          para não re-anunciar botões/imagem a cada ciclo. */}
      <p aria-live="polite" className="sr-only">
        Manchete {indiceSeguro + 1} de {total}: {atual.titulo}
      </p>
      <NewsCard
        key={`${atual.tipo}-${atual.id}`}
        entrada={atual}
        variante="destaque"
        eager={indiceSeguro === 0}
        salvo={salvos.has(`${atual.tipo}-${atual.id}`)}
        onToggleSalvar={onToggleSalvar}
      />
      {total > 1 && (
        <div className="flex items-center justify-between gap-2 rounded-[var(--raio-completo)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] px-2 py-1.5 shadow-[var(--sombra-1)]">
          <button
            type="button"
            onClick={() => irPara(indiceSeguro - 1)}
            aria-label="Manchete anterior"
            className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-[var(--cor-texto-suave)] hover:bg-[var(--cor-fundo-elevado)] hover:text-[var(--cor-texto)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]"
          >
            <ChevronLeft className="h-4 w-4" aria-hidden />
          </button>
          <div className="flex items-center gap-1.5" aria-hidden={false}>
            {itens.map((item, i) => (
              <button
                key={`${item.tipo}-${item.id}`}
                type="button"
                onClick={() => irPara(i)}
                aria-label={`Ir para manchete ${i + 1} de ${total}`}
                aria-current={i === indiceSeguro}
                className={cn(
                  "h-1.5 rounded-full motion-safe:transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]",
                  i === indiceSeguro
                    ? "w-5 bg-[var(--cor-primaria)]"
                    : "w-1.5 bg-[var(--cor-borda)] hover:bg-[var(--cor-texto-suave)]"
                )}
              />
            ))}
          </div>
          <button
            type="button"
            onClick={() => irPara(indiceSeguro + 1)}
            aria-label="Próxima manchete"
            className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-[var(--cor-texto-suave)] hover:bg-[var(--cor-fundo-elevado)] hover:text-[var(--cor-texto)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]"
          >
            <ChevronRight className="h-4 w-4" aria-hidden />
          </button>
        </div>
      )}
    </div>
  );
}
