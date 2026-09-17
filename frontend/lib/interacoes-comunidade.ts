/**
 * FRENTE 4 (Comunidade viva) — eventos de interação da comunidade.
 *
 * Integração com o ecossistema (não funcionalidade isolada): cada gesto de
 * participação (ver feed/publicação, comentar, responder, seguir, publicar,
 * denunciar, clicar em notícia relacionada, filtrar) é registrado aqui em
 * `localStorage` de forma fire-and-forget (nunca quebra a UI) e agregado
 * em `obterMetricasComunidade()` para os indicadores de interação do layout
 * (faixa de stats, "em discussão agora"). Os agregados de negócio
 * (publicações/comentários/seguidores) continuam vindo do backend via
 * `/api/metricas/painel/` — este módulo cobre o sinal comportamental local.
 */

export type EventoComunidadeTipo =
  | "ver_feed"
  | "ver_publicacao"
  | "comentar"
  | "responder"
  | "seguir_autor"
  | "deixar_seguir"
  | "publicar"
  | "denunciar"
  | "clicar_noticia_relacionada"
  | "filtrar";

export interface EventoComunidade {
  tipo: EventoComunidadeTipo;
  em: string;
  publicacaoId?: number;
  categoria?: string;
  destino?: string;
}

const CHAVE = "brd_comunidade_eventos";
const MAX_EVENTOS = 300;

function ler(): EventoComunidade[] {
  if (typeof window === "undefined") return [];
  try {
    const bruto = window.localStorage.getItem(CHAVE);
    if (!bruto) return [];
    const dados = JSON.parse(bruto) as unknown;
    return Array.isArray(dados) ? (dados as EventoComunidade[]) : [];
  } catch {
    return [];
  }
}

/** Registra um evento de interação — nunca lança. */
export function registrarEventoComunidade(
  tipo: EventoComunidadeTipo,
  dados: { publicacaoId?: number; categoria?: string; destino?: string } = {}
): void {
  if (typeof window === "undefined") return;
  try {
    const atual = ler();
    atual.push({ tipo, em: new Date().toISOString(), ...dados });
    window.localStorage.setItem(CHAVE, JSON.stringify(atual.slice(-MAX_EVENTOS)));
  } catch {
    // localStorage indisponível — evento descartado, UI segue normal.
  }
}

export interface MetricasComunidadeLocal {
  visualizacoes: number;
  comentarios: number;
  respostas: number;
  follows: number;
  publicacoes: number;
  cliquesNoticias: number;
}

/** Agregado local dos eventos (para indicadores de interação no layout). */
export function obterMetricasComunidade(): MetricasComunidadeLocal {
  const eventos = ler();
  let visualizacoes = 0;
  let comentarios = 0;
  let respostas = 0;
  let follows = 0;
  let publicacoes = 0;
  let cliquesNoticias = 0;
  for (const e of eventos) {
    switch (e.tipo) {
      case "ver_feed":
      case "ver_publicacao":
        visualizacoes += 1;
        break;
      case "comentar":
        comentarios += 1;
        break;
      case "responder":
        respostas += 1;
        break;
      case "seguir_autor":
        follows += 1;
        break;
      case "publicar":
        publicacoes += 1;
        break;
      case "clicar_noticia_relacionada":
        cliquesNoticias += 1;
        break;
      default:
        break;
    }
  }
  return { visualizacoes, comentarios, respostas, follows, publicacoes, cliquesNoticias };
}
