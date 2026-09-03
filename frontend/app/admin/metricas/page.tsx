"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import * as api from "@/lib/api";

function formatarPercentual(valor: number): string {
  return `${(valor * 100).toFixed(1)}%`;
}

function formatarMoeda(valor: string): string {
  const numero = Number(valor);
  if (Number.isNaN(numero)) return valor;
  return numero.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

export default function PaginaAdminMetricas() {
  const router = useRouter();
  const { token, usuario, carregando: carregandoAuth } = useAuth();

  const [dias, setDias] = useState(30);
  const [painel, setPainel] = useState<api.PainelMetricas | null>(null);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    if (carregandoAuth) return;
    if (!token) {
      router.push("/login");
      return;
    }
    if (usuario && usuario.papel !== "admin") {
      setErro("Acesso restrito à administração.");
      setCarregando(false);
      return;
    }
    setCarregando(true);
    api
      .obterPainelMetricas(token, dias)
      .then(setPainel)
      .catch((e: unknown) => {
        setErro(e instanceof api.ApiError ? e.message : "Não foi possível carregar o painel.");
      })
      .finally(() => setCarregando(false));
  }, [token, usuario, carregandoAuth, router, dias]);

  if (carregandoAuth || carregando) return <p className="texto-suave">Carregando...</p>;
  if (erro) return <p className="mensagem-erro">{erro}</p>;

  return (
    <div>
      <h1>Painel de métricas de negócio</h1>

      <div className="controles-feed">
        <label htmlFor="dias">Período (dias)</label>
        <select id="dias" value={dias} onChange={(e) => setDias(Number(e.target.value))}>
          <option value={7}>7</option>
          <option value={30}>30</option>
          <option value={90}>90</option>
        </select>
      </div>

      {painel && (
        <div className="cartao">
          <p>
            <strong>Usuários cadastrados (total):</strong> {painel.usuarios_cadastrados_total}
          </p>
          <p>
            <strong>Novos cadastros no período:</strong> {painel.usuarios_cadastrados_periodo}
          </p>
          <p>
            <strong>Usuários ativos (24h):</strong> {painel.usuarios_ativos_diarios}
          </p>
          <p>
            <strong>Usuários ativos (30 dias):</strong> {painel.usuarios_ativos_mensais}
          </p>
          <p>
            <strong>Retenção no período:</strong> {formatarPercentual(painel.retencao_periodo)}
          </p>
          <p>
            <strong>Assinaturas ativas:</strong> {painel.assinaturas_ativas}
          </p>
          <p>
            <strong>Conversão free → premium:</strong> {formatarPercentual(painel.conversao_free_premium)}
          </p>
          <p>
            <strong>Receita recorrente no período:</strong>{" "}
            {formatarMoeda(painel.receita_recorrente_periodo)}
          </p>
          <p>
            <strong>Receita média por assinante:</strong>{" "}
            {formatarMoeda(painel.receita_media_por_assinante)}
          </p>
          <p>
            <strong>Churn no período:</strong> {formatarPercentual(painel.churn_periodo)}
          </p>
          <p>
            <strong>Taxa de renovação no período:</strong> {formatarPercentual(painel.taxa_renovacao_periodo)}
          </p>
          <p>
            <strong>Organizações B2B ativas:</strong> {painel.organizacoes_b2b_ativas}
          </p>
        </div>
      )}
    </div>
  );
}
