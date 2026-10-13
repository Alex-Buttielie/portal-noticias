"use client";
import { memo, useEffect, useState } from "react";
import Link from "next/link";
import { Bookmark, BookmarkCheck, MapPin, Plus, Check } from "lucide-react";
import { useAuth } from "@/lib/auth-context";
import { segueFonte, alternarFonte } from "@/lib/minhas-fontes";
import { Badge } from "@/components/ui/badge";
import { ImagemNoticia } from "@/components/ImagemNoticia";
import { cn } from "@/lib/utils";
import type { FeedEntrada } from "@/lib/api";
import {
  derivarSelo,
  formatarCredito,
  formatarLocalidade,
  timeAgo,
  type SeloEditorial,
} from "@/lib/editorial";
import { formatarDataHora } from "@/lib/datas";
import { truncarPreservandoPalavra } from "@/lib/texto";

const SELO_ESTILO: Record<SeloEditorial, string> = {
  Urgente: "bg-[var(--cor-sinal)] text-[var(--cor-texto-invertido)]",
  Exclusivo: "bg-[var(--cor-premium)] text-[var(--cor-texto-invertido)]",
  Especial: "bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]",
  Análise: "bg-[var(--cor-fundo-elevado)] text-[var(--cor-primaria)] border border-[var(--cor-primaria)]",
  Opinião: "bg-[var(--cor-fundo-elevado)] text-[var(--cor-texto)] border border-[var(--cor-borda)]",
  Entrevista: "bg-[var(--cor-fundo-elevado)] text-[var(--cor-primaria)] border border-dashed border-[var(--cor-primaria)]",
};

/** Etiqueta editorial (classificação), não um chip de filtro — por isso
 * é um "flag" de canto reto (raio-sm) e não um pill (rounded-full). */
export function SeloBadge({ selo }: { selo: SeloEditorial }) {
  return (
    <span
      className={cn(
        "kicker inline-flex shrink-0 items-center rounded-[var(--raio-sm)] px-1.5 py-0.5 leading-4",
        SELO_ESTILO[selo]
      )}
    >
      {selo}
    </span>
  );
}

/** "Seguir fonte" — inspirado no Google Notícias. Local (localStorage) +
 * sincronizado com a conta quando logado (ver lib/minhas-fontes.ts). Só
 * aparece quando há um crédito real (autor/fonte, nunca a categoria). */
function BotaoSeguirFonte({ nomeFonte }: { nomeFonte: string }) {
  const { token } = useAuth();
  const [segue, setSegue] = useState(false);
  const [hidratado, setHidratado] = useState(false);

  useEffect(() => {
    setSegue(segueFonte(nomeFonte));
    setHidratado(true);
  }, [nomeFonte]);

  if (!hidratado) return null;

  return (
    <button
      type="button"
      onClick={(e) => {
        e.stopPropagation();
        e.preventDefault();
        alternarFonte(nomeFonte, token);
        setSegue((v) => !v);
      }}
      aria-pressed={segue}
      className="inline-flex shrink-0 items-center gap-0.5 rounded-full border border-[var(--cor-borda)] px-1.5 py-0.5 text-[10px] font-medium text-[var(--cor-texto-suave)] hover:border-[var(--cor-primaria)] hover:text-[var(--cor-primaria)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]"
    >
      {segue ? <Check className="h-2.5 w-2.5" aria-hidden /> : <Plus className="h-2.5 w-2.5" aria-hidden />}
      {segue ? "Seguindo" : "Seguir"}
    </button>
  );
}

export function LocalidadeTag({ entrada, className }: { entrada: FeedEntrada; className?: string }) {
  const local = formatarLocalidade(entrada);
  if (!local) return null;
  return (
    <span className={cn("inline-flex min-w-0 items-center gap-1 text-xs text-[var(--cor-texto-suave)]", className)}>
      <MapPin className="h-3 w-3 shrink-0" aria-hidden />
      <span className="truncate">{local}</span>
    </span>
  );
}

export function MetaLinha({ entrada, mostrarFontes = true }: { entrada: FeedEntrada; mostrarFontes?: boolean }) {
  const credito = formatarCredito(entrada);
  return (
    <p className="flex min-w-0 flex-wrap items-center gap-x-1.5 gap-y-0.5 text-xs text-[var(--cor-texto-suave)]">
      <Link
        href={`/categoria/${encodeURIComponent(entrada.categoria)}`}
        onClick={(e) => e.stopPropagation()}
        className="font-semibold capitalize text-[var(--cor-primaria)] hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] rounded-sm"
      >
        {entrada.categoria || "geral"}
      </Link>
      <LocalidadeTag entrada={entrada} />
      <time
        dateTime={entrada.timestamp}
        title={formatarDataHora(entrada.timestamp)}
        suppressHydrationWarning
      >
        {formatarDataHora(entrada.timestamp)} ({timeAgo(entrada.timestamp)})
      </time>
      {mostrarFontes && <span aria-label={`${entrada.numero_fontes} fontes`}>• {entrada.numero_fontes} {entrada.numero_fontes === 1 ? "fonte" : "fontes"}</span>}
      {credito && <span className="truncate">• {credito}</span>}
    </p>
  );
}

interface NewsCardProps {
  entrada: FeedEntrada;
  /** H-03: "grade" é a variante compacta usada no grid de 2 colunas mobile
   * de "Por editoria" (imagem menor no topo + título mais curto). */
  variante?: "destaque" | "secundaria" | "lista" | "grade";
  salvo?: boolean;
  onToggleSalvar?: (entrada: FeedEntrada) => void;
  eager?: boolean;
}

/**
 * Card clicável por inteiro (link estendido) — sem botões grandes.
 * O "Salvar" é um ícone discreto que não quebra o clique no card.
 */
export const NewsCard = memo(function NewsCard({ entrada, variante = "secundaria", salvo, onToggleSalvar, eager }: NewsCardProps) {
  const selo = derivarSelo(entrada);
  const href = `/noticia/${entrada.id}`;
  // H-02: truncamento por CARACTERES puro (`.slice`) cortava o resumo no
  // meio de uma palavra, sem nenhum indicador — `truncarPreservandoPalavra`
  // para no último espaço e acrescenta "…" (ver lib/texto.ts).
  const resumoCurto = truncarPreservandoPalavra(entrada.resumo || "", variante === "destaque" ? 220 : 140);

  const salvarBotao = onToggleSalvar && (
    <button
      type="button"
      onClick={(e) => {
        e.stopPropagation();
        onToggleSalvar(entrada);
      }}
      aria-pressed={!!salvo}
      aria-label={salvo ? "Remover dos salvos" : "Salvar para ler depois"}
      title={salvo ? "Remover dos salvos" : "Salvar para ler depois"}
      className="ml-auto inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-[var(--cor-texto-suave)] hover:bg-[var(--cor-fundo-elevado)] hover:text-[var(--cor-texto)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]"
    >
      {salvo ? <BookmarkCheck className="h-3.5 w-3.5" /> : <Bookmark className="h-3.5 w-3.5" />}
    </button>
  );

  // Linha "fonte": no Google Notícias cada story abre com a fonte + tempo,
  // antes do título. Aqui lidera o crédito real (autor/fonte, quando o
  // pipeline tiver) — nunca inventado — com a categoria como identificador
  // de fallback, já que o portal funde várias fontes por manchete em vez
  // de atribuir a uma só editora.
  const credito = formatarCredito(entrada);
  const nomeParaSeguir = (entrada.autor || entrada.nome_fonte || "").trim();
  // H-02/H-06: `flex-wrap` + `gap-x`/`gap-y` (em vez de só `gap`) — em cards
  // estreitos (grid 2 colunas, sidebar) esta linha tinha vários filhos
  // `shrink-0` numa única linha sem quebra, o que forçava overflow
  // horizontal em vez de quebrar para a linha seguinte.
  const linhaFonte = (
    <p className="flex min-w-0 flex-wrap items-center gap-x-1.5 gap-y-0.5 text-xs text-[var(--cor-texto-suave)]">
      {credito ? (
        <>
          <span className="min-w-0 truncate font-semibold text-[var(--cor-texto)]">{credito}</span>
          {nomeParaSeguir && <BotaoSeguirFonte nomeFonte={nomeParaSeguir} />}
        </>
      ) : (
        <Link
          href={`/categoria/${encodeURIComponent(entrada.categoria)}`}
          onClick={(e) => e.stopPropagation()}
          className="min-w-0 truncate font-semibold capitalize text-[var(--cor-texto)] hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] rounded-sm"
        >
          {entrada.categoria || "geral"}
        </Link>
      )}
      <span aria-hidden>·</span>
      {credito && (
        <>
          <Link
            href={`/categoria/${encodeURIComponent(entrada.categoria)}`}
            onClick={(e) => e.stopPropagation()}
            className="shrink-0 truncate capitalize hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] rounded-sm"
          >
            {entrada.categoria || "geral"}
          </Link>
          <span aria-hidden>·</span>
        </>
      )}
      <time dateTime={entrada.timestamp} title={formatarDataHora(entrada.timestamp)} suppressHydrationWarning className="shrink-0">
        {timeAgo(entrada.timestamp)}
      </time>
      {entrada.urgente && (
        <span className="ml-1 h-1.5 w-1.5 shrink-0 rounded-full bg-[var(--cor-sinal)] motion-safe:animate-pulse" aria-label="Urgente" />
      )}
    </p>
  );

  if (variante === "grade") {
    // H-03: variante compacta para o grid de 2 colunas mobile de "Por
    // editoria" — imagem proporcional pequena no topo (em vez do
    // thumbnail fixo 112px da lista densa, que não cabe em meia-tela) e
    // título mais curto (line-clamp-2 em vez de 3).
    return (
      <article className="group relative flex min-w-0 flex-col overflow-hidden rounded-[var(--raio-md)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] motion-safe:transition-colors hover:border-[var(--cor-primaria)]">
        <Link
          href={href}
          aria-label={entrada.titulo}
          className="block overflow-hidden bg-[var(--cor-fundo-elevado)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[var(--cor-foco)]"
        >
          <ImagemNoticia
            src={entrada.imagem_url}
            seed={`${entrada.categoria || "geral"}-${entrada.id}`}
            alt=""
            eager={eager}
            sizes="50vw"
            className="aspect-[4/3] w-full object-cover motion-safe:transition motion-safe:duration-300 group-hover:motion-safe:scale-[1.02]"
          />
        </Link>
        <div className="flex min-w-0 flex-1 flex-col gap-1 p-2.5">
          <div className="flex min-w-0 flex-wrap items-center gap-1">
            <span className="min-w-0 truncate text-[11px] font-semibold capitalize text-[var(--cor-texto-suave)]">
              {entrada.categoria || "geral"}
            </span>
            {selo && <SeloBadge selo={selo} />}
          </div>
          <Link
            href={href}
            className="block break-words text-balance text-[13px] font-bold leading-snug text-[var(--cor-texto)] after:absolute after:inset-0 after:content-[''] hover:text-[var(--cor-primaria)] focus-visible:outline-none motion-safe:transition-colors line-clamp-2"
          >
            {entrada.titulo}
          </Link>
          <div className="relative z-10 mt-auto flex min-w-0 items-center justify-between gap-1.5 text-[10px] text-[var(--cor-texto-suave)]">
            <time dateTime={entrada.timestamp} title={formatarDataHora(entrada.timestamp)} suppressHydrationWarning className="truncate">
              {timeAgo(entrada.timestamp)}
            </time>
            {salvarBotao}
          </div>
        </div>
      </article>
    );
  }

  if (variante !== "destaque") {
    // Linha densa, texto-primeiro (miniatura pequena, sem imagem
    // dominante) — padrão de lista do Google Notícias, em vez do cartão
    // com imagem no topo.
    return (
      <article className="group relative flex min-w-0 gap-3 border-b border-[var(--cor-borda)] py-3 first:pt-0 last:border-b-0 last:pb-0">
        <div className="min-w-0 flex-1">
          <div className="flex min-w-0 flex-wrap items-center gap-2">
            {linhaFonte}
            {selo && <SeloBadge selo={selo} />}
          </div>
          <Link
            href={href}
            className="mt-0.5 block break-words text-balance text-[15px] font-bold leading-snug text-[var(--cor-texto)] after:absolute after:inset-0 after:content-[''] hover:text-[var(--cor-primaria)] focus-visible:outline-none motion-safe:transition-colors line-clamp-3"
          >
            {entrada.titulo}
          </Link>
          {resumoCurto && (
            <p className="mt-0.5 line-clamp-1 text-xs leading-snug text-[var(--cor-texto-suave)]">{resumoCurto}</p>
          )}
          <div className="relative z-10 mt-1 flex items-center gap-3">
            <LocalidadeTag entrada={entrada} />
            {mostrarFontesBreve(entrada)}
            {salvarBotao}
          </div>
        </div>
        <ImagemNoticia
          src={entrada.imagem_url}
          seed={`${entrada.categoria || "geral"}-${entrada.id}`}
          alt=""
          eager={eager}
          sizes="112px"
          className="h-20 w-28 shrink-0 rounded-[var(--raio-md)] object-cover"
        />
      </article>
    );
  }

  return (
    <article
      className={cn(
        "group relative flex overflow-hidden rounded-[var(--raio-lg)] border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] motion-safe:transition-colors hover:border-[var(--cor-primaria)]",
        "flex-col md:grid md:grid-cols-[1.5fr_1fr]"
      )}
    >
      <Link
        href={href}
        aria-label={entrada.titulo}
        className="block overflow-hidden bg-[var(--cor-fundo-elevado)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[var(--cor-foco)]"
      >
        <ImagemNoticia
          src={entrada.imagem_url}
          seed={`${entrada.categoria || "geral"}-${entrada.id}`}
          alt={entrada.titulo}
          eager={eager}
          sizes="(max-width: 768px) 100vw, 60vw"
          className="aspect-[16/9] w-full object-cover motion-safe:transition motion-safe:duration-300 group-hover:motion-safe:scale-[1.02] md:h-full md:min-h-[320px]"
        />
      </Link>
      <div className="flex w-full min-w-0 flex-1 flex-col gap-2 p-5 md:p-6">
        <div className="flex flex-wrap items-center gap-2">
          {linhaFonte}
          {selo && <SeloBadge selo={selo} />}
          {salvarBotao}
        </div>
        <Link
          href={href}
          className="break-words text-balance text-2xl font-bold leading-tight tracking-tight text-[var(--cor-texto)] hover:text-[var(--cor-primaria)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] motion-safe:transition-colors sm:text-3xl md:text-4xl line-clamp-3"
        >
          {entrada.titulo}
        </Link>
        {resumoCurto && (
          <Link
            href={href}
            className="break-words text-sm leading-snug text-[var(--cor-texto-suave)] hover:text-[var(--cor-texto)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] motion-safe:transition-colors line-clamp-3"
          >
            {resumoCurto}
          </Link>
        )}
        <div className="mt-auto pt-1">
          <MetaLinha entrada={entrada} mostrarFontes={false} />
        </div>
      </div>
      <Badge className="sr-only">Manchete principal</Badge>
    </article>
  );
});

function mostrarFontesBreve(entrada: FeedEntrada) {
  return (
    <span className="text-xs text-[var(--cor-texto-suave)]">
      {entrada.numero_fontes} {entrada.numero_fontes === 1 ? "fonte" : "fontes"}
    </span>
  );
}
