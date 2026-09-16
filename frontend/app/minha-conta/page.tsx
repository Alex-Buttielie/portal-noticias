"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { useToast } from "@/components/ToastProvider";
import * as api from "@/lib/api";
import {
  useCancelarAssinatura,
  useHistoricoPagamentos,
  useMinhaAssinatura,
  useNewsletterCancelar,
  useNewsletterSalvar,
} from "@/lib/queries";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { CampoSelecao, CampoTexto } from "@/components/ui/FormField";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { DataTable } from "@/components/ui/Data";
import { EmptyState, ErrorState, SkeletonLista } from "@/components/ui/Estados";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

const ROTULOS_STATUS: Record<api.StatusAssinatura, string> = {
  teste: "Em teste",
  ativa: "Ativa",
  pagamento_pendente: "Pagamento pendente",
  inadimplente: "Pagamento em atraso",
  cancelada: "Cancelada (acesso mantido até o vencimento)",
  expirada: "Expirada",
  encerrada: "Encerrada",
};

const VARIANTE_STATUS: Record<api.StatusAssinatura, "default" | "secondary" | "destructive" | "outline" | "success" | "warning"> = {
  teste: "secondary",
  ativa: "success",
  pagamento_pendente: "warning",
  inadimplente: "destructive",
  cancelada: "outline",
  expirada: "outline",
  encerrada: "outline",
};

const VARIANTE_PAGAMENTO: Record<api.Pagamento["status"], "default" | "secondary" | "destructive" | "outline" | "success" | "warning"> = {
  aprovado: "success",
  recusado: "destructive",
  pendente: "warning",
  estornado: "secondary",
};

function formatarData(data: string | null): string {
  if (!data) return "—";
  const d = new Date(data);
  if (Number.isNaN(d.getTime())) return data;
  return new Intl.DateTimeFormat("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric" }).format(d);
}

function formatarPreco(preco: string): string {
  const numero = Number(preco);
  if (Number.isNaN(numero)) return preco;
  return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(numero);
}

type Aba = "assinatura" | "pagamentos" | "perfil";

export default function PaginaMinhaConta() {
  const router = useRouter();
  const { token, usuario, carregando: carregandoAuth } = useAuth();
  const { notificar } = useToast();
  const assinaturaQuery = useMinhaAssinatura();
  const pagamentosQuery = useHistoricoPagamentos();
  const cancelarMutacao = useCancelarAssinatura();
  const newsletterSalvar = useNewsletterSalvar();
  const newsletterCancelar = useNewsletterCancelar();

  const [aba, setAba] = useState<Aba>("assinatura");
  const [dialogoAberto, setDialogoAberto] = useState(false);
  const [avisoCancelada, setAvisoCancelada] = useState(false);
  const [ordemPagamentos, setOrdemPagamentos] = useState<"recentes" | "antigos">("recentes");
  const [tipoNewsletter, setTipoNewsletter] = useState<api.TipoNewsletter>("padrao");
  const [periodoNewsletter, setPeriodoNewsletter] = useState<api.PeriodoNewsletter>("manha");
  const [categoriasNewsletter, setCategoriasNewsletter] = useState("");
  const [newsletterAtiva, setNewsletterAtiva] = useState<boolean | null>(null);

  useEffect(() => {
    if (!carregandoAuth && !token) {
      router.push("/login");
    }
  }, [carregandoAuth, token, router]);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const abaUrl = params.get("aba");
    if (abaUrl === "pagamentos" || abaUrl === "perfil" || abaUrl === "assinatura") {
      setAba(abaUrl);
    }
  }, []);

  function trocarAba(nova: Aba) {
    setAba(nova);
    const params = new URLSearchParams(window.location.search);
    params.set("aba", nova);
    window.history.replaceState({}, "", `${window.location.pathname}?${params.toString()}`);
  }

  const pagamentosOrdenados = useMemo(() => {
    const lista = [...(pagamentosQuery.data ?? [])];
    lista.sort((a, b) => {
      const ta = new Date(a.criado_em).getTime();
      const tb = new Date(b.criado_em).getTime();
      return ordemPagamentos === "recentes" ? tb - ta : ta - tb;
    });
    return lista;
  }, [pagamentosQuery.data, ordemPagamentos]);

  if (carregandoAuth) {
    return (
      <div className="mx-auto w-full max-w-4xl px-4 py-10">
        <p className="text-sm text-[var(--cor-texto-suave)]">Carregando…</p>
      </div>
    );
  }

  const assinatura = assinaturaQuery.data ?? null;
  const carregando = assinaturaQuery.isLoading || pagamentosQuery.isLoading;
  const erro = assinaturaQuery.isError || pagamentosQuery.isError;

  async function confirmarCancelamento() {
    if (!token) return;
    try {
      await cancelarMutacao.mutateAsync();
      setDialogoAberto(false);
      setAvisoCancelada(true);
      notificar("Assinatura cancelada. Você mantém o acesso Premium até o vencimento.", "info");
    } catch (e) {
      notificar(e instanceof api.ApiError ? e.message : "Não foi possível cancelar a assinatura.", "erro");
    }
  }

  async function inscreverNaNewsletter() {
    if (!token) return;
    try {
      const categorias = categoriasNewsletter
        .split(",")
        .map((c) => c.trim())
        .filter(Boolean);
      const resultado = await newsletterSalvar.mutateAsync({
        tipo: tipoNewsletter,
        periodo: periodoNewsletter,
        categorias: tipoNewsletter === "padrao" ? undefined : categorias,
      });
      setNewsletterAtiva(resultado.ativa);
      notificar("Inscrição na newsletter salva.", "sucesso");
    } catch (e) {
      notificar(e instanceof api.ApiError ? e.message : "Não foi possível salvar a inscrição.", "erro");
    }
  }

  async function cancelarNewsletterAtual() {
    if (!token) return;
    try {
      await newsletterCancelar.mutateAsync();
      setNewsletterAtiva(false);
      notificar("Inscrição na newsletter cancelada.", "info");
    } catch (e) {
      notificar(e instanceof api.ApiError ? e.message : "Não foi possível cancelar a inscrição.", "erro");
    }
  }

  const salvandoNewsletter = newsletterSalvar.isPending || newsletterCancelar.isPending;

  return (
    <div className="mx-auto w-full max-w-4xl px-4 py-8 sm:px-6">
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div className="grid gap-1">
          <h1 className="font-[var(--fonte-titulo)] text-3xl font-bold tracking-tight text-balance text-[var(--cor-texto)]">
            Minha conta
          </h1>
          {usuario && <p className="text-sm text-[var(--cor-texto-suave)]">Você entrou como {usuario.email}.</p>}
        </div>
        {usuario && (
          <Badge variant={usuario.papel === "premium" ? "default" : "secondary"}>
            {usuario.papel === "premium" ? "Premium" : usuario.papel === "admin" ? "Admin" : "Free"}
          </Badge>
        )}
      </div>

      {avisoCancelada && (
        <div className="mb-6" aria-live="polite">
          <Alert variant="success">
            <AlertTitle>Cancelamento registrado</AlertTitle>
            <AlertDescription>
              Você mantém o acesso Premium até o fim do período já pago. Mudou de ideia?{" "}
              <Link href="/planos" className="font-medium underline underline-offset-4">
                Veja os planos
              </Link>{" "}
              para assinar de novo.
            </AlertDescription>
          </Alert>
        </div>
      )}

      {carregando && <SkeletonLista quantidade={2} />}
      {erro && (
        <ErrorState
          mensagem="Não foi possível carregar sua conta."
          aoTentarNovamente={() => {
            void assinaturaQuery.refetch();
            void pagamentosQuery.refetch();
          }}
        />
      )}

      {!carregando && !erro && (
        <Tabs value={aba} onValueChange={(v) => trocarAba(v as Aba)} className="grid gap-6">
          <TabsList aria-label="Seções da conta">
            <TabsTrigger value="assinatura">Assinatura</TabsTrigger>
            <TabsTrigger value="pagamentos">Pagamentos</TabsTrigger>
            <TabsTrigger value="perfil">Perfil e newsletter</TabsTrigger>
          </TabsList>

          <TabsContent value="assinatura">
            <Card>
              <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-2">
                <CardTitle className="text-base">Sua assinatura</CardTitle>
                <Link
                  href="/planos"
                  className="rounded-md text-xs font-semibold uppercase tracking-wider text-[var(--cor-primaria)] hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]"
                >
                  Ver planos
                </Link>
              </CardHeader>
              <CardContent>
                {!assinatura ? (
                  <p className="text-sm text-[var(--cor-texto-suave)]">
                    Você ainda não tem uma assinatura. Assine o Premium e leia sem limites.
                  </p>
                ) : (
                  <div className="grid gap-3 rounded-lg border border-[var(--cor-borda)] bg-[var(--cor-fundo)] p-4">
                    <p className="text-sm">
                      <span className="font-semibold">Plano:</span> {assinatura.plan.nome}
                    </p>
                    <p className="flex flex-wrap items-center gap-2 text-sm">
                      <span className="font-semibold">Status:</span>
                      <Badge variant={VARIANTE_STATUS[assinatura.status]}>{ROTULOS_STATUS[assinatura.status]}</Badge>
                    </p>
                    <p className="text-sm text-[var(--cor-texto-suave)]">
                      Início em {formatarData(assinatura.inicio)} — vence em {formatarData(assinatura.vencimento)}
                    </p>
                    {(assinatura.status === "ativa" || assinatura.status === "teste") && (
                      <Dialog open={dialogoAberto} onOpenChange={setDialogoAberto}>
                        <DialogTrigger asChild>
                          <Button variant="destructive" className="w-fit">
                            Cancelar assinatura
                          </Button>
                        </DialogTrigger>
                        <DialogContent>
                          <DialogHeader>
                            <DialogTitle>Cancelar a assinatura?</DialogTitle>
                            <DialogDescription>
                              Você mantém o acesso Premium até {formatarData(assinatura.vencimento)}. Depois disso,
                              sua conta volta ao plano Free.
                            </DialogDescription>
                          </DialogHeader>
                          <DialogFooter>
                            <Button variant="outline" onClick={() => setDialogoAberto(false)} disabled={cancelarMutacao.isPending}>
                              Manter assinatura
                            </Button>
                            <Button variant="destructive" loading={cancelarMutacao.isPending} onClick={() => void confirmarCancelamento()}>
                              Sim, cancelar
                            </Button>
                          </DialogFooter>
                        </DialogContent>
                      </Dialog>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="pagamentos">
            <Card>
              <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-2">
                <div>
                  <CardTitle className="text-base">Histórico de pagamentos</CardTitle>
                  <CardDescription>Confira cobranças e status.</CardDescription>
                </div>
                <div className="flex items-center gap-2">
                  <Label htmlFor="ordem-pagamentos" className="text-xs text-[var(--cor-texto-suave)]">
                    Ordenar
                  </Label>
                  <select
                    id="ordem-pagamentos"
                    value={ordemPagamentos}
                    onChange={(e) => setOrdemPagamentos(e.target.value as "recentes" | "antigos")}
                    className="h-10 min-h-[44px] rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo)] px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]"
                  >
                    <option value="recentes">Mais recentes</option>
                    <option value="antigos">Mais antigos</option>
                  </select>
                </div>
              </CardHeader>
              <CardContent>
                {pagamentosOrdenados.length === 0 ? (
                  <EmptyState titulo="Nenhum pagamento registrado" descricao="Seus pagamentos aparecerão aqui." />
                ) : (
                  <DataTable
                    legenda="Histórico de pagamentos"
                    linhas={pagamentosOrdenados}
                    colunas={[
                      { cabecalho: "Data", render: (p) => formatarData(p.criado_em) },
                      { cabecalho: "Valor", render: (p) => formatarPreco(p.valor) },
                      {
                        cabecalho: "Status",
                        render: (p) => <Badge variant={VARIANTE_PAGAMENTO[p.status]}>{p.status}</Badge>,
                      },
                    ]}
                  />
                )}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="perfil">
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Newsletter</CardTitle>
                <CardDescription>Receba os destaques do dia no seu e-mail, no período que preferir.</CardDescription>
              </CardHeader>
              <CardContent className="grid gap-4">
                <div aria-live="polite">
                  {newsletterAtiva === true && (
                    <Alert variant="success">
                      <AlertTitle>Inscrição ativa</AlertTitle>
                      <AlertDescription>Você receberá a newsletter no período escolhido.</AlertDescription>
                    </Alert>
                  )}
                  {newsletterAtiva === false && (
                    <p className="text-sm text-[var(--cor-texto-suave)]">Você não está inscrito na newsletter no momento.</p>
                  )}
                </div>
                <div className="grid gap-4 sm:grid-cols-2">
                  <CampoSelecao
                    id="tipo-newsletter"
                    name="tipo-newsletter"
                    rotulo="Tipo"
                    value={tipoNewsletter}
                    onChange={(e) => setTipoNewsletter(e.target.value as api.TipoNewsletter)}
                  >
                    <option value="padrao">Padrão (destaques do dia)</option>
                    <option value="categoria">Por categoria</option>
                    {usuario?.papel === "premium" && <option value="personalizada">Personalizada (Premium)</option>}
                  </CampoSelecao>
                  <CampoSelecao
                    id="periodo-newsletter"
                    name="periodo-newsletter"
                    rotulo="Período de envio"
                    value={periodoNewsletter}
                    onChange={(e) => setPeriodoNewsletter(e.target.value as api.PeriodoNewsletter)}
                  >
                    <option value="manha">Resumo da manhã</option>
                    <option value="noite">Resumo da noite</option>
                  </CampoSelecao>
                </div>
                {tipoNewsletter !== "padrao" && (
                  <CampoTexto
                    id="categorias-newsletter"
                    name="categorias-newsletter"
                    rotulo="Categorias (separadas por vírgula)"
                    placeholder="política, economia, esportes…"
                    value={categoriasNewsletter}
                    onChange={(e) => setCategoriasNewsletter(e.target.value)}
                  />
                )}
                <div className="flex flex-wrap gap-3">
                  <Button onClick={() => void inscreverNaNewsletter()} loading={salvandoNewsletter}>
                    Salvar inscrição
                  </Button>
                  <Button variante="secundaria" onClick={() => void cancelarNewsletterAtual()} disabled={salvandoNewsletter}>
                    Cancelar inscrição
                  </Button>
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      )}
    </div>
  );
}
