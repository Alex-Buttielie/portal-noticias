"use client";

import {
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationResult,
  type UseQueryResult,
} from "@tanstack/react-query";
import * as api from "./api";
import { useAuth } from "./auth-context";

// Camada de dados padronizada sobre lib/api.ts. Páginas usam estes hooks em
// vez de useEffect manual — loading/erro ficam uniformes em toda a interface.

export interface FiltroFeed {
  categoria?: string;
  busca?: string;
}

export function useFeed(filtro: FiltroFeed) {
  return useInfiniteQuery({
    queryKey: ["feed", filtro.categoria ?? "", filtro.busca ?? ""],
    queryFn: ({ pageParam }) =>
      api.obterFeed({ categoria: filtro.categoria, busca: filtro.busca, page: pageParam as number }),
    initialPageParam: 1,
    getNextPageParam: (ultima, paginas) => (ultima.next ? paginas.length + 1 : undefined),
  });
}

export function useUrgentes(limite = 6): UseQueryResult<api.FeedEntrada[], Error> {
  return useQuery({ queryKey: ["urgentes", limite], queryFn: () => api.obterUrgentes(limite) });
}

export function useMaisLidas(limite = 5): UseQueryResult<api.FeedEntrada[], Error> {
  return useQuery({ queryKey: ["mais-lidas", limite], queryFn: () => api.obterMaisLidas(limite) });
}

export function useDetalheCluster(id: number | string, inicial?: api.FeedDetalhe | null): UseQueryResult<api.FeedDetalhe, Error> {
  return useQuery({
    queryKey: ["cluster", String(id)],
    queryFn: () => api.obterDetalheCluster(id),
    enabled: Boolean(id),
    initialData: inicial ?? undefined,
    staleTime: 60 * 1000,
  });
}

export function useDetalheItem(id: number | string, inicial?: api.FeedDetalhe | null): UseQueryResult<api.FeedDetalhe, Error> {
  return useQuery({
    queryKey: ["item", String(id)],
    queryFn: () => api.obterDetalheItem(id),
    enabled: Boolean(id),
    initialData: inicial ?? undefined,
    staleTime: 60 * 1000,
  });
}

export function usePublicacoes(params: { destaque?: boolean; autor?: number } = {}): UseQueryResult<api.Publicacao[], Error> {
  return useQuery({
    queryKey: ["publicacoes", params.destaque ?? null, params.autor ?? null],
    queryFn: () => api.obterPublicacoes(params),
  });
}

export function usePublicacao(id: number): UseQueryResult<api.Publicacao | null, Error> {
  const { token } = useAuth();
  return useQuery({
    queryKey: ["publicacao", id],
    queryFn: () => api.obterPublicacao(token, id),
    enabled: Number.isFinite(id),
  });
}

export function useComentarios(publicacaoId: number): UseQueryResult<api.Comentario[], Error> {
  return useQuery({
    queryKey: ["comentarios", publicacaoId],
    queryFn: () => api.obterComentarios({ publicacao: publicacaoId }),
    enabled: Number.isFinite(publicacaoId),
  });
}

export function useComentar(publicacaoId: number): UseMutationResult<api.Comentario, Error, string> {
  const { token } = useAuth();
  const cliente = useQueryClient();
  return useMutation({
    mutationFn: (conteudo: string) => api.comentar(token ?? "", { conteudo, publicacao: publicacaoId }),
    onSuccess: () => {
      void cliente.invalidateQueries({ queryKey: ["comentarios", publicacaoId] });
    },
  });
}

export function useEditarPublicacao(publicacaoId: number): UseMutationResult<api.Publicacao, Error, { titulo?: string; conteudo?: string }> {
  const { token } = useAuth();
  const cliente = useQueryClient();
  return useMutation({
    mutationFn: (dados: { titulo?: string; conteudo?: string }) =>
      api.editarPublicacao(token ?? "", publicacaoId, dados),
    onSuccess: (atualizada) => {
      cliente.setQueryData(["publicacao", publicacaoId], atualizada);
      void cliente.invalidateQueries({ queryKey: ["publicacoes"] });
    },
  });
}

export function usePublicarAnalise(): UseMutationResult<api.Publicacao, Error, { titulo: string; conteudo: string; tipo: api.TipoPublicacao; categoria: string }> {
  const { token } = useAuth();
  const cliente = useQueryClient();
  return useMutation({
    mutationFn: async (dados: { titulo: string; conteudo: string; tipo: api.TipoPublicacao; categoria: string }) => {
      const rascunho = await api.criarRascunhoPublicacao(token ?? "", {
        titulo: dados.titulo,
        conteudo: dados.conteudo,
        tipo: dados.tipo,
        categoria: dados.categoria || undefined,
      });
      return api.enviarPublicacao(token ?? "", rascunho.id);
    },
    onSuccess: () => {
      void cliente.invalidateQueries({ queryKey: ["publicacoes"] });
    },
  });
}

export function useTendenciasRadar(params: { pais?: string; estado?: string; cidade?: string }): UseQueryResult<Awaited<ReturnType<typeof api.obterTendenciasRadar>>, Error> {
  return useQuery({
    queryKey: ["radar", params.pais ?? "", params.estado ?? "", params.cidade ?? ""],
    queryFn: () => api.obterTendenciasRadar(params),
  });
}

export function usePlanos(): UseQueryResult<api.Plano[], Error> {
  return useQuery({ queryKey: ["planos"], queryFn: api.obterPlanos, staleTime: 5 * 60 * 1000 });
}

export function useMinhaAssinatura(): UseQueryResult<api.Assinatura | null, Error> {
  const { token } = useAuth();
  return useQuery({
    queryKey: ["minha-assinatura"],
    queryFn: () => (token ? api.obterMinhaAssinatura(token) : Promise.resolve(null)),
    enabled: Boolean(token),
  });
}

export function useAssinarPlano(): UseMutationResult<api.Assinatura, Error, number> {
  const { token } = useAuth();
  const cliente = useQueryClient();
  return useMutation({
    mutationFn: (planId: number) => api.assinarPlano(token ?? "", planId),
    onSuccess: () => {
      void cliente.invalidateQueries({ queryKey: ["minha-assinatura"] });
    },
  });
}
