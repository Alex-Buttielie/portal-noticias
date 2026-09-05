"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { useToast } from "@/components/ToastProvider";
import * as api from "@/lib/api";

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

  const [assinatura, setAssinatura] = useState<api.Assinatura | null>(null);
  const [pagamentos, setPagamentos] = useState<api.Pagamento[]>([]);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState<string | null>(null);
  const [cancelando, setCancelando] = useState(false);

  const [tipoNewsletter, setTipoNewsletter] = useState<api.TipoNewsletter>("padrao");
  const [periodoNewsletter, setPeriodoNewsletter] = useState<api.PeriodoNewsletter>("manha");
  const [categoriasNewsletter, setCategoriasNewsletter] = useState("");
  const [newsletterAtiva, setNewsletterAtiva] = useState<boolean | null>(null);
  const [salvandoNewsletter, setSalvandoNewsletter] = useState(false);

  useEffect(() => {
    if (carregandoAuth) return;
    if (!token) {
      router.push("/login");
      return;
    }
    Promise.all([api.obterMinhaAssinatura(token), api.obterHistoricoPagamentos(token)])
      .then(([minhaAssinatura, historico]) => {
        setAssinatura(minhaAssinatura);
        setPagamentos(historico);
      })
      .catch((e: unknown) => {
        setErro(e instanceof api.ApiError ? e.message : "Não foi possível carregar sua conta.");
      })
      .finally(() => setCarregando(false));
  }, [token, carregandoAuth, router]);

  async function cancelar() {
    if (!token) return;
    const confirmado = window.confirm(
      "Tem certeza que deseja cancelar sua assinatura? Você mantém acesso Premium até o fim do período já pago."
    );
    if (!confirmado) return;

    setCancelando(true);
    setErro(null);
    try {
      const atualizada = await api.cancelarAssinatura(token);
      setAssinatura(atualizada);
      notificar("Assinatura cancelada. Você mantém o acesso Premium até o vencimento.", "info");
    } catch (e) {
      notificar(
        e instanceof api.ApiError ? e.message : "Não foi possível cancelar a assinatura.",
        "erro"
      );
    } finally {
      setCancelando(false);
    }
  }

  async function inscreverNaNewsletter() {
    if (!token) return;
    setSalvandoNewsletter(true);
    try {
      const categorias = categoriasNewsletter
        .split(",")
        .map((c) => c.trim())
        .filter(Boolean);
      const resultado = await api.inscreverNewsletter(token, {
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
    } finally {
      setSalvandoNewsletter(false);
    }
  }

  async function cancelarNewsletterAtual() {
    if (!token) return;
    setSalvandoNewsletter(true);
    try {
      await api.cancelarNewsletter(token);
      setNewsletterAtiva(false);
      notificar("Inscrição na newsletter cancelada.", "info");
    } catch (e) {
      notificar(
        e instanceof api.ApiError ? e.message : "Não foi possível cancelar a inscrição.",
        "erro"
      );
    } finally {
      setSalvandoNewsletter(false);
    }
  }

  if (carregandoAuth || carregando) return <p className="texto-suave">Carregando...</p>;

  return (
    <div>
      <h1>Minha conta</h1>
      {usuario && (
        <p className="texto-suave">
          {usuario.email} —{" "}
          <span
            className={
              usuario.papel === "premium"
                ? "selo-premium"
                : usuario.papel === "admin"
                  ? "selo-premium"
                  : "selo-free"
            }
          >
            {usuario.papel === "premium" ? "Premium" : usuario.papel === "admin" ? "Admin" : "Free"}
          </span>
        </p>
      )}

      {erro && <p className="mensagem-erro">{erro}</p>}

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
            <button
              type="button"
              className="botao botao-perigo"
              onClick={cancelar}
              disabled={cancelando}
            >
              {cancelando ? "Cancelando..." : "Cancelar assinatura"}
            </button>
          )}
        </div>
      )}

      <h2 style={{ fontSize: "1.1rem", marginTop: "1.5rem" }}>Histórico de pagamentos</h2>
      {pagamentos.length === 0 ? (
        <p className="texto-suave">Nenhum pagamento registrado ainda.</p>
      ) : (
        <div className="tabela-wrapper">
          <table className="tabela">
            <thead>
              <tr>
                <th>Data</th>
                <th>Valor</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {pagamentos.map((pagamento) => (
                <tr key={pagamento.id}>
                  <td>{formatarData(pagamento.criado_em)}</td>
                  <td>{formatarPreco(pagamento.valor)}</td>
                  <td>{pagamento.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <h2 style={{ fontSize: "1.1rem", marginTop: "1.5rem" }}>Newsletter</h2>
      <div className="cartao">
        {newsletterAtiva === true && (
          <p className="mensagem-sucesso">Inscrição salva — você receberá a newsletter.</p>
        )}
        {newsletterAtiva === false && (
          <p className="texto-suave">Você não está inscrito na newsletter no momento.</p>
        )}
        <div className="campo">
          <label htmlFor="tipo-newsletter">Tipo</label>
          <select
            id="tipo-newsletter"
            value={tipoNewsletter}
            onChange={(e) => setTipoNewsletter(e.target.value as api.TipoNewsletter)}
          >
            <option value="padrao">Padrão (destaques do dia)</option>
            <option value="categoria">Por categoria</option>
            {usuario?.papel === "premium" && (
              <option value="personalizada">Personalizada (Premium)</option>
            )}
          </select>
        </div>
        <div className="campo">
          <label htmlFor="periodo-newsletter">Período de envio</label>
          <select
            id="periodo-newsletter"
            value={periodoNewsletter}
            onChange={(e) => setPeriodoNewsletter(e.target.value as api.PeriodoNewsletter)}
          >
            <option value="manha">Resumo da manhã</option>
            <option value="noite">Resumo da noite</option>
          </select>
        </div>
        {tipoNewsletter !== "padrao" && (
          <div className="campo">
            <label htmlFor="categorias-newsletter">Categorias (separadas por vírgula)</label>
            <input
              id="categorias-newsletter"
              type="text"
              placeholder="política, economia, esportes"
              value={categoriasNewsletter}
              onChange={(e) => setCategoriasNewsletter(e.target.value)}
            />
          </div>
        )}
        <button type="button" className="botao" onClick={inscreverNaNewsletter} disabled={salvandoNewsletter}>
          {salvandoNewsletter ? "Salvando..." : "Inscrever-se / atualizar"}
        </button>{" "}
        <button
          type="button"
          className="botao botao-secundario"
          onClick={cancelarNewsletterAtual}
          disabled={salvandoNewsletter}
        >
          Cancelar inscrição
        </button>
      </div>
    </div>
  );
}
