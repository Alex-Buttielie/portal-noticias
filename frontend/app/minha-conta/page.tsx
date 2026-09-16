"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
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
import Badge from "@/components/Badge";
import { Button } from "@/components/ui/Button";
import { CampoSelecao, CampoTexto } from "@/components/ui/FormField";
import { DataTable } from "@/components/ui/Data";
import { EmptyState, ErrorState, SkeletonLista } from "@/components/ui/Estados";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/Cards";
import { cn } from "@/lib/utils";

const ROTULOS_STATUS: Record<api.StatusAssinatura, string> = {
  teste: "Em teste",
  ativa: "Ativa",
  pagamento_pendente: "Pagamento pendente",
  inadimplente: "Pagamento em atraso",
  cancelada: "Cancelada (acesso mantido até o vencimento)",
  expirada: "Expirada",
  encerrada: "Encerrada",
};

function formatarData(data: string | null): string {
  if (!data) return "—";
  try {
    return new Date(data).toLocaleDateString("pt-BR");
  } catch {
    return data;
  }
}

function formatarPreco(preco: string): string {
  const numero = Number(preco);
  if (Number.isNaN(numero)) return preco;
  return numero.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

export default function PaginaMinhaConta() {
  const router = useRouter();
  const { token, usuario, carregando: carregandoAuth } = useAuth();
  const { notificar } = useToast();
  const assinaturaQuery = useMinhaAssinatura();
  const pagamentosQuery = useHistoricoPagamentos();
  const cancelarMutacao = useCancelarAssinatura();
  const newsletterSalvar = useNewsletterSalvar();
  const newsletterCancelar = useNewsletterCancelar();

  const [tipoNewsletter, setTipoNewsletter] = useState<api.TipoNewsletter>("padrao");
  const [periodoNewsletter, setPeriodoNewsletter] = useState<api.PeriodoNewsletter>("manha");
  const [categoriasNewsletter, setCategoriasNewsletter] = useState("");
  const [newsletterAtiva, setNewsletterAtiva] = useState<boolean | null>(null);

  useEffect(() => {
    if (!carregandoAuth && !token) {
      router.push("/login");
    }
  }, [carregandoAuth, token, router]);

  if (carregandoAuth)
    return (
      <div className={cn("container mx-auto max-w-2xl px-4 py-10")}>
        <p className="text-sm text-[var(--cor-texto-suave)]">Carregando…</p>
      </div>
    );

  const assinatura = assinaturaQuery.data ?? null;
  const carregando = assinaturaQuery.isLoading || pagamentosQuery.isLoading;
  const erro = assinaturaQuery.isError || pagamentosQuery.isError;

  async function cancelar() {
    if (!token) return;
    const confirmado = window.confirm(
      "Tem certeza que deseja cancelar sua assinatura? Você mantém acesso Premium até o fim do período já pago."
    );
    if (!confirmado) return;
    try {
      await cancelarMutacao.mutateAsync();
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
<div className={cn("container mx-auto max-w-4xl px-4 py-8 sm:px-6")}>
      <div className="mb-8 flex flex-wrap items-start justify-between gap-4 secao-bloco secao-cabecalho secao-ver-todas cartao">
        <div className="grid gap-1">
          <p className="text-xs font-bold uppercase tracking-widest text-[var(--cor-primaria)] secao-eyebrow">Sua conta</p>
          <h1 id="conta-titulo" className="font-[var(--fonte-titulo)] text-3xl font-bold tracking-tight text-[var(--cor-texto)] secao-titulo">
            Minha conta
          </h1>
          {usuario && <p className="text-sm text-[var(--cor-texto-suave)]">Você entrou como {usuario.email}.</p>}
        </div>
        {usuario && (
          <Badge variante={usuario.papel === "free" ? "neutro" : "premium"}>
            {usuario.papel === "premium" ? "Premium" : usuario.papel === "admin" ? "Admin" : "Free"}
          </Badge>
        )}
      </div>

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
        <div className="grid gap-6">
          <Card className="shadow-sm">
            <CardHeader className="flex flex-row items-center justify-between space-y-0">
              <CardTitle id="conta-assinatura" className="text-base">
                Assinatura
              </CardTitle>
              <a href="/planos" className="text-xs font-semibold uppercase tracking-wider text-[var(--cor-primaria)] hover:underline">
                Ver planos
              </a>
            </CardHeader>
            <CardContent>
              {!assinatura ? (
                <p className="text-sm text-[var(--cor-texto-suave)]">Você ainda não tem uma assinatura. Assine o Premium e leia sem limites.</p>
              ) : (
                <div className="grid gap-3 rounded-lg border border-[var(--cor-borda)] bg-[var(--cor-fundo)] p-4">
                  <p className="text-sm">
                    <span className="font-semibold">Plano:</span> {assinatura.plan.nome}
                  </p>
                  <p className="text-sm">
                    <span className="font-semibold">Status:</span> {ROTULOS_STATUS[assinatura.status]}
                  </p>
                  <p className="text-sm text-[var(--cor-texto-suave)]">
                    Início em {formatarData(assinatura.inicio)} — vence em {formatarData(assinatura.vencimento)}
                  </p>
                  {(assinatura.status === "ativa" || assinatura.status === "teste") && (
                    <Button variante="perigo" onClick={() => void cancelar()} carregando={cancelarMutacao.isPending} className="w-fit">
                      Cancelar assinatura
                    </Button>
                  )}
                </div>
              )}
</CardContent>
          </Card>

          <Card className="shadow-sm secao-bloco secao-cabecalho secao-titulo">
            <CardHeader>
              <CardTitle id="conta-pagamentos" className="text-base">
                Histórico de pagamentos
              </CardTitle>
              <CardDescription>Confira cobranças e status.</CardDescription>
            </CardHeader>
            <CardContent>
              {(pagamentosQuery.data?.length ?? 0) === 0 ? (
                <EmptyState titulo="Nenhum pagamento registrado" descricao="Seus pagamentos aparecerão aqui." />
              ) : (
                <DataTable
                  legenda="Histórico de pagamentos"
                  linhas={pagamentosQuery.data ?? []}
                  colunas={[
                    { cabecalho: "Data", render: (p) => formatarData(p.criado_em) },
                    { cabecalho: "Valor", render: (p) => formatarPreco(p.valor) },
                    { cabecalho: "Status", render: (p) => p.status },
                  ]}
                />
              )}
</CardContent>
          </Card>

          <Card className="shadow-sm secao-bloco secao-titulo mensagem-sucesso">
            <CardHeader>
              <CardTitle id="conta-newsletter" className="text-base">
                Newsletter
              </CardTitle>
              <CardDescription>Receba os destaques do dia no seu e-mail, no período que preferir.</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4">
              {newsletterAtiva === true && (
                <div className="rounded-md bg-[var(--cor-sucesso)]/10 px-4 py-3 text-sm text-[var(--cor-sucesso)] secao-cabecalho cartao">Inscrição salva — você receberá a newsletter.</div>
              )}
              {newsletterAtiva === false && <p className="text-sm text-[var(--cor-texto-suave)]">Você não está inscrito na newsletter no momento.</p>}
              <div className="grid gap-4 sm:grid-cols-2">
                <CampoSelecao
                  id="tipo-newsletter"
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
                <Button onClick={() => void inscreverNaNewsletter()} carregando={salvandoNewsletter}>
                  Salvar inscrição
                </Button>
                <Button variante="secundaria" onClick={() => void cancelarNewsletterAtual()} disabled={salvandoNewsletter}>
                  Cancelar inscrição
                </Button>
              </div>
</CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
