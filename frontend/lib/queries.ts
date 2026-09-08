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
import { useToast } from "@/components/ToastProvider";

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

export function useCadastrar(): UseMutationResult<
  unknown,
  Error,
  { email: string; nome: string; senha: string; aceite_termos: boolean }
> {
  return useMutation({
    mutationFn: (dados: { email: string; nome: string; senha: string; aceite_termos: boolean }) =>
      api.cadastrar(dados),
  });
}

export function useOnboarding(): UseQueryResult<api.OnboardingDados | null, Error> {
  const { token } = useAuth();
  return useQuery({
    queryKey: ["onboarding"],
    queryFn: () => (token ? api.obterOnboarding(token).catch(() => null) : Promise.resolve(null)),
    enabled: Boolean(token),
  });
}

export function useSalvarOnboarding(): UseMutationResult<
  api.OnboardingDados,
  Error,
  Partial<{ interesses: string[]; localidade: string; canal_preferido: string; pular: boolean }>
> {
  const { token } = useAuth();
  const cliente = useQueryClient();
  return useMutation({
    mutationFn: (
      dados: Partial<{ interesses: string[]; localidade: string; canal_preferido: string; pular: boolean }>
    ) => api.atualizarOnboarding(token ?? "", dados),
    onSuccess: (atualizado) => {
      cliente.setQueryData(["onboarding"], atualizado);
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

export function useHistoricoPagamentos(): UseQueryResult<api.Pagamento[], Error> {
  const { token } = useAuth();
  return useQuery({
    queryKey: ["pagamentos"],
    queryFn: () => (token ? api.obterHistoricoPagamentos(token) : Promise.resolve([])),
    enabled: Boolean(token),
  });
}

export function useCancelarAssinatura(): UseMutationResult<api.Assinatura, Error, void> {
  const { token } = useAuth();
  const cliente = useQueryClient();
  return useMutation({
    mutationFn: () => api.cancelarAssinatura(token ?? ""),
    onSuccess: (atualizada) => {
      cliente.setQueryData(["minha-assinatura"], atualizada);
    },
  });
}

export function useNewsletterSalvar(): UseMutationResult<
  { tipo: api.TipoNewsletter; periodo: api.PeriodoNewsletter; ativa: boolean },
  Error,
  { tipo: api.TipoNewsletter; categorias?: string[]; periodo?: api.PeriodoNewsletter }
> {
  const { token } = useAuth();
  return useMutation({
    mutationFn: (dados: { tipo: api.TipoNewsletter; categorias?: string[]; periodo?: api.PeriodoNewsletter }) =>
      api.inscreverNewsletter(token ?? "", dados),
  });
}

export function useNewsletterCancelar(): UseMutationResult<void, Error, void> {
  const { token } = useAuth();
  return useMutation({
    mutationFn: () => api.cancelarNewsletter(token ?? ""),
  });
}

export function useListaEspera(): UseMutationResult<
  { detail: string },
  Error,
  { nome: string; email: string; interesses: string[]; localidade?: string; canal_preferido?: string; aceite_comunicacao: boolean }
> {
  return useMutation({
    mutationFn: (dados: {
      nome: string;
      email: string;
      interesses: string[];
      localidade?: string;
      canal_preferido?: string;
      aceite_comunicacao: boolean;
    }) => api.inscreverListaEspera(dados),
  });
}

export function useSolicitarCredenciamento(): UseMutationResult<
  api.SolicitacaoCredenciamento,
  Error,
  { cidade: string; uf: string; mini_bio: string; dados_profissionais: string; documento: File; telefone?: string }
> {
  const { token } = useAuth();
  return useMutation({
    mutationFn: (dados: {
      cidade: string;
      uf: string;
      mini_bio: string;
      dados_profissionais: string;
      documento: File;
      telefone?: string;
    }) => api.solicitarCredenciamento(token ?? "", dados),
  });
}

export function useMinhaSolicitacao(): UseQueryResult<api.SolicitacaoCredenciamento | null, Error> {
  const { token } = useAuth();
  return useQuery({
    queryKey: ["minha-solicitacao"],
    queryFn: () => (token ? api.obterMinhaSolicitacaoCredenciamento(token) : Promise.resolve(null)),
    enabled: Boolean(token),
  });
}

export function useMeuPerfilJornalista(): UseQueryResult<api.PerfilJornalista | null, Error> {
  const { token } = useAuth();
  return useQuery({
    queryKey: ["meu-perfil-jornalista"],
    queryFn: () => (token ? api.obterMeuPerfilJornalista(token) : Promise.resolve(null)),
    enabled: Boolean(token),
  });
}

export function useSalvarPerfilJornalista(): UseMutationResult<
  api.PerfilJornalista,
  Error,
  { mini_bio?: string; dados_profissionais?: string }
> {
  const { token } = useAuth();
  const cliente = useQueryClient();
  return useMutation({
    mutationFn: (dados: { mini_bio?: string; dados_profissionais?: string }) =>
      api.atualizarMeuPerfilJornalista(token ?? "", dados),
    onSuccess: (atualizado) => {
      cliente.setQueryData(["meu-perfil-jornalista"], atualizado);
    },
  });
}

export function usePerfilAutor(autorId: number): UseQueryResult<api.PerfilAutorPublico, Error> {
  return useQuery({
    queryKey: ["perfil-autor", autorId],
    queryFn: () => api.obterPerfilAutor(autorId),
    enabled: Number.isFinite(autorId),
  });
}

export function useSeguirAutor(
  autorId: number,
  nomeAutor: string
): UseMutationResult<void, Error, boolean> {
  const { token } = useAuth();
  const { notificar } = useToast();
  const cliente = useQueryClient();
  return useMutation({
    mutationFn: (seguindoAgora: boolean) =>
      seguindoAgora
        ? api.deixarDeSeguirAutor(token ?? "", autorId)
        : api.seguirAutor(token ?? "", autorId),
    onMutate: async (seguindoAgora: boolean) => {
      await cliente.cancelQueries({ queryKey: ["perfil-autor", autorId] });
      const anterior = cliente.getQueryData<api.PerfilAutorPublico>(["perfil-autor", autorId]);
      if (anterior) {
        cliente.setQueryData<api.PerfilAutorPublico>(["perfil-autor", autorId], {
          ...anterior,
          numero_seguidores: anterior.numero_seguidores + (seguindoAgora ? -1 : 1),
        });
      }
      return { anterior, estavaSeguindo: seguindoAgora };
    },
    onError: (_e, _v, contexto) => {
      if (contexto?.anterior) cliente.setQueryData(["perfil-autor", autorId], contexto.anterior);
      notificar("Não foi possível atualizar agora.", "erro");
    },
    onSuccess: (_d, seguindoAgora) => {
      notificar(
        seguindoAgora ? `Você deixou de seguir ${nomeAutor}.` : `Agora você segue ${nomeAutor}.`,
        seguindoAgora ? "info" : "sucesso"
      );
    },
  });
}

export function useEvolucaoRadar(): UseMutationResult<
  api.RadarEvolucao,
  Error,
  { categoria?: string; pais?: string; estado?: string; cidade?: string }
> {
  const { token } = useAuth();
  return useMutation({
    mutationFn: (params: { categoria?: string; pais?: string; estado?: string; cidade?: string }) =>
      api.obterEvolucaoRadar(token ?? "", params),
  });
}

export function useSalvarLocalidade(): UseMutationResult<
  { id: number },
  Error,
  { pais?: string; estado?: string; cidade?: string }
> {
  const { token } = useAuth();
  return useMutation({
    mutationFn: (dados: { pais?: string; estado?: string; cidade?: string }) =>
      api.salvarLocalidade(token ?? "", dados),
  });
}
