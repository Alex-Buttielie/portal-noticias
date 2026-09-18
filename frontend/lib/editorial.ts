import { useEffect, useState } from "react";
import type { FeedEntrada } from "./api";
import { obterTodasLeituras } from "./intent";

// ---------------------------------------------------------------------------
// Central editorial da Home (FRENTE 1) — utilidades puras + configuração.
// Sem adivinhação: selo e localidade derivam SÓ do dado existente.
// ---------------------------------------------------------------------------

export type SeloEditorial = "Exclusivo" | "Urgente" | "Análise" | "Opinião" | "Especial" | "Entrevista";

const CATEGORIAS_OPINIAO = new Set(["opinião", "opiniao", "coluna", "colunistas"]);
const CATEGORIAS_ANALISE = new Set(["análise", "analise"]);
export const CATEGORIAS_BOMBANDO = [
  "cultura",
  "entretenimento",
  "celebridades",
  "famosos",
  "música",
  "musica",
  "cinema",
  "séries",
  "series",
  "tv",
  "esportes",
];

/** Quantidades da Home — configuráveis sem código via localStorage (chave abaixo). */
export interface HomeConfig {
  manchetesSecundarias: number;
  ultimasLimite: number;
  ultimasPasso: number;
  emAltaLimite: number;
  bombandoLimite: number;
  portfolioCategorias: number;
  portfolioPorCategoria: number;
  portfolioPasso: number;
  refreshUltimasSegundos: number;
}

export const HOME_CONFIG_PADRAO: HomeConfig = {
  manchetesSecundarias: 8,
  ultimasLimite: 12,
  ultimasPasso: 6,
  emAltaLimite: 10,
  bombandoLimite: 8,
  portfolioCategorias: 6,
  portfolioPorCategoria: 6,
  portfolioPasso: 4,
  refreshUltimasSegundos: 90,
};

const CHAVE_CONFIG = "brd_home_config";

export function obterHomeConfig(): HomeConfig {
  if (typeof window === "undefined") return HOME_CONFIG_PADRAO;
  try {
    const bruto = window.localStorage.getItem(CHAVE_CONFIG);
    if (!bruto) return HOME_CONFIG_PADRAO;
    const dados = JSON.parse(bruto) as Partial<HomeConfig>;
    const num = (v: unknown, fallback: number) =>
      typeof v === "number" && Number.isFinite(v) && v > 0 ? Math.min(Math.floor(v), 60) : fallback;
    return {
      manchetesSecundarias: num(dados.manchetesSecundarias, HOME_CONFIG_PADRAO.manchetesSecundarias),
      ultimasLimite: num(dados.ultimasLimite, HOME_CONFIG_PADRAO.ultimasLimite),
      ultimasPasso: num(dados.ultimasPasso, HOME_CONFIG_PADRAO.ultimasPasso),
      emAltaLimite: num(dados.emAltaLimite, HOME_CONFIG_PADRAO.emAltaLimite),
      bombandoLimite: num(dados.bombandoLimite, HOME_CONFIG_PADRAO.bombandoLimite),
      portfolioCategorias: num(dados.portfolioCategorias, HOME_CONFIG_PADRAO.portfolioCategorias),
      portfolioPorCategoria: num(dados.portfolioPorCategoria, HOME_CONFIG_PADRAO.portfolioPorCategoria),
      portfolioPasso: num(dados.portfolioPasso, HOME_CONFIG_PADRAO.portfolioPasso),
      refreshUltimasSegundos: num(dados.refreshUltimasSegundos, HOME_CONFIG_PADRAO.refreshUltimasSegundos),
    };
  } catch {
    return HOME_CONFIG_PADRAO;
  }
}

// --- Selo editorial (PT-BR; nunca "exclusive") ------------------------------

const norm = (v: string | undefined | null) =>
  (v || "").trim().toLowerCase();

/**
 * Deriva o selo editorial SOMENTE do dado existente:
 * - "Urgente": entrada marcada urgente no backend;
 * - "Exclusivo": cobertura ampla (4+ fontes distintas);
 * - "Especial": cluster com 3+ fontes (cobertura especial multiview);
 * - "Opinião"/"Análise": categoria editorial correspondente.
 * - "Entrevista": só via `seloPublicacao` (lib/colunistas) quando as tags
 *   da publicação contêm "entrevista" — nunca inferido para manchete de feed.
 * Retorna null quando nada se aplica (a maioria das manchetes não tem selo).
 */
export function derivarSelo(entrada: FeedEntrada): SeloEditorial | null {
  const categoria = norm(entrada.categoria);
  if (entrada.urgente) return "Urgente";
  if (CATEGORIAS_OPINIAO.has(categoria)) return "Opinião";
  if (CATEGORIAS_ANALISE.has(categoria)) return "Análise";
  if (entrada.numero_fontes >= 4) return "Exclusivo";
  if (entrada.tipo === "cluster" && entrada.numero_fontes >= 3) return "Especial";
  return null;
}

// --- Localização discreta (só quando existir no dado, nunca inventar) -------

/**
 * Formata "cidade/UF, estado, país" usando SÓ os campos do backend.
 * Ex.: cidade=Goiânia + estado=GO → "Goiânia/GO"; só estado=GO → "GO";
 * só país=Brasil → "Brasil". Retorna null quando não há nenhum dado.
 */
export function formatarLocalidade(entrada: Pick<FeedEntrada, "cidade" | "estado" | "pais">): string | null {
  const cidade = (entrada.cidade || "").trim();
  const estado = (entrada.estado || "").trim();
  const pais = (entrada.pais || "").trim();
  if (cidade && estado) return `${cidade}/${estado}`;
  if (cidade) return cidade;
  if (estado) return estado;
  if (pais) return pais;
  return null;
}

/** Linha de autoria sem inventar pessoa: "Fonte: X" quando houver fonte. */
export function formatarAutoria(entrada: Pick<FeedEntrada, "nome_fonte">): string | null {
  const fonte = (entrada.nome_fonte || "").trim();
  return fonte ? fonte : null;
}

/**
 * Crédito editorial sem inventar pessoa: prefere o autor/colunista real
 * (FRENTE 3, campo `autor` do RSS) — "Por Nome"; senão a fonte — "Fonte: X";
 * null quando não há nenhum dos dois (a linha é omitida).
 */
export function formatarCredito(entrada: Pick<FeedEntrada, "autor" | "nome_fonte">): string | null {
  const autor = (entrada.autor || "").trim();
  if (autor) return `Por ${autor}`;
  const fonte = (entrada.nome_fonte || "").trim();
  if (fonte) return `Fonte: ${fonte}`;
  return null;
}

// --- Data/hora ---------------------------------------------------------------

export function formatarDataHora(iso: string): string {
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return "";
    const data = d.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" });
    const hora = d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
    return `${data} • ${hora}`;
  } catch {
    return "";
  }
}

export function formatarHora(iso: string): string {
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return "";
    return d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
  } catch {
    return "";
  }
}

export function ehNova(iso: string, minutos = 60): boolean {
  try {
    const ms = Date.now() - new Date(iso).getTime();
    return ms >= 0 && ms < minutos * 60_000;
  } catch {
    return false;
  }
}

export function timeAgo(iso: string): string {
  try {
    const d = Math.max(0, Date.now() - new Date(iso).getTime());
    const min = Math.floor(d / 60000);
    if (min < 1) return "agora";
    if (min < 60) return `${min}min`;
    const h = Math.floor(min / 60);
    if (h < 24) return `${h}h`;
    return `${Math.floor(h / 24)}d`;
  } catch {
    return "";
  }
}

// --- Em Alta: score composto (não só views absolutas) ------------------------
// O backend não expõe views/cliques por item (ver "o que falta" no resumo).
// O score combina sinais disponíveis: cobertura (nº fontes, proxy de
// repercussão), recência (decaimento por horas), urgência, formato cluster e
// engajamento local (leituras/salvos por categoria). Determinístico e
// explicável — cada item expõe os componentes via `explicarScoreEmAlta`.

export interface SinaisEngajamento {
  leiturasPorCategoria: Record<string, number>;
  salvosPorCategoria: Record<string, number>;
  categoriaBuscada?: string | null;
}

/** Sinais neutros (vazios): primeira render idêntica ao SSR; ver `useHidratado`. */
export function sinaisNeutros(categoriaBuscada?: string | null): SinaisEngajamento {
  return { leiturasPorCategoria: {}, salvosPorCategoria: {}, categoriaBuscada: categoriaBuscada || null };
}

export function lerSinaisLocais(categoriaBuscada?: string | null): SinaisEngajamento {
  let leiturasPorCategoria: Record<string, number> = {};
  try {
    leiturasPorCategoria = obterTodasLeituras();
  } catch {
    leiturasPorCategoria = {};
  }
  let salvosPorCategoria: Record<string, number> = {};
  try {
    if (typeof window !== "undefined") {
      const bruto = window.localStorage.getItem("portal_noticias_salvos");
      const itens = bruto ? (JSON.parse(bruto) as FeedEntrada[]) : [];
      if (Array.isArray(itens)) {
        for (const it of itens) {
          const cat = norm(it.categoria);
          if (cat) salvosPorCategoria[cat] = (salvosPorCategoria[cat] || 0) + 1;
        }
      }
    }
  } catch {
    salvosPorCategoria = {};
  }
  return { leiturasPorCategoria, salvosPorCategoria, categoriaBuscada: categoriaBuscada || null };
}

export function scoreEmAlta(entrada: FeedEntrada, sinais: SinaisEngajamento): number {
  const horas = Math.max(0, (Date.now() - new Date(entrada.timestamp).getTime()) / 3600000);
  const recencia = 24 / (24 + horas); // 1.0 agora → ~0.5 em 24h → decai
  const cobertura = Math.min(entrada.numero_fontes || 1, 8) / 8; // 0.125–1
  const cat = norm(entrada.categoria);
  const leituras = Math.min(sinais.leiturasPorCategoria[entrada.categoria] ?? sinais.leiturasPorCategoria[cat] ?? 0, 8) / 8;
  const salvos = Math.min(sinais.salvosPorCategoria[cat] ?? 0, 8) / 8;
  const busca = sinais.categoriaBuscada && cat === norm(sinais.categoriaBuscada) ? 0.15 : 0;
  let score =
    cobertura * 0.35 +
    recencia * 0.3 +
    (entrada.urgente ? 0.15 : 0) +
    (entrada.tipo === "cluster" ? 0.05 : 0) +
    leituras * 0.08 +
    salvos * 0.07 +
    busca;
  return Math.round(score * 1000) / 1000;
}

export function explicarScoreEmAlta(entrada: FeedEntrada, sinais: SinaisEngajamento): string {
  const partes: string[] = [];
  partes.push(`${entrada.numero_fontes} ${entrada.numero_fontes === 1 ? "fonte" : "fontes"}`);
  partes.push(timeAgo(entrada.timestamp));
  if (entrada.urgente) partes.push("urgente");
  if (entrada.tipo === "cluster") partes.push("multiview");
  const cat = norm(entrada.categoria);
  const eng = (sinais.leiturasPorCategoria[entrada.categoria] ?? sinais.leiturasPorCategoria[cat] ?? 0) as number;
  if (eng >= 2) partes.push("lida por você");
  return partes.join(" • ");
}

export function ordenarEmAlta(feed: FeedEntrada[], sinais: SinaisEngajamento): { entrada: FeedEntrada; score: number }[] {
  return feed
    .map((entrada) => ({ entrada, score: scoreEmAlta(entrada, sinais) }))
    .sort((a, b) => b.score - a.score || new Date(b.entrada.timestamp).getTime() - new Date(a.entrada.timestamp).getTime());
}

// --- Portfólio dinâmico de categorias ----------------------------------------

export interface BlocoPortfolio {
  categoria: string;
  itens: FeedEntrada[];
  total: number;
  motivo: string;
}

/**
 * Seleção dinâmica de categorias por 4 sinais (sem restrição fixa de N):
 * pesquisas (categoria buscada/filtro ativo), acessos (volume no feed),
 * crescimento (itens das últimas 24h) e engajamento (leituras+salvos locais).
 */
export function selecionarPortfolio(
  feed: FeedEntrada[],
  sinais: SinaisEngajamento,
  maxCategorias: number
): BlocoPortfolio[] {
  const porCategoria = new Map<string, FeedEntrada[]>();
  const rotulo = new Map<string, string>();
  for (const entrada of feed) {
    const chave = norm(entrada.categoria);
    if (!chave) continue;
    if (!porCategoria.has(chave)) {
      porCategoria.set(chave, []);
      rotulo.set(chave, (entrada.categoria || "").trim() || chave);
    }
    porCategoria.get(chave)!.push(entrada);
  }
  const agora = Date.now();
  const blocos: (BlocoPortfolio & { pontos: number })[] = [];
  for (const [chave, itens] of porCategoria) {
    const recentes24h = itens.filter((i) => agora - new Date(i.timestamp).getTime() < 24 * 3600000).length;
    const crescimento = itens.length ? recentes24h / itens.length : 0;
    const leituras = sinais.leiturasPorCategoria[rotulo.get(chave) || ""] ?? sinais.leiturasPorCategoria[chave] ?? 0;
    const salvos = sinais.salvosPorCategoria[chave] ?? 0;
    const pesquisa = sinais.categoriaBuscada && chave === norm(sinais.categoriaBuscada) ? 3 : 0;
    const pontos = Math.min(itens.length, 12) * 0.5 + crescimento * 4 + Math.min(leituras, 6) * 0.6 + Math.min(salvos, 6) * 0.5 + pesquisa;
    const motivos: string[] = [];
    if (pesquisa) motivos.push("sua pesquisa");
    if (crescimento >= 0.5 && recentes24h >= 2) motivos.push(`${recentes24h} novas em 24h`);
    else if (itens.length >= 4) motivos.push(`${itens.length} matérias`);
    if (leituras >= 2) motivos.push("você acompanha");
    blocos.push({
      categoria: rotulo.get(chave) || chave,
      itens: [...itens].sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()),
      total: itens.length,
      motivo: motivos.slice(0, 2).join(" • ") || "cobertura do dia",
      pontos: Math.round(pontos * 100) / 100,
    });
  }
  return blocos
    .sort((a, b) => b.pontos - a.pontos)
    .slice(0, Math.max(1, maxCategorias))
    .map(({ pontos: _p, ...rest }) => rest);
}

/** Agrupa estados com contagem (para "Mais de GO" contextual). */
export function agruparPorEstado(feed: FeedEntrada[]): { estado: string; total: number }[] {
  const mapa = new Map<string, number>();
  for (const entrada of feed) {
    const estado = (entrada.estado || "").trim();
    if (estado) mapa.set(estado, (mapa.get(estado) || 0) + 1);
  }
  return [...mapa.entries()]
    .map(([estado, total]) => ({ estado, total }))
    .sort((a, b) => b.total - a.total)
    .slice(0, 6);
}

// --- debounce ----------------------------------------------------------------

export function useDebouncedValue<T>(valor: T, atrasoMs = 300): T {
  const [atual, setAtual] = useState(valor);
  useEffect(() => {
    const id = setTimeout(() => setAtual(valor), atrasoMs);
    return () => clearTimeout(id);
  }, [valor, atrasoMs]);
  return atual;
}
