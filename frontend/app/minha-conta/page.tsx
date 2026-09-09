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

  if (carregandoAuth) return <p className="texto-suave">Carregando...</p>;

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
      notificar(
        e instanceof api.ApiError ? e.message : "Não foi possível cancelar a assinatura.",
        "erro"
      );
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
      notificar(
        e instanceof api.ApiError ? e.message : "Não foi possível salvar a inscrição.",
        "erro"
      );
    }
  }

  async function cancelarNewsletterAtual() {
    if (!token) return;
    try {
      await newsletterCancelar.mutateAsync();
      setNewsletterAtiva(false);
      notificar("Inscrição na newsletter cancelada.", "info");
    } catch (e) {
      notificar(
        e instanceof api.ApiError ? e.message : "Não foi possível cancelar a inscrição.",
        "erro"
      );
    }
  }

  const salvandoNewsletter = newsletterSalvar.isPending || newsletterCancelar.isPending;

  return (
    <div>
      <h1>Minha conta</h1>
      {usuario && (
        <p className="texto-suave">
          {usuario.email} —{" "}
          <Badge variante={usuario.papel === "free" ? "neutro" : "premium"}>
            {usuario.papel === "premium" ? "Premium" : usuario.papel === "admin" ? "Admin" : "Free"}
          </Badge>
        </p>
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
        <>
          <h2 style={{ fontSize: "1.1rem", marginTop: "1.5rem" }}>Assinatura</h2>
          {!assinatura && (
            <p className="texto-suave">
              Você ainda não tem uma assinatura. <a href="/planos">Ver planos</a>
            </p>
          )}
          {assinatura && (
            <div className="cartao">
              <p>
                <strong>Plano:</strong> {assinatura.plan.nome}
              </p>
              <p>
                <strong>Status:</strong> {ROTULOS_STATUS[assinatura.status]}
              </p>
              <p>
                <strong>Início:</strong> {formatarData(assinatura.inicio)} —{" "}
                <strong>Vencimento:</strong> {formatarData(assinatura.vencimento)}
              </p>
              {(assinatura.status === "ativa" || assinatura.status === "teste") && (
                <Button variante="perigo" onClick={() => void cancelar()} carregando={cancelarMutacao.isPending}>
                  Cancelar assinatura
                </Button>
              )}
            </div>
          )}

          <h2 style={{ fontSize: "1.1rem", marginTop: "1.5rem" }}>Histórico de pagamentos</h2>
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

          <h2 style={{ fontSize: "1.1rem", marginTop: "1.5rem" }}>Newsletter</h2>
          <div className="cartao">
            {newsletterAtiva === true && (
              <p className="mensagem-sucesso">Inscrição salva — você receberá a newsletter.</p>
            )}
            {newsletterAtiva === false && (
              <p className="texto-suave">Você não está inscrito na newsletter no momento.</p>
            )}
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
            {tipoNewsletter !== "padrao" && (
              <CampoTexto
                id="categorias-newsletter"
                rotulo="Categorias (separadas por vírgula)"
                placeholder="política, economia, esportes"
                value={categoriasNewsletter}
                onChange={(e) => setCategoriasNewsletter(e.target.value)}
              />
            )}
            <Button onClick={() => void inscreverNaNewsletter()} carregando={salvandoNewsletter}>
              Inscrever-se / atualizar
            </Button>{" "}
            <Button variante="secundaria" onClick={() => void cancelarNewsletterAtual()} disabled={salvandoNewsletter}>
              Cancelar inscrição
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
