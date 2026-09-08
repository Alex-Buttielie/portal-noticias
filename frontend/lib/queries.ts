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

export function useFeed(filtro: FiltroFeed & { enabled?: boolean }) {
  const { enabled = true, categoria, busca } = filtro;
  return useInfiniteQuery({
    queryKey: ["feed", categoria ?? "", busca ?? ""],
    queryFn: ({ pageParam }) =>
      api.obterFeed({ categoria, busca, page: pageParam as number }),
    initialPageParam: 1,
    getNextPageParam: (ultima, paginas) => (ultima.next ? paginas.length + 1 : undefined),
    enabled,
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

export function usePublicacoes(params: { destaque?: boolean; autor?: number; enabled?: boolean } = {}): UseQueryResult<api.Publicacao[], Error> {
  const { destaque, autor, enabled = true } = params;
  return useQuery({
    queryKey: ["publicacoes", destaque ?? null, autor ?? null],
    queryFn: () => api.obterPublicacoes({ destaque, autor }),
    enabled,
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

type ItensMonitorados = Record<string, { criterio: { tipo: string; valor: string }; itens: api.ItemMonitorado[] }>;

function chavesB2B(): string[][] {
  return [["b2b-criterios"], ["b2b-itens"], ["b2b-resumo"], ["b2b-membros"]];
}

export function usePainelB2B(): {
  criterios: UseQueryResult<api.CriterioMonitoramento[], Error>;
  itens: UseQueryResult<ItensMonitorados, Error>;
  resumo: UseQueryResult<api.ResumoExecutivo, Error>;
  membros: UseQueryResult<api.MembroOrganizacao[], Error>;
  recarregar: () => void;
} {
  const { token } = useAuth();
  const cliente = useQueryClient();
  const enabled = Boolean(token);
  const criterios = useQuery({
    queryKey: ["b2b-criterios"],
    queryFn: () => api.obterCriteriosB2B(token ?? ""),
    enabled,
  });
  const itens = useQuery({
    queryKey: ["b2b-itens"],
    queryFn: () => api.obterItensMonitoradosB2B(token ?? ""),
    enabled,
  });
  const resumo = useQuery({
    queryKey: ["b2b-resumo"],
    queryFn: () => api.obterResumoExecutivoB2B(token ?? ""),
    enabled,
  });
  const membros = useQuery({
    queryKey: ["b2b-membros"],
    queryFn: () => api.obterMembrosB2B(token ?? ""),
    enabled,
  });
  return {
    criterios,
    itens,
    resumo,
    membros,
    recarregar: () => {
      for (const key of chavesB2B()) void cliente.invalidateQueries({ queryKey: key });
    },
  };
}

export function useCriarCriterioB2B(recarregar: () => void): UseMutationResult<
  api.CriterioMonitoramento,
  Error,
  { tipo: api.TipoCriterioMonitoramento; valor: string }
> {
  const { token } = useAuth();
  return useMutation({
    mutationFn: (dados: { tipo: api.TipoCriterioMonitoramento; valor: string }) =>
      api.criarCriterioB2B(token ?? "", dados),
    onSuccess: () => recarregar(),
  });
}

export function useConvidarMembroB2B(recarregar: () => void): UseMutationResult<api.MembroOrganizacao, Error, string> {
  const { token } = useAuth();
  return useMutation({
    mutationFn: (email: string) => api.convidarMembroB2B(token ?? "", email),
    onSuccess: () => recarregar(),
  });
}

export function useRemoverMembroB2B(recarregar: () => void): UseMutationResult<void, Error, string> {
  const { token } = useAuth();
  return useMutation({
    mutationFn: (email: string) => api.removerMembroB2B(token ?? "", email),
    onSuccess: () => recarregar(),
  });
}

export type LimiteAdmin = { id: number; chave: string; plano: string; valor: string; descricao: string };
export type DenunciaAdmin = {
  id: number;
  motivo: string;
  detalhe: string;
  status: string;
  denunciante_email: string;
  criado_em: string;
  alvo_repr: string | null;
};

export function useAdminUsuarios(params: { search?: string; papel?: string; page?: number }): UseQueryResult<api.Paginated<api.AdminUsuario>, Error> {
  const { token } = useAuth();
  return useQuery({
    queryKey: ["admin-usuarios", params.search ?? "", params.papel ?? "", params.page ?? 1],
    queryFn: () => api.adminListarUsuarios(token ?? "", params),
    enabled: Boolean(token),
  });
}

export function useAdminAtualizarUsuario(): UseMutationResult<api.AdminUsuario, Error, { id: number; dados: { papel?: string; is_active?: boolean } }> {
  const { token } = useAuth();
  const cliente = useQueryClient();
  return useMutation({
    mutationFn: ({ id, dados }: { id: number; dados: { papel?: string; is_active?: boolean } }) =>
      api.adminAtualizarUsuario(token ?? "", id, dados),
    onSuccess: () => {
      void cliente.invalidateQueries({ queryKey: ["admin-usuarios"] });
    },
  });
}

export function useAdminFila(params: { status?: string; page?: number }): UseQueryResult<api.Paginated<api.AdminFilaItem>, Error> {
  const { token } = useAuth();
  return useQuery({
    queryKey: ["admin-fila", params.status ?? "", params.page ?? 1],
    queryFn: () => api.adminListarFila(token ?? "", params),
    enabled: Boolean(token),
  });
}

export function useAdminDecidirFila(): UseMutationResult<{ detail: string }, Error, { id: number; acao: "aprovar" | "rejeitar" }> {
  const { token } = useAuth();
  const cliente = useQueryClient();
  return useMutation({
    mutationFn: ({ id, acao }: { id: number; acao: "aprovar" | "rejeitar" }) =>
      api.adminDecidirFila(token ?? "", id, acao),
    onSuccess: () => {
      void cliente.invalidateQueries({ queryKey: ["admin-fila"] });
    },
  });
}

export function useAdminPlanos(): UseQueryResult<api.Plano[], Error> {
  const { token } = useAuth();
  return useQuery({
    queryKey: ["admin-planos"],
    queryFn: async () => {
      const r = await api.adminListarPlanos(token ?? "");
      return (r as unknown as { results?: api.Plano[] }).results ?? (r as unknown as api.Plano[]);
    },
    enabled: Boolean(token),
  });
}

export function useAdminLimites(): UseQueryResult<LimiteAdmin[], Error> {
  const { token } = useAuth();
  return useQuery({
    queryKey: ["admin-limites"],
    queryFn: async () => {
      const r = await api.adminListarLimites(token ?? "");
      return (r as unknown as { results?: LimiteAdmin[] }).results ?? (r as unknown as LimiteAdmin[]);
    },
    enabled: Boolean(token),
  });
}

export function useAdminSalvarPlano(): UseMutationResult<api.Plano, Error, { nome: string; preco: string; duracao_dias: number }> {
  const { token } = useAuth();
  const cliente = useQueryClient();
  return useMutation({
    mutationFn: (dados: { nome: string; preco: string; duracao_dias: number }) =>
      api.adminCriarPlano(token ?? "", dados),
    onSuccess: () => {
      void cliente.invalidateQueries({ queryKey: ["admin-planos"] });
    },
  });
}

export function useAdminAlternarPlano(): UseMutationResult<api.Plano, Error, { id: number; ativo: boolean }> {
  const { token } = useAuth();
  const cliente = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ativo }: { id: number; ativo: boolean }) =>
      api.adminAtualizarPlano(token ?? "", id, { ativo }),
    onSuccess: () => {
      void cliente.invalidateQueries({ queryKey: ["admin-planos"] });
    },
  });
}

export function useAdminSalvarLimite(): UseMutationResult<{ id: number; chave: string; plano: string; valor: string }, Error, { id: number; valor: string }> {
  const { token } = useAuth();
  const cliente = useQueryClient();
  return useMutation({
    mutationFn: ({ id, valor }: { id: number; valor: string }) =>
      api.adminAtualizarLimite(token ?? "", id, { valor }),
    onSuccess: () => {
      void cliente.invalidateQueries({ queryKey: ["admin-limites"] });
    },
  });
}

export function useAdminAssinaturas(params: { status?: string; search?: string; page?: number }): UseQueryResult<api.Paginated<api.AdminAssinatura>, Error> {
  const { token } = useAuth();
  return useQuery({
    queryKey: ["admin-assinaturas", params.status ?? "", params.search ?? "", params.page ?? 1],
    queryFn: () => api.adminListarAssinaturas(token ?? "", params),
    enabled: Boolean(token),
  });
}

export function useAdminDenuncias(params: { status?: string; page?: number }): UseQueryResult<api.Paginated<DenunciaAdmin>, Error> {
  const { token } = useAuth();
  return useQuery({
    queryKey: ["admin-denuncias", params.status ?? "", params.page ?? 1],
    queryFn: () => api.adminListarDenuncias(token ?? "", params),
    enabled: Boolean(token),
  });
}

export function useAdminAcaoDenuncia(): UseMutationResult<{ detail: string }, Error, { id: number; tipo: string; motivo: string; procedente?: boolean }> {
  const { token } = useAuth();
  const cliente = useQueryClient();
  return useMutation({
    mutationFn: ({ id, tipo, motivo, procedente }: { id: number; tipo: string; motivo: string; procedente?: boolean }) =>
      api.adminAplicarAcaoDenuncia(token ?? "", id, { tipo, motivo, procedente }),
    onSuccess: () => {
      void cliente.invalidateQueries({ queryKey: ["admin-denuncias"] });
    },
  });
}

export function usePainelMetricas(dias: number): UseQueryResult<api.PainelMetricas, Error> {
  const { token } = useAuth();
  return useQuery({
    queryKey: ["metricas", dias],
    queryFn: () => api.obterPainelMetricas(token ?? "", dias),
    enabled: Boolean(token),
  });
}

export function useRobosFontes(): UseQueryResult<api.FonteRobo[], Error> {
  const { token } = useAuth();
  return useQuery({
    queryKey: ["robos-fontes"],
    queryFn: () => api.robosListarFontes(token ?? ""),
    enabled: Boolean(token),
  });
}

export function useRobosConfig(): UseQueryResult<api.ConfigRobo, Error> {
  const { token } = useAuth();
  return useQuery({
    queryKey: ["robos-config"],
    queryFn: () => api.robosObterConfig(token ?? ""),
    enabled: Boolean(token),
  });
}

export function useRobosExecucoes(): UseQueryResult<api.ExecucaoRobo[], Error> {
  const { token } = useAuth();
  return useQuery({
    queryKey: ["robos-execucoes"],
    queryFn: () => api.robosListarExecucoes(token ?? ""),
    enabled: Boolean(token),
  });
}

export function useRobosMutacao(): UseMutationResult<unknown, Error, () => Promise<unknown>> {
  const cliente = useQueryClient();
  return useMutation({
    mutationFn: (acao: () => Promise<unknown>) => acao(),
    onSuccess: () => {
      void cliente.invalidateQueries({ queryKey: ["robos-fontes"] });
      void cliente.invalidateQueries({ queryKey: ["robos-config"] });
      void cliente.invalidateQueries({ queryKey: ["robos-execucoes"] });
    },
  });
}

function useInvalidarRobos() {
  const cliente = useQueryClient();
  return () => {
    void cliente.invalidateQueries({ queryKey: ["robos-fontes"] });
    void cliente.invalidateQueries({ queryKey: ["robos-config"] });
    void cliente.invalidateQueries({ queryKey: ["robos-execucoes"] });
  };
}

export function useRobosCriarFonte(): UseMutationResult<api.FonteRobo, Error, { nome: string; url: string; ativo?: boolean; categoria_padrao?: string }> {
  const { token } = useAuth();
  const invalidar = useInvalidarRobos();
  return useMutation({
    mutationFn: (dados: { nome: string; url: string; ativo?: boolean; categoria_padrao?: string }) =>
      api.robosCriarFonte(token ?? "", dados),
    onSuccess: () => invalidar(),
  });
}

export function useRobosSalvarFonte(): UseMutationResult<api.FonteRobo, Error, { id: number; dados: Partial<api.FonteRobo> }> {
  const { token } = useAuth();
  const invalidar = useInvalidarRobos();
  return useMutation({
    mutationFn: ({ id, dados }: { id: number; dados: Partial<api.FonteRobo> }) =>
      api.robosAtualizarFonte(token ?? "", id, dados),
    onSuccess: () => invalidar(),
  });
}

export function useRobosRemoverFonte(): UseMutationResult<void, Error, number> {
  const { token } = useAuth();
  const invalidar = useInvalidarRobos();
  return useMutation({
    mutationFn: (id: number) => api.robosRemoverFonte(token ?? "", id),
    onSuccess: () => invalidar(),
  });
}

export function useRobosSalvarConfig(): UseMutationResult<api.ConfigRobo, Error, Partial<api.ConfigRobo>> {
  const { token } = useAuth();
  const invalidar = useInvalidarRobos();
  return useMutation({
    mutationFn: (dados: Partial<api.ConfigRobo>) => api.robosSalvarConfig(token ?? "", dados),
    onSuccess: () => invalidar(),
  });
}

export function useRobosExecutar(): UseMutationResult<api.ExecucaoRobo, Error, void> {
  const { token } = useAuth();
  const cliente = useQueryClient();
  return useMutation({
    mutationFn: () => api.robosExecutar(token ?? ""),
    onSuccess: () => {
      void cliente.invalidateQueries({ queryKey: ["robos-execucoes"] });
    },
  });
}
