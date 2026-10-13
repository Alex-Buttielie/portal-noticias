const AMBIENTE_QUERY =
  process.env.NEXT_PUBLIC_API_BASE_URL?.trim() || "mesma-origem";

export interface FiltrosRadar {
  pais?: string;
  estado?: string;
  // R-02 — coordenada do usuário (quando disponível em `Regiao`), usada
  // para ordenar por proximidade; não altera o RECORTE (`estado`), só a
  // ordem dos resultados — por isso entra na chave de cache.
  lat?: number;
  lon?: number;
}

export interface FiltrosEvolucaoRadar extends FiltrosRadar {
  categoria?: string;
}

export interface FiltrosNoticiasRadar extends FiltrosRadar {
  categoria?: string;
  busca?: string;
  periodoDias?: number;
}

export interface FiltrosPublicacoesComunidade {
  ordenar?: "recentes" | "discutidos" | "destaques";
  categoria?: string;
  tipo?: string;
  busca?: string;
  destaque?: boolean;
}

export interface FiltrosAdminAssinaturas {
  busca?: string | null;
  status?: string | null;
}

export interface FiltrosAdminDenuncias {
  status?: string | null;
}

export interface FiltrosAdminUsuarios {
  busca?: string | null;
  papel?: string | null;
  page?: number;
}

export interface FiltrosAdminAuditoria {
  acao?: string | null;
  alvoTipo?: string | null;
  page?: number;
}

export interface FiltrosAdminHistoricoLimites {
  chave?: string | null;
  plano?: string | null;
  page?: number;
}

function textoNormalizado(valor: string | null | undefined): string {
  return valor?.trim().toLowerCase() ?? "";
}

function idNormalizado(valor: number): number {
  return Number.isSafeInteger(valor) && valor > 0 ? valor : 0;
}

function coordenadaNormalizada(valor: number | undefined): number {
  // R-02 — arredonda a 2 casas (~1km) antes de entrar na chave de cache: a
  // ordenação por distância é por UF (capital), então jitter de GPS na 3ª
  // casa decimal não deveria gerar uma query nova.
  return typeof valor === "number" && Number.isFinite(valor) ? Math.round(valor * 100) / 100 : 0;
}

function filtrosLocalidade(filtros: FiltrosRadar) {
  return {
    pais: textoNormalizado(filtros.pais),
    estado: textoNormalizado(filtros.estado),
    lat: coordenadaNormalizada(filtros.lat),
    lon: coordenadaNormalizada(filtros.lon),
  };
}

function filtrosPublicacoes(
  filtros: FiltrosPublicacoesComunidade
) {
  const ordenar = filtros.ordenar;
  return {
    ordenar:
      ordenar === "discutidos" || ordenar === "destaques"
        ? ordenar
        : "recentes",
    categoria: textoNormalizado(filtros.categoria),
    tipo: textoNormalizado(filtros.tipo),
    busca: textoNormalizado(filtros.busca),
    destaque: filtros.destaque === true,
  };
}

/**
 * Fábricas explícitas: não existe uma chave genérica que aceite token, e-mail
 * ou o objeto de usuário. Queries privadas recebem somente `usuarioId` e
 * filtros fechados; credenciais permanecem no closure do `queryFn`.
 */
export const queryKeys = {
  privadas: () => ["privado"] as const,

  premium: {
    status: () => ["publico", AMBIENTE_QUERY, "premium", "status"] as const,
  },

  planos: {
    publicos: () => ["publico", AMBIENTE_QUERY, "planos"] as const,
  },

  patrocinio: {
    ativo: (posicao: string) => ["publico", AMBIENTE_QUERY, "patrocinio", "ativo", posicao] as const,
  },

  feed: {
    noticiasRelacionadasRaiz: () =>
      ["publico", AMBIENTE_QUERY, "feed", "noticias-relacionadas"] as const,
    ultimasNoticias: (pageSize: number) =>
      [
        "publico",
        AMBIENTE_QUERY,
        "feed",
        "ultimas-noticias",
        { pageSize: Math.max(1, Math.trunc(pageSize)) },
      ] as const,
    noticiasRelacionadas: (categoria: string) =>
      [
        "publico",
        AMBIENTE_QUERY,
        "feed",
        "noticias-relacionadas",
        { categoria: textoNormalizado(categoria) },
      ] as const,
  },

  cobertura: {
    porEntrada: (tipo: "cluster" | "item", id: number) =>
      [
        "publico",
        AMBIENTE_QUERY,
        "cobertura",
        { tipo, id: idNormalizado(id) },
      ] as const,
  },

  radar: {
    tendencias: (filtros: FiltrosRadar = {}) =>
      ["publico", AMBIENTE_QUERY, "radar", "tendencias", filtrosLocalidade(filtros)] as const,
    evolucao: (usuarioId: number, filtros: FiltrosEvolucaoRadar) =>
      [
        "privado",
        AMBIENTE_QUERY,
        "radar",
        "evolucao",
        {
          usuarioId: idNormalizado(usuarioId),
          filtros: {
            ...filtrosLocalidade(filtros),
            categoria: textoNormalizado(filtros.categoria),
          },
        },
      ] as const,
    noticias: (filtros: FiltrosNoticiasRadar = {}) =>
      [
        "publico",
        AMBIENTE_QUERY,
        "radar",
        "noticias",
        {
          ...filtrosLocalidade(filtros),
          categoria: textoNormalizado(filtros.categoria),
          busca: textoNormalizado(filtros.busca),
          periodoDias: Number.isSafeInteger(filtros.periodoDias) && (filtros.periodoDias ?? 0) > 0 ? filtros.periodoDias : 0,
        },
      ] as const,
    localidadesSalvas: (usuarioId: number) =>
      [
        "privado",
        AMBIENTE_QUERY,
        "radar",
        "localidades-salvas",
        { usuarioId: idNormalizado(usuarioId) },
      ] as const,
  },

  comunidade: {
    publicacoesRaiz: () =>
      ["publico", AMBIENTE_QUERY, "comunidade", "publicacoes"] as const,
    publicacoes: (filtros: FiltrosPublicacoesComunidade = {}) =>
      [
        "publico",
        AMBIENTE_QUERY,
        "comunidade",
        "publicacoes",
        filtrosPublicacoes(filtros),
      ] as const,
    relacionadasRaiz: () =>
      ["publico", AMBIENTE_QUERY, "comunidade", "relacionadas"] as const,
    relacionadas: (categoria: string) =>
      [
        "publico",
        AMBIENTE_QUERY,
        "comunidade",
        "relacionadas",
        { categoria: textoNormalizado(categoria) },
      ] as const,
    perfilAutor: (autorId: number) =>
      [
        "publico",
        AMBIENTE_QUERY,
        "comunidade",
        "perfil-autor",
        { autorId: idNormalizado(autorId) },
      ] as const,
    publicacao: (id: number, usuarioId?: number | null) => {
      const idPublicacao = idNormalizado(id);
      const idUsuario = idNormalizado(usuarioId ?? 0);
      return idUsuario > 0
        ? (["privado", AMBIENTE_QUERY, "comunidade", "publicacao", {
            usuarioId: idUsuario,
            id: idPublicacao,
          }] as const)
        : (["publico", AMBIENTE_QUERY, "comunidade", "publicacao", {
            id: idPublicacao,
          }] as const);
    },
    comentarios: (publicacaoId: number) =>
      [
        "publico",
        AMBIENTE_QUERY,
        "comunidade",
        "comentarios",
        { publicacaoId: idNormalizado(publicacaoId) },
      ] as const,
  },

  jornalista: {
    solicitacao: (usuarioId: number) =>
      [
        "privado",
        AMBIENTE_QUERY,
        "jornalista",
        "solicitacao",
        { usuarioId: idNormalizado(usuarioId) },
      ] as const,
    perfil: (usuarioId: number) =>
      [
        "privado",
        AMBIENTE_QUERY,
        "jornalista",
        "perfil",
        { usuarioId: idNormalizado(usuarioId) },
      ] as const,
  },

  /**
   * Telas de decisão (Admin). Leitura autenticada: por isso o prefixo
   * "privado" — o QuerySessionBoundary limpa o cache no logout/troca.
   * Chaves sem token, e-mail ou objeto de usuário; credenciais ficam no
   * closure do `queryFn`. O staleTime 0 (sempre frescas) fica em queries.ts.
   */
  admin: {
    filaRaiz: () => ["privado", AMBIENTE_QUERY, "admin", "fila"] as const,
    fila: (status: string | null | undefined, page: number) =>
      [
        "privado",
        AMBIENTE_QUERY,
        "admin",
        "fila",
        {
          status: textoNormalizado(status) || "todas",
          page: Math.max(1, Math.trunc(page)),
        },
      ] as const,
    usuariosRaiz: () =>
      ["privado", AMBIENTE_QUERY, "admin", "usuarios"] as const,
    usuarios: (filtros: FiltrosAdminUsuarios = {}) =>
      [
        "privado",
        AMBIENTE_QUERY,
        "admin",
        "usuarios",
        {
          busca: filtros.busca == null ? null : textoNormalizado(filtros.busca),
          papel: filtros.papel == null ? null : textoNormalizado(filtros.papel),
          page: Math.max(1, Math.trunc(filtros.page ?? 1)),
        },
      ] as const,
    usuariosAtivosAgora: () =>
      ["privado", AMBIENTE_QUERY, "admin", "usuarios-ativos-agora"] as const,
    assinaturasRaiz: () =>
      ["privado", AMBIENTE_QUERY, "admin", "assinaturas"] as const,
    assinaturas: (filtros: FiltrosAdminAssinaturas = {}) =>
      [
        "privado",
        AMBIENTE_QUERY,
        "admin",
        "assinaturas",
        {
          busca: filtros.busca == null ? null : textoNormalizado(filtros.busca),
          status:
            filtros.status == null ? null : textoNormalizado(filtros.status),
        },
      ] as const,
    denunciasRaiz: () =>
      ["privado", AMBIENTE_QUERY, "admin", "moderacao-denuncias"] as const,
    denuncias: (filtros: FiltrosAdminDenuncias = {}) =>
      [
        "privado",
        AMBIENTE_QUERY,
        "admin",
        "moderacao-denuncias",
        {
          status:
            filtros.status == null ? null : textoNormalizado(filtros.status),
        },
      ] as const,
    planosAdmin: () => ["privado", AMBIENTE_QUERY, "admin", "planos"] as const,
    limites: () => ["privado", AMBIENTE_QUERY, "admin", "limites"] as const,
    fontes: () => ["privado", AMBIENTE_QUERY, "admin", "robos-fontes"] as const,
    roboConfig: () =>
      ["privado", AMBIENTE_QUERY, "admin", "robos-config"] as const,
    roboExecucoes: () =>
      ["privado", AMBIENTE_QUERY, "admin", "robos-execucoes"] as const,
    metricas: (periodo: string, inicio: string | null, fim: string | null) =>
      [
        "privado",
        AMBIENTE_QUERY,
        "admin",
        "inteligencia",
        {
          periodo: textoNormalizado(periodo),
          inicio: inicio ? textoNormalizado(inicio) : null,
          fim: fim ? textoNormalizado(fim) : null,
        },
      ] as const,
    destaques: () =>
      ["privado", AMBIENTE_QUERY, "admin", "destaque-editoriais"] as const,
    regras: () =>
      ["privado", AMBIENTE_QUERY, "admin", "regras-curadoria"] as const,
    sistema: () => ["privado", AMBIENTE_QUERY, "admin", "sistema"] as const,
    auditoriaRaiz: () =>
      ["privado", AMBIENTE_QUERY, "admin", "auditoria"] as const,
    auditoria: (filtros: FiltrosAdminAuditoria = {}) =>
      [
        "privado",
        AMBIENTE_QUERY,
        "admin",
        "auditoria",
        {
          acao: filtros.acao == null ? null : textoNormalizado(filtros.acao),
          alvoTipo: filtros.alvoTipo == null ? null : textoNormalizado(filtros.alvoTipo),
          page: Math.max(1, Math.trunc(filtros.page ?? 1)),
        },
      ] as const,
    historicoLimitesRaiz: () =>
      ["privado", AMBIENTE_QUERY, "admin", "historico-limites"] as const,
    historicoLimites: (filtros: FiltrosAdminHistoricoLimites = {}) =>
      [
        "privado",
        AMBIENTE_QUERY,
        "admin",
        "historico-limites",
        {
          chave: filtros.chave == null ? null : textoNormalizado(filtros.chave),
          plano: filtros.plano == null ? null : textoNormalizado(filtros.plano),
          page: Math.max(1, Math.trunc(filtros.page ?? 1)),
        },
      ] as const,
    atividadeRecente: () =>
      ["privado", AMBIENTE_QUERY, "admin", "atividade-recente"] as const,
  },
} as const;
