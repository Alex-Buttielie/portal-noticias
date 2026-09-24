import { obterPerfilAutor, obterPublicacoes, type Publicacao } from "./api";
import type { SeloEditorial } from "./editorial";
import { formatarDataCurta } from "./datas";

// A listagem é a etapa que decide se a seção existe; por isso recebe um
// orçamento mais tolerante que o deadline original de 2 s.
const TIMEOUT_PUBLICACOES_COLUNISTAS_MS = 5000;
// Cada perfil é opcional e independente: um perfil lento não cancela os demais.
const TIMEOUT_PERFIL_COLUNISTA_MS = 2000;
const PAGE_SIZE_COLUNISTAS = 6;

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
 * Carrega colunistas no servidor/ISR: publicações em destaque (fallback:
 * recentes), agrupadas por autor, com perfil público (foto/bio/seguidores)
 * buscado em paralelo e ignorado silenciosamente quando indisponível.
 * A consulta é limitada e usa um deadline de 5 s para as publicações; cada
 * perfil tem timeout próprio de 2 s e um perfil lento não cancela os demais.
 * Retorna [] quando a listagem não pode ser concluída — a seção se oculta,
 * nunca exibe dado inventado. O timeout continua sendo um guardrail: uma
 * listagem lenta não deve prender a revalidação da Home.
 */
export async function carregarColunistas(limite = 4): Promise<Colunista[]> {
  const quantidade = Number.isFinite(limite) ? Math.max(1, Math.floor(limite)) : 1;
  const tamanhoConsulta = Math.max(quantidade, PAGE_SIZE_COLUNISTAS);
  const controllerPublicacoes = new AbortController();
  const timeoutPublicacoes = setTimeout(
    () => controllerPublicacoes.abort(),
    TIMEOUT_PUBLICACOES_COLUNISTAS_MS
  );

  try {
    let pubs: Publicacao[];
    try {
      const destaques = await obterPublicacoes(
        { destaque: true, page_size: tamanhoConsulta },
        { signal: controllerPublicacoes.signal }
      );
      pubs = destaques.length
        ? destaques
        : await obterPublicacoes({ page_size: tamanhoConsulta }, { signal: controllerPublicacoes.signal });
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
      .slice(0, quantidade);

    return await Promise.all(
      grupos.map(async ({ autorId, lista, recente }): Promise<Colunista> => {
        let foto_url: string | null = null;
        let mini_bio = "";
        let credenciado = false;
        let numero_seguidores = 0;
        let textos = lista;
        const controllerPerfil = new AbortController();
        const timeoutPerfil = setTimeout(
          () => controllerPerfil.abort(),
          TIMEOUT_PERFIL_COLUNISTA_MS
        );
        try {
          const perfil = await obterPerfilAutor(autorId, { signal: controllerPerfil.signal });
          foto_url = perfil.foto_url || null;
          mini_bio = perfil.mini_bio || "";
          credenciado = !!perfil.credenciado;
          numero_seguidores = perfil.numero_seguidores || 0;
          // A listagem paginada é apenas a amostra de apresentação; quando
          // disponível, o perfil preserva a contagem/especialidade completas.
          if (Array.isArray(perfil.publicacoes) && perfil.publicacoes.length) {
            textos = perfil.publicacoes;
          }
        } catch {
          // Perfil indisponível — mantém valores vazios honestos.
        } finally {
          clearTimeout(timeoutPerfil);
        }
        return {
          id: autorId,
          nome: recente.autor_nome || `Autor #${autorId}`,
          foto_url,
          mini_bio,
          credenciado,
          especialidade: especialidadeDe(textos),
          total_textos: textos.length,
          numero_seguidores,
          recente,
          selo: seloPublicacao(recente),
        };
      })
    );
  } catch {
    return [];
  } finally {
    clearTimeout(timeoutPublicacoes);
  }
}

/** Data do conteúdo (publicação ou criação) formatada pt-BR curta. */
export function formatarDataConteudo(pub: Publicacao): string {
  return formatarDataCurta(pub.publicado_em || pub.criado_em);
}
