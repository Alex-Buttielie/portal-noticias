"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { useToast } from "@/components/ToastProvider";
import * as api from "@/lib/api";
import { useEvolucaoRadar, useLocalidadesSalvas, useRemoverLocalidade, useSalvarLocalidade, useTendenciasRadar } from "@/lib/queries";
import Badge from "@/components/Badge";
import { Button } from "@/components/ui/Button";
import { CampoTexto } from "@/components/ui/FormField";
import { EmptyState, ErrorState, SkeletonLista } from "@/components/ui/Estados";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Cards";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/Data";
import { cn } from "@/lib/utils";

const formatoDataTabela = new Intl.DateTimeFormat("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric" });

export default function PaginaRadar() {
  const { token, usuario } = useAuth();
  const { notificar } = useToast();

  const [pais, setPais] = useState("");
  const [estado, setEstado] = useState("");
  const [cidade, setCidade] = useState("");
  const [filtros, setFiltros] = useState<{ pais?: string; estado?: string; cidade?: string }>({});
  const [salvo, setSalvo] = useState(false);

  const tendencias = useTendenciasRadar(filtros);
  const evolucaoMutacao = useEvolucaoRadar();
  const salvarMutacao = useSalvarLocalidade();
  const salvasQuery = useLocalidadesSalvas();
  const removerMutacao = useRemoverLocalidade();

  function aoSubmeter(evento: FormEvent) {
    evento.preventDefault();
    setSalvo(false);
    evolucaoMutacao.reset();
    setFiltros({ pais: pais || undefined, estado: estado || undefined, cidade: cidade || undefined });
  }

  async function salvarLocalidadeAtual() {
    if (!token) return;
    try {
      await salvarMutacao.mutateAsync({ pais: pais || undefined, estado: estado || undefined, cidade: cidade || undefined });
      setSalvo(true);
      notificar("Localidade salva.", "sucesso");
    } catch {
      // falha ao salvar não deve travar a navegação do radar
    }
  }

  async function removerLocalidadeSalva(local: { pais?: string; estado?: string; cidade?: string }) {
    if (!window.confirm("Remover esta localidade salva?")) return;
    try {
      await removerMutacao.mutateAsync(local);
    } catch {
      notificar("Não foi possível remover a localidade.", "erro");
    }
  }

  const dados = tendencias.data ?? null;
  const evolucao = evolucaoMutacao.data ?? null;
  const salvas = salvasQuery.data ?? [];

  return (
<div className="min-w-0 w-full max-w-full space-y-6 overflow-hidden">
      <header className={cn("seu-rio", "min-w-0 space-y-2 overflow-hidden")}>
        <p className="text-xs font-bold uppercase tracking-[0.14em] text-[var(--cor-primaria)] secao-eyebrow">Radar</p>
        <h1 className="font-[var(--fonte-titulo)] text-3xl font-extrabold tracking-[-0.03em] text-wrap-balance seu-rio__titulo">Radar de Tendências</h1>
        <p className="max-w-[62ch] text-sm text-[var(--cor-texto-suave)] texto-suave">Assuntos em alta por localidade — os filtros ficam nesta página, sem mudar a URL.</p>
      </header>

      <Card className="min-w-0 overflow-hidden">
        <CardContent className="pt-6">
          <form onSubmit={aoSubmeter} className="flex min-w-0 flex-wrap items-end gap-3 controles-feed">
            <div className="min-w-0 flex-1 basis-[140px]">
              <CampoTexto id="radar-pais" rotulo="País" value={pais} onChange={(e) => setPais(e.target.value)} placeholder="Ex: Brasil…" autoComplete="country-name" />
            </div>
            <div className="min-w-0 flex-1 basis-[140px]">
              <CampoTexto id="radar-estado" rotulo="Estado" value={estado} onChange={(e) => setEstado(e.target.value)} placeholder="Ex: SP…" autoComplete="address-level1" />
            </div>
            <div className="min-w-0 flex-1 basis-[140px]">
              <CampoTexto id="radar-cidade" rotulo="Cidade" value={cidade} onChange={(e) => setCidade(e.target.value)} placeholder="Ex: São Paulo…" autoComplete="address-level2" />
            </div>
            <Button type="submit" className="shrink-0">Filtrar</Button>
            {token && (
              <Button type="button" variante="secundaria" onClick={() => void salvarLocalidadeAtual()} carregando={salvarMutacao.isPending} className="shrink-0">
                {salvo ? "Localidade salva ✓" : "Salvar localidade"}
              </Button>
            )}
          </form>
        </CardContent>
      </Card>

      <div aria-live="polite" aria-busy={tendencias.isLoading || undefined}>
        {tendencias.isLoading && <SkeletonLista quantidade={3} />}
        {tendencias.isError && (
          <ErrorState
            mensagem="Não foi possível carregar o radar."
            aoTentarNovamente={() => void tendencias.refetch()}
          />
        )}
      </div>

      {dados && (
<section className="min-w-0 space-y-4 overflow-hidden secao-bloco" aria-label="Assuntos em alta">
          <div className="flex items-baseline gap-3 border-b-2 border-[var(--cor-borda)] pb-3 secao-cabecalho">
            <h2 className="font-[var(--fonte-titulo)] text-xl font-extrabold tracking-tight secao-titulo">Assuntos em alta</h2>
          </div>
          <p className="break-words text-sm italic text-[var(--cor-texto-suave)] texto-suave">
            {dados.aviso_metodologia}
          </p>
          {dados.assuntos_em_alta.length === 0 && (
            <EmptyState titulo="Sem assuntos em alta" descricao="Nenhum assunto em alta neste recorte ainda." />
          )}
<div className={cn("grade-noticias", "grid w-full max-w-full grid-cols-1 gap-4 overflow-hidden break-words sm:grid-cols-2 lg:grid-cols-3")}>
            {dados.assuntos_em_alta.map((assunto) => (
              <Card key={assunto.categoria} className="flex min-w-0 flex-col overflow-hidden break-words p-4 cartao-meta">
                <div className="mb-3 flex flex-wrap items-center gap-2 text-xs text-[var(--cor-texto-suave)] cartao">
                  <Badge variante="neutro">{assunto.categoria}</Badge>
                  <span>{assunto.numero_noticias.toLocaleString("pt-BR")} notícia(s)</span>
                  <span>{assunto.numero_fontes.toLocaleString("pt-BR")} fonte(s)</span>
                </div>
                {assunto.cluster_id ? (
                  <Link href={`/noticia/cluster/${assunto.cluster_id}`} className="break-words font-medium text-[var(--cor-primaria)] hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]">Ver acontecimento agrupado</Link>
                ) : assunto.item_id ? (
                  <Link href={`/noticia/item/${assunto.item_id}`} className="break-words font-medium text-[var(--cor-primaria)] hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]">Ver notícia</Link>
                ) : null}
                {usuario?.papel === "premium" ? (
                  <div className="mt-3">
                    <Button
                      variante="secundaria"
                      tamanho="pequeno"
                      carregando={evolucaoMutacao.isPending}
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
                  </div>
                ) : (
                  <p className="mt-3 break-words text-xs text-[var(--cor-texto-suave)]">Evolução ao longo do tempo é um recurso Premium.</p>
                )}
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
      {token && salvas.length > 0 && (
<section className="space-y-3 secao-bloco secao-titulo" aria-label="Localidades salvas">
          <div className="flex items-baseline gap-3 border-b-2 border-[var(--cor-borda)] pb-3 secao-cabecalho">
            <h2 className="font-[var(--fonte-titulo)] text-xl font-extrabold tracking-tight">Localidades salvas</h2>
          </div>
          <ul className="flex flex-col gap-2">
            {salvas.map((loc, i) => {
              const rotulo = [loc.cidade, loc.estado, loc.pais].filter(Boolean).join(" · ") || "Localidade";
              return (
                <li key={`${loc.pais}-${loc.estado}-${loc.cidade}-${i}`} className="flex flex-wrap items-center gap-2 rounded-lg border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] px-3 py-2">
                  <Button
                    variante="fantasma"
                    tamanho="pequeno"
                    onClick={() => {
                      setPais(loc.pais ?? "");
                      setEstado(loc.estado ?? "");
                      setCidade(loc.cidade ?? "");
                      setFiltros({ pais: loc.pais || undefined, estado: loc.estado || undefined, cidade: loc.cidade || undefined });
                    }}
                  >
                    {rotulo}
                  </Button>
                  <Button
                    variante="fantasma"
                    tamanho="pequeno"
                    carregando={removerMutacao.isPending}
                    onClick={() => void removerLocalidadeSalva({ pais: loc.pais || undefined, estado: loc.estado || undefined, cidade: loc.cidade || undefined })}
                    aria-label={`Remover ${rotulo}`}
                  >
                    Remover
                  </Button>
                </li>
              );
            })}
          </ul>
        </section>
      )}
      {evolucao && (
<section className="min-w-0 space-y-3 overflow-hidden secao-bloco cartao cartao-titulo tabela-wrapper" aria-label="Evolução do assunto">
          <Card className="min-w-0 overflow-hidden">
            <CardHeader>
              <CardTitle className="break-words">Evolução — {evolucao.categoria}</CardTitle>
            </CardHeader>
            <CardContent className="min-w-0 overflow-hidden">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead scope="col">Dia</TableHead>
                    <TableHead scope="col">Notícias</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {evolucao.serie.map((ponto) => {
                    const d = new Date(ponto.dia);
                    const diaFmt = Number.isNaN(d.getTime()) ? ponto.dia : formatoDataTabela.format(d);
                    return (
                      <TableRow key={ponto.dia}>
                        <TableCell>
                          <time dateTime={ponto.dia}>{diaFmt}</time>
                        </TableCell>
                        <TableCell>{ponto.numero_noticias.toLocaleString("pt-BR")} notícia(s)</TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </section>
      )}
    </div>
  );
}
