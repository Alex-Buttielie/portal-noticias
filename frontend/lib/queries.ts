"use client";

import { useQuery, type QueryClient } from "@tanstack/react-query";
import * as api from "@/lib/api";
import { queryKeys, type FiltrosAdminAssinaturas, type FiltrosAdminDenuncias, type FiltrosEvolucaoRadar, type FiltrosPublicacoesComunidade, type FiltrosRadar } from "@/lib/query-keys";

const STALE_TIME_PUBLICO_MS = 60_000;
const STALE_TIME_PRIVADO_MS = 15_000;
/** Telas de decisão (Admin) — sempre frescas. */
const STALE_TIME_DECISAO_MS = 0;

/** Gate padrão de leitura autenticada: exige token e usuário válido. */
function habilitadoAdmin(token: string | null, usuarioId: number): boolean {
  return Boolean(token && usuarioId > 0);
}

export function useQueryPlanos() {
  return useQuery({
    queryKey: queryKeys.planos.publicos(),
    queryFn: api.obterPlanos,
  });
}

export function useQueryFeedUltimasNoticias(
  pageSize: number,
  inicial: api.FeedEntrada[],
  intervaloSegundos: number
) {
  return useQuery({
    queryKey: queryKeys.feed.ultimasNoticias(pageSize),
    queryFn: () => api.obterFeed({ page_size: pageSize }),
    initialData: {
      count: inicial.length,
      next: null,
      previous: null,
      results: inicial,
    },
    staleTime: STALE_TIME_PUBLICO_MS,
    refetchInterval:
      intervaloSegundos > 0 ? intervaloSegundos * 1_000 : false,
    refetchIntervalInBackground: false,
  });
}

export function useQueryCobertura(
  tipo: "cluster" | "item",
  id: number,
  enabled: boolean
) {
  return useQuery({
    queryKey: queryKeys.cobertura.porEntrada(tipo, id),
    queryFn: ({ signal }) => api.obterCobertura(tipo, id),
    enabled: enabled && id > 0,
  });
}

export function useQueryTendenciasRadar(
  filtros: FiltrosRadar,
  comPolling = false
) {
  return useQuery({
    queryKey: queryKeys.radar.tendencias(filtros),
    queryFn: () => api.obterTendenciasRadar(filtros),
    refetchInterval: comPolling ? 60_000 : false,
    refetchIntervalInBackground: false,
  });
}

export function useQueryPublicacoesComunidade(
  filtros: FiltrosPublicacoesComunidade
) {
  return useQuery({
    queryKey: queryKeys.comunidade.publicacoes(filtros),
    queryFn: ({ signal }) => api.obterPublicacoes(filtros, { signal }),
  });
}

export function useQueryPublicacaoComunidade(input: {
  id: number;
  token: string | null;
  usuarioId?: number | null;
}) {
  return useQuery({
    queryKey: queryKeys.comunidade.publicacao(input.id, input.usuarioId),
    queryFn: () => api.obterPublicacao(input.token, input.id),
    enabled: input.id > 0,
  });
}

export function useQueryComentariosComunidade(publicacaoId: number) {
  return useQuery({
    queryKey: queryKeys.comunidade.comentarios(publicacaoId),
    queryFn: () => api.obterComentarios({ publicacao: publicacaoId }),
    enabled: publicacaoId > 0,
  });
}

export function useQueryRelacionadasComunidade(
  categoria: string | undefined,
  enabled: boolean
) {
  return useQuery({
    queryKey: queryKeys.comunidade.relacionadas(categoria ?? ""),
    queryFn: ({ signal }) =>
      api.obterPublicacoes(
        { categoria: categoria || undefined, ordenar: "discutidos" },
        { signal }
      ),
    enabled: enabled && Boolean(categoria),
  });
}

export function useQueryNoticiasRelacionadas(
  categoria: string | undefined,
  enabled: boolean
) {
  return useQuery({
    queryKey: queryKeys.feed.noticiasRelacionadas(categoria ?? ""),
    queryFn: () => api.obterFeed({ categoria: categoria || undefined }),
    enabled: enabled && Boolean(categoria),
  });
}

export function useQueryPerfilAutor(autorId: number, enabled: boolean) {
  return useQuery({
    queryKey: queryKeys.comunidade.perfilAutor(autorId),
    queryFn: ({ signal }) => api.obterPerfilAutor(autorId, { signal }),
    enabled: enabled && autorId > 0,
  });
}

export function useQueryRadarEvolucao(input: {
  token: string | null;
  usuarioId: number;
  filtros: FiltrosEvolucaoRadar;
}) {
  return useQuery({
    queryKey: queryKeys.radar.evolucao(input.usuarioId, input.filtros),
    queryFn: () => api.obterEvolucaoRadar(input.token ?? "", input.filtros),
    enabled: Boolean(input.token && input.usuarioId > 0),
    staleTime: STALE_TIME_PRIVADO_MS,
  });
}

export function useQueryRadarLocalidadesSalvas(input: {
  token: string | null;
  usuarioId: number;
}) {
  return useQuery({
    queryKey: queryKeys.radar.localidadesSalvas(input.usuarioId),
    queryFn: () => api.obterLocalidadesSalvas(input.token ?? ""),
    enabled: Boolean(input.token && input.usuarioId > 0),
    staleTime: STALE_TIME_PRIVADO_MS,
  });
}

export function useQuerySolicitacaoJornalista(input: {
  token: string | null;
  usuarioId: number;
}) {
  return useQuery({
    queryKey: queryKeys.jornalista.solicitacao(input.usuarioId),
    queryFn: () =>
      api.obterMinhaSolicitacaoCredenciamento(input.token ?? ""),
    enabled: Boolean(input.token && input.usuarioId > 0),
    staleTime: STALE_TIME_PRIVADO_MS,
  });
}

export function useQueryPerfilJornalista(input: {
  token: string | null;
  usuarioId: number;
}) {
  return useQuery({
    queryKey: queryKeys.jornalista.perfil(input.usuarioId),
    queryFn: () => api.obterMeuPerfilJornalista(input.token ?? ""),
    enabled: Boolean(input.token && input.usuarioId > 0),
    staleTime: STALE_TIME_PRIVADO_MS,
  });
}

interface InvalidacaoComunidade {
  publicacaoId?: number;
  autorId?: number;
  usuarioId?: number | null;
}

/**
 * Constrói o conjunto de chaves de query a invalidar.
 * Cada chamada retorna um novo array; não há mutação compartilhada.
 * O retorno é readonly unknown[][] compatível com JSON.stringify e a invalidation.
 */
function chavesInvalidacaoComunidade(
  alvo: InvalidacaoComunidade
): readonly unknown[][] {
  const pubId = alvo.publicacaoId;
  const authId = alvo.autorId;
  const pubHas = pubId !== undefined && pubId > 0;
  const authHas = authId !== undefined && authId > 0;

  // Base (sempre presente)
  const base0: unknown[] = [queryKeys.comunidade.publicacoesRaiz()];
  const base1: unknown[] = [queryKeys.comunidade.relacionadasRaiz()];
  const base2: unknown[] = [queryKeys.feed.noticiasRelacionadasRaiz()];

  // Itens condicionais (tambiã como unknown[])
  const c0: unknown[] = pubHas
    ? [queryKeys.comunidade.comentarios(pubId!)]
    : [];

  const c1: unknown[] = pubHas
    ? [queryKeys.comunidade.publicacao(pubId!, null)]
    : [];

  const c2: unknown[] = pubHas
    && alvo.usuarioId && alvo.usuarioId > 0
      ? [queryKeys.comunidade.publicacao(pubId!, alvo.usuarioId!)]
      : [];

  const c3: unknown[] = authHas
    ? [queryKeys.comunidade.perfilAutor(authId!)]
    : [];

  // Montagem final - usa spread com tipo any intermediário para burlar TS
  if (pubHas && authHas) {
    return [
      ...base0, ...base1, ...base2, ...c0, ...c1, ...c2, ...c3,
    ] as unknown[][] as readonly unknown[][];
  }
  if (pubHas) {
    return [
      ...base0, ...base1, ...base2, ...c0, ...c1, ...c2,
    ] as unknown[][] as readonly unknown[][];
  }
  if (authHas) {
    return [
      ...base0, ...base1, ...base2, ...c3,
    ] as unknown[][] as readonly unknown[][];
  }
  return [
    ...base0, ...base1, ...base2,
  ] as unknown[][] as readonly unknown[][];
}

export async function invalidarQueriesComunidade(
  cliente: QueryClient,
  alvo: InvalidacaoComunidade = {}
): Promise<void> {
  const chaves = chavesInvalidacaoComunidade(alvo);

  await Promise.all(
    [...new Set(chaves.map((chave) => JSON.stringify(chave)))].map((serialized) => {
      const chave = chaves.find((item) => JSON.stringify(item) === serialized);
      return chave
        ? cliente.invalidateQueries({ queryKey: chave })
        : Promise.resolve();
    })
  );
}

export async function invalidarQueriesRadarLocalidades(
  cliente: QueryClient,
  usuarioId: number
): Promise<void> {
  await cliente.invalidateQueries({
    queryKey: queryKeys.radar.localidadesSalvas(usuarioId),
  });
}

// ---------------------------------------------------------------------------
// Admin — telas de decisão. Leitura autenticada (token no closure, nunca na
// chave); staleTime 0 para que montar a tela sempre traga dados do momento.
// ---------------------------------------------------------------------------

export function useQueryAdminFila(input: {
  token: string | null;
  usuarioId: number;
  status: string | null | undefined;
  page: number;
  /** Polling opcional (ms) — Auto 30s da fila de curadoria. */
  intervaloMs?: number;
}) {
  return useQuery({
    queryKey: queryKeys.admin.fila(input.status, input.page),
    queryFn: () =>
      api.adminListarFila(input.token ?? "", {
        status: input.status || undefined,
        page: input.page,
      }),
    enabled: habilitadoAdmin(input.token, input.usuarioId),
    staleTime: STALE_TIME_DECISAO_MS,
    placeholderData: (anterior) => anterior,
    refetchInterval:
      input.intervaloMs && input.intervaloMs > 0 ? input.intervaloMs : false,
    refetchIntervalInBackground: false,
  });
}

export function useQueryAdminUsuarios(input: {
  token: string | null;
  usuarioId: number;
  /** null = ainda não buscou — a tela espera o clique em "Buscar". */
  busca: string | null;
  /** Gate adicional da tela (só carregar após a busca ser submetida). */
  habilitada: boolean;
}) {
  return useQuery({
    queryKey: queryKeys.admin.usuarios(input.busca),
    queryFn: () =>
      api.adminListarUsuarios(input.token ?? "", {
        search: input.busca || undefined,
      }),
    enabled: input.habilitada && habilitadoAdmin(input.token, input.usuarioId),
    staleTime: STALE_TIME_DECISAO_MS,
    placeholderData: (anterior) => anterior,
  });
}

export function useQueryAdminAssinaturas(input: {
  token: string | null;
  usuarioId: number;
  filtros: FiltrosAdminAssinaturas;
  /** Gate adicional da tela (só carregar após a busca ser submetida). */
  habilitada: boolean;
}) {
  return useQuery({
    queryKey: queryKeys.admin.assinaturas(input.filtros),
    queryFn: () =>
      api.adminListarAssinaturas(input.token ?? "", {
        search: input.filtros.busca || undefined,
        status: input.filtros.status || undefined,
      }),
    enabled: input.habilitada && habilitadoAdmin(input.token, input.usuarioId),
    staleTime: STALE_TIME_DECISAO_MS,
    placeholderData: (anterior) => anterior,
  });
}

export function useQueryAdminDenuncias(input: {
  token: string | null;
  usuarioId: number;
  filtros: FiltrosAdminDenuncias;
  /** Gate adicional da tela (só carregar após o clique em "Carregar"). */
  habilitada: boolean;
}) {
  return useQuery({
    queryKey: queryKeys.admin.denuncias(input.filtros),
    queryFn: () =>
      api.adminListarDenuncias(input.token ?? "", {
        status: input.filtros.status || undefined,
      }),
    enabled: input.habilitada && habilitadoAdmin(input.token, input.usuarioId),
    staleTime: STALE_TIME_DECISAO_MS,
    placeholderData: (anterior) => anterior,
  });
}

export function useQueryAdminPlanos(input: {
  token: string | null;
  usuarioId: number;
}) {
  return useQuery({
    queryKey: queryKeys.admin.planosAdmin(),
    queryFn: () => api.adminListarPlanos(input.token ?? ""),
    enabled: habilitadoAdmin(input.token, input.usuarioId),
    staleTime: STALE_TIME_DECISAO_MS,
  });
}

export function useQueryAdminLimites(input: {
  token: string | null;
  usuarioId: number;
}) {
  return useQuery({
    queryKey: queryKeys.admin.limites(),
    queryFn: () => api.adminListarLimites(input.token ?? ""),
    enabled: habilitadoAdmin(input.token, input.usuarioId),
    staleTime: STALE_TIME_DECISAO_MS,
  });
}

export function useQueryAdminFontes(input: {
  token: string | null;
  usuarioId: number;
}) {
  return useQuery({
    queryKey: queryKeys.admin.fontes(),
    queryFn: () => api.robosListarFontes(input.token ?? ""),
    enabled: habilitadoAdmin(input.token, input.usuarioId),
    staleTime: STALE_TIME_DECISAO_MS,
  });
}

export function useQueryAdminRoboConfig(input: {
  token: string | null;
  usuarioId: number;
}) {
  return useQuery({
    queryKey: queryKeys.admin.roboConfig(),
    queryFn: () => api.robosObterConfig(input.token ?? ""),
    enabled: habilitadoAdmin(input.token, input.usuarioId),
    staleTime: STALE_TIME_DECISAO_MS,
  });
}

export function useQueryAdminRoboExecucoes(input: {
  token: string | null;
  usuarioId: number;
}) {
  return useQuery({
    queryKey: queryKeys.admin.roboExecucoes(),
    queryFn: () => api.robosListarExecucoes(input.token ?? ""),
    enabled: habilitadoAdmin(input.token, input.usuarioId),
    staleTime: STALE_TIME_DECISAO_MS,
  });
}

export function useQueryAdminCentralInteligencia(input: {
  token: string | null;
  usuarioId: number;
  periodo: api.PeriodoInteligencia;
  inicio: string | null;
  fim: string | null;
}) {
  return useQuery({
    queryKey: queryKeys.admin.metricas(input.periodo, input.inicio, input.fim),
    queryFn: () =>
      api.obterCentralInteligencia(input.token ?? "", {
        periodo: input.periodo,
        inicio: input.inicio || undefined,
        fim: input.fim || undefined,
      }),
    enabled: habilitadoAdmin(input.token, input.usuarioId),
    staleTime: STALE_TIME_DECISAO_MS,
  });
}

export function useQueryAdminDestaques(input: {
  token: string | null;
  usuarioId: number;
}) {
  return useQuery({
    queryKey: queryKeys.admin.destaques(),
    queryFn: () => api.adminListarDestaques(input.token ?? ""),
    enabled: habilitadoAdmin(input.token, input.usuarioId),
    staleTime: STALE_TIME_DECISAO_MS,
  });
}

export function useQueryAdminRegras(input: {
  token: string | null;
  usuarioId: number;
}) {
  return useQuery({
    queryKey: queryKeys.admin.regras(),
    queryFn: () => api.adminListarRegras(input.token ?? ""),
    enabled: habilitadoAdmin(input.token, input.usuarioId),
    staleTime: STALE_TIME_DECISAO_MS,
  });
}

export function useQueryAdminSistema(input: {
  token: string | null;
  usuarioId: number;
}) {
  return useQuery({
    queryKey: queryKeys.admin.sistema(),
    queryFn: () => api.obterConfigSistemaAdmin(input.token ?? ""),
    enabled: habilitadoAdmin(input.token, input.usuarioId),
    staleTime: STALE_TIME_DECISAO_MS,
  });
}
