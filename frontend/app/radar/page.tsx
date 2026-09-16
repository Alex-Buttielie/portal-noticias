"use client";

import { Suspense, useMemo } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { useToast } from "@/components/ToastProvider";
import * as api from "@/lib/api";
import { useEvolucaoRadar, useLocalidadesSalvas, useRemoverLocalidade, useSalvarLocalidade, useTendenciasRadar } from "@/lib/queries";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Sparkline } from "@/components/ui/sparkline";
import { EmptyState, ErrorState, SkeletonLista } from "@/components/ui/Estados";
import { cn } from "@/lib/utils";

const formatoDataTabela = new Intl.DateTimeFormat("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric" });
const formatoNumero = new Intl.NumberFormat("pt-BR");

function ConteudoRadar() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { token, usuario } = useAuth();
  const { notificar } = useToast();

  const aba = searchParams.get("aba") === "salvas" ? "salvas" : "tendencias";
  const pais = searchParams.get("pais") ?? "";
  const estado = searchParams.get("estado") ?? "";
  const cidade = searchParams.get("cidade") ?? "";

  const filtros = useMemo(
    () => ({
      ...(pais ? { pais } : {}),
      ...(estado ? { estado } : {}),
      ...(cidade ? { cidade } : {}),
    }),
    [pais, estado, cidade]
  );

  const tendencias = useTendenciasRadar(filtros);
  const evolucaoMutacao = useEvolucaoRadar();
  const salvarMutacao = useSalvarLocalidade();
  const salvasQuery = useLocalidadesSalvas();
  const removerMutacao = useRemoverLocalidade();

  function atualizarQuery(proximos: Record<string, string | undefined>) {
    const params = new URLSearchParams(searchParams.toString());
    for (const [chave, valor] of Object.entries(proximos)) {
      if (valor) params.set(chave, valor);
      else params.delete(chave);
    }
    const qs = params.toString();
    router.replace(`/radar${qs ? `?${qs}` : ""}`, { scroll: false });
  }

  function aoFiltrar(evento: React.FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    const dados = new FormData(evento.currentTarget);
    evolucaoMutacao.reset();
    atualizarQuery({
      pais: String(dados.get("pais") || "") || undefined,
      estado: String(dados.get("estado") || "") || undefined,
      cidade: String(dados.get("cidade") || "") || undefined,
    });
  }

  async function salvarLocalidadeAtual() {
    if (!token) return;
    try {
      await salvarMutacao.mutateAsync({
        pais: pais || undefined,
        estado: estado || undefined,
        cidade: cidade || undefined,
      });
      notificar("Localidade salva — encontre-a na aba Salvas.", "sucesso");
    } catch {
      notificar("Não foi possível salvar a localidade.", "erro");
    }
  }

  async function removerLocalidadeSalva(local: { pais?: string; estado?: string; cidade?: string }) {
    const rotulo = [local.cidade, local.estado, local.pais].filter(Boolean).join(" · ") || "esta localidade";
    if (!window.confirm(`Remover ${rotulo} das suas localidades?`)) return;
    try {
      await removerMutacao.mutateAsync(local);
      notificar("Localidade removida.", "info");
    } catch {
      notificar("Não foi possível remover a localidade.", "erro");
    }
  }

  const dados = tendencias.data ?? null;
  const evolucao = evolucaoMutacao.data ?? null;
  const salvas = salvasQuery.data ?? [];
  const serieValores = (evolucao?.serie ?? []).map((p) => p.numero_noticias);

  return (
    <div className="min-w-0 w-full max-w-full space-y-6 overflow-hidden">
      <header className="min-w-0 space-y-2 overflow-hidden">
        <p className="text-xs font-bold uppercase tracking-[0.14em] text-[var(--cor-primaria)]">Radar</p>
        <h1 className="break-words font-[var(--fonte-titulo)] text-3xl font-extrabold tracking-tight text-wrap-balance">
          Radar de tendências
        </h1>
        <p className="max-w-[62ch] break-words text-sm text-[var(--cor-texto-suave)]">
          Descubra quais assuntos estão em alta na sua região — filtros e abas ficam salvos no link para você compartilhar.
        </p>
      </header>

      <Tabs
        value={aba}
        onValueChange={(v) => atualizarQuery({ aba: v === "salvas" ? "salvas" : undefined })}
        className="min-w-0"
      >
        <TabsList aria-label="Seções do radar">
          <TabsTrigger value="tendencias">Tendências</TabsTrigger>
          <TabsTrigger value="salvas">Suas localidades{token && salvas.length > 0 ? ` (${salvas.length})` : ""}</TabsTrigger>
        </TabsList>

        <TabsContent value="tendencias" className="min-w-0 space-y-6">
          <Card className="min-w-0 overflow-hidden">
            <CardContent className="pt-6">
              <form onSubmit={aoFiltrar} className="flex min-w-0 flex-wrap items-end gap-3">
                <div className="min-w-0 flex-1 basis-[140px] space-y-2">
                  <Label htmlFor="radar-pais">País</Label>
                  <Input id="radar-pais" name="pais" key={`pais-${pais}`} defaultValue={pais} placeholder="Ex.: Brasil…" autoComplete="country-name" className="text-[16px] sm:text-sm" />
                </div>
                <div className="min-w-0 flex-1 basis-[140px] space-y-2">
                  <Label htmlFor="radar-estado">Estado</Label>
                  <Input id="radar-estado" name="estado" key={`estado-${estado}`} defaultValue={estado} placeholder="Ex.: SP…" autoComplete="address-level1" className="text-[16px] sm:text-sm" />
                </div>
                <div className="min-w-0 flex-1 basis-[140px] space-y-2">
                  <Label htmlFor="radar-cidade">Cidade</Label>
                  <Input id="radar-cidade" name="cidade" key={`cidade-${cidade}`} defaultValue={cidade} placeholder="Ex.: São Paulo…" autoComplete="address-level2" className="text-[16px] sm:text-sm" />
                </div>
                <Button type="submit" className="shrink-0">Filtrar</Button>
                {token && (
                  <Button type="button" variante="secundaria" onClick={() => void salvarLocalidadeAtual()} loading={salvarMutacao.isPending} className="shrink-0">
                    Salvar localidade
                  </Button>
                )}
              </form>
            </CardContent>
          </Card>

          <div aria-live="polite" aria-busy={tendencias.isLoading || undefined} className="min-w-0">
            {tendencias.isLoading && <SkeletonLista quantidade={3} />}
            {tendencias.isError && (
              <ErrorState
                mensagem="Não foi possível carregar o radar."
                aoTentarNovamente={() => void tendencias.refetch()}
              />
            )}
          </div>

          {dados && (
            <section className="min-w-0 space-y-4 overflow-hidden" aria-label="Assuntos em alta">
              <div className="flex min-w-0 items-baseline gap-3 border-b-2 border-[var(--cor-borda)] pb-3">
                <h2 className="break-words font-[var(--fonte-titulo)] text-xl font-extrabold tracking-tight text-wrap-balance">
                  Assuntos em alta
                </h2>
              </div>
              <p className="break-words text-sm italic text-[var(--cor-texto-suave)]">
                {dados.aviso_metodologia}
              </p>
              {dados.assuntos_em_alta.length === 0 && (
                <EmptyState titulo="Sem assuntos em alta" descricao="Nenhum assunto em alta neste recorte ainda." />
              )}
              <div className={cn("grid w-full max-w-full grid-cols-1 gap-4 overflow-hidden break-words sm:grid-cols-2 lg:grid-cols-3")}>
                {dados.assuntos_em_alta.map((assunto) => (
                  <Card key={assunto.categoria} className="flex min-w-0 flex-col overflow-hidden break-words">
                    <CardHeader className="min-w-0 pb-2">
                      <Badge variant="secondary" className="min-h-0 self-start">
                        {assunto.categoria}
                      </Badge>
                      <CardTitle className="break-words text-lg">
                        {formatoNumero.format(assunto.numero_noticias)}{" "}
                        {assunto.numero_noticias === 1 ? "notícia" : "notícias"}
                      </CardTitle>
                      <CardDescription className="break-words">
                        {formatoNumero.format(assunto.numero_fontes)}{" "}
                        {assunto.numero_fontes === 1 ? "fonte" : "fontes"} confirmando
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="mt-auto min-w-0 space-y-3">
                      {assunto.cluster_id ? (
                        <Link href={`/noticia/cluster/${assunto.cluster_id}`} className="break-words font-medium text-[var(--cor-primaria)] hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]">
                          Ver acontecimento agrupado
                        </Link>
                      ) : assunto.item_id ? (
                        <Link href={`/noticia/item/${assunto.item_id}`} className="break-words font-medium text-[var(--cor-primaria)] hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]">
                          Ver notícia
                        </Link>
                      ) : null}
                      {usuario?.papel === "premium" ? (
                        <Button
                          variante="secundaria"
                          tamanho="pequeno"
                          loading={evolucaoMutacao.isPending}
                          onClick={() =>
                            evolucaoMutacao.mutate({
                              categoria: assunto.categoria,
                              pais: pais || undefined,
                              estado: estado || undefined,
                              cidade: cidade || undefined,
                            })
                          }
                        >
                          Ver evolução
                        </Button>
                      ) : (
                        <p className="break-words text-xs text-[var(--cor-texto-suave)]">
                          A evolução ao longo do tempo é um recurso Premium —{" "}
                          <Link href="/planos" className="font-medium text-[var(--cor-primaria)] hover:underline">
                            assine Premium
                          </Link>
                          .
                        </p>
                      )}
                    </CardContent>
                  </Card>
                ))}
              </div>
            </section>
          )}

          {evolucaoMutacao.isError && (
            <ErrorState
              mensagem={
                evolucaoMutacao.error instanceof api.ApiError
                  ? evolucaoMutacao.error.message
                  : "Não foi possível carregar a evolução."
              }
            />
          )}
          {evolucao && (
            <section className="min-w-0 space-y-3 overflow-hidden" aria-label="Evolução do assunto">
              <Card className="min-w-0 overflow-hidden">
                <CardHeader className="min-w-0">
                  <CardTitle className="break-words text-wrap-balance">Evolução — {evolucao.categoria}</CardTitle>
                  <CardDescription className="break-words">{evolucao.aviso_metodologia}</CardDescription>
                </CardHeader>
                <CardContent className="min-w-0 space-y-4 overflow-hidden">
                  {serieValores.length > 1 ? (
                    <div className="min-w-0 overflow-x-auto">
                      <Sparkline data={serieValores} width={560} height={96} className="min-h-[96px] w-full" />
                      <span className="sr-only">
                        {evolucao.serie.map((p) => `${p.dia}: ${p.numero_noticias} notícias`).join("; ")}
                      </span>
                    </div>
                  ) : (
                    <p className="break-words text-sm text-[var(--cor-texto-suave)]">
                      Ainda há poucos pontos para desenhar o gráfico — veja a tabela abaixo.
                    </p>
                  )}
                  <ul className="min-w-0 space-y-1 text-sm">
                    {evolucao.serie.map((ponto) => {
                      const d = new Date(ponto.dia);
                      const diaFmt = Number.isNaN(d.getTime()) ? ponto.dia : formatoDataTabela.format(d);
                      return (
                        <li key={ponto.dia} className="flex min-w-0 items-baseline justify-between gap-2 tabular-nums">
                          <time dateTime={ponto.dia} className="min-w-0 break-words text-[var(--cor-texto-suave)]">{diaFmt}</time>
                          <span className="shrink-0">{formatoNumero.format(ponto.numero_noticias)} {ponto.numero_noticias === 1 ? "notícia" : "notícias"}</span>
                        </li>
                      );
                    })}
                  </ul>
                </CardContent>
              </Card>
            </section>
          )}
        </TabsContent>

        <TabsContent value="salvas" className="min-w-0 space-y-4">
          {!token ? (
            <EmptyState
              titulo="Entre para salvar localidades"
              descricao="Suas localidades ficam vinculadas à sua conta e aparecem aqui."
            />
          ) : salvasQuery.isLoading ? (
            <SkeletonLista quantidade={2} />
          ) : salvasQuery.isError ? (
            <ErrorState
              mensagem="Não foi possível carregar suas localidades."
              aoTentarNovamente={() => void salvasQuery.refetch()}
            />
          ) : salvas.length === 0 ? (
            <EmptyState
              titulo="Nenhuma localidade salva"
              descricao="Filtre por uma região na aba Tendências e toque em Salvar localidade."
            />
          ) : (
            <ul className="flex min-w-0 flex-col gap-2" aria-live="polite">
              {salvas.map((loc, i) => {
                const rotulo = [loc.cidade, loc.estado, loc.pais].filter(Boolean).join(" · ") || "Localidade";
                return (
                  <li key={`${loc.pais}-${loc.estado}-${loc.cidade}-${i}`} className="min-w-0">
                    <Card className="flex min-w-0 flex-wrap items-center gap-2 p-3">
                      <Button
                        variante="fantasma"
                        tamanho="pequeno"
                        className="min-w-0"
                        onClick={() => {
                          atualizarQuery({
                            aba: undefined,
                            pais: loc.pais || undefined,
                            estado: loc.estado || undefined,
                            cidade: loc.cidade || undefined,
                          });
                        }}
                      >
                        <span className="min-w-0 truncate">{rotulo}</span>
                      </Button>
                      <Button
                        variante="fantasma"
                        tamanho="pequeno"
                        loading={removerMutacao.isPending}
                        onClick={() => void removerLocalidadeSalva({ pais: loc.pais || undefined, estado: loc.estado || undefined, cidade: loc.cidade || undefined })}
                        aria-label={`Remover ${rotulo}`}
                        className="ml-auto shrink-0"
                      >
                        Remover
                      </Button>
                    </Card>
                  </li>
                );
              })}
            </ul>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}

export default function PaginaRadar() {
  return (
    <Suspense fallback={<SkeletonLista quantidade={3} />}>
      <ConteudoRadar />
    </Suspense>
  );
}
