import { obterPerfilAutor, obterPublicacoes, type Publicacao } from "./api";
import type { SeloEditorial } from "./editorial";

// ---------------------------------------------------------------------------
// Colunistas (FRENTE 2) — derivados SÓ de dados reais do backend:
// autores de Publicacao (comunidade) + perfil público do autor.
// Sem mocks, sem foto inventada (iniciais quando não há foto).
// ---------------------------------------------------------------------------

export interface Colunista {
  id: number;
  nome: string;
  foto_url?: string | null;
  mini_bio?: string;
  credenciado: boolean;
  /** Assunto mais frequente do autor (categoria com mais textos). */
  especialidade: string;
  total_textos: number;
  numero_seguidores: number;
  recente: Publicacao;
  selo: SeloEditorial;
}

/**
 * Selo do conteúdo mais recente, derivado SÓ do dado da publicação:
 * tags explícitas ("entrevista"/"especial") > destaque ("Exclusivo") >
 * tipo ("Análise"/"Opinião"). Nunca inventado.
 */
export function seloPublicacao(pub: Pick<Publicacao, "tipo" | "tags" | "destaque">): SeloEditorial {
  const tags = (pub.tags || []).map((t) => (t || "").toLowerCase());
  if (tags.some((t) => t.includes("entrevista"))) return "Entrevista";
  if (tags.some((t) => t.includes("especial"))) return "Especial";
  if (pub.destaque) return "Exclusivo";
  return pub.tipo === "analise" ? "Análise" : "Opinião";
}

/** Iniciais para avatar quando o autor não tem foto (nunca imagem inventada). */
export function iniciais(nome: string): string {
  const partes = (nome || "").trim().split(/\s+/).filter(Boolean);
  if (!partes.length) return "?";
  if (partes.length === 1) return partes[0].slice(0, 2).toUpperCase();
  return (partes[0][0] + partes[partes.length - 1][0]).toUpperCase();
}

function especialidadeDe(pubs: Publicacao[]): string {
  const contagem = new Map<string, { rotulo: string; total: number }>();
  for (const p of pubs) {
    const chave = (p.categoria || "").trim().toLowerCase();
    if (!chave) continue;
    const atual = contagem.get(chave) || { rotulo: (p.categoria || "").trim(), total: 0 };
    atual.total += 1;
    contagem.set(chave, atual);
  }
  let melhor: { rotulo: string; total: number } | null = null;
  for (const v of contagem.values()) {
    if (!melhor || v.total > melhor.total) melhor = v;
  }
  return melhor ? melhor.rotulo : "Colunista";
}

function dataPub(p: Publicacao): number {
  const iso = p.publicado_em || p.criado_em;
  const t = new Date(iso).getTime();
  return Number.isFinite(t) ? t : 0;
}

/**
 * Carrega colunistas: publicações em destaque (fallback: recentes),
 * agrupadas por autor, com perfil público (foto/bio/seguidores) buscado
 * em paralelo e ignorado silenciosamente quando indisponível.
 * Retorna [] em falha — a seção se oculta, nunca exibe dado inventado.
 */
export async function carregarColunistas(limite = 4): Promise<Colunista[]> {
  let pubs: Publicacao[];
  try {
    const destaques = await obterPublicacoes({ destaque: true });
    pubs = destaques.length ? destaques : await obterPublicacoes({});
  } catch {
    return [];
  }
  if (!pubs.length) return [];

  const porAutor = new Map<number, Publicacao[]>();
  for (const p of pubs) {
    if (!porAutor.has(p.autor)) porAutor.set(p.autor, []);
    porAutor.get(p.autor)!.push(p);
  }

  const grupos = [...porAutor.entries()]
    .map(([autorId, lista]) => {
      const ordenada = [...lista].sort((a, b) => dataPub(b) - dataPub(a));
      return { autorId, lista: ordenada, recente: ordenada[0] };
    })
    .sort((a, b) => dataPub(b.recente) - dataPub(a.recente))
    .slice(0, Math.max(1, limite));

  const colunistas = await Promise.all(
    grupos.map(async ({ autorId, lista, recente }): Promise<Colunista> => {
      let foto_url: string | null = null;
      let mini_bio = "";
      let credenciado = false;
      let numero_seguidores = 0;
      try {
        const perfil = await obterPerfilAutor(autorId);
        foto_url = perfil.foto_url || null;
        mini_bio = perfil.mini_bio || "";
        credenciado = !!perfil.credenciado;
        numero_seguidores = perfil.numero_seguidores || 0;
      } catch {
        // Perfil indisponível — mantém valores vazios honestos.
      }
      return {
        id: autorId,
        nome: recente.autor_nome || `Autor #${autorId}`,
        foto_url,
        mini_bio,
        credenciado,
        especialidade: especialidadeDe(lista),
        total_textos: lista.length,
        numero_seguidores,
        recente,
        selo: seloPublicacao(recente),
      };
    })
  );
  return colunistas;
}

/** Data do conteúdo (publicação ou criação) formatada pt-BR curta. */
export function formatarDataConteudo(pub: Publicacao): string {
  const iso = pub.publicado_em || pub.criado_em;
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return "";
    return d.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric" });
  } catch {
    return "";
  }
}
