"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { useToast } from "@/components/ToastProvider";
import * as api from "@/lib/api";

function formatarPreco(preco: string): string {
  const numero = Number(preco);
  if (Number.isNaN(numero)) return preco;
  return numero.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

export default function PaginaPlanos() {
  const router = useRouter();
  const { token, usuario } = useAuth();
  const { notificar } = useToast();
  const [planos, setPlanos] = useState<api.Plano[]>([]);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState<string | null>(null);
  const [assinando, setAssinando] = useState<number | null>(null);

  useEffect(() => {
    api
      .obterPlanos()
      .then(setPlanos)
      .catch((e: unknown) => {
        setErro(e instanceof api.ApiError ? e.message : "Não foi possível carregar os planos.");
      })
      .finally(() => setCarregando(false));
  }, []);

  async function assinar(planoId: number) {
    if (!token) {
      router.push("/login");
      return;
    }
    setErro(null);
    setAssinando(planoId);
    try {
      const assinatura = await api.assinarPlano(token, planoId);
      notificar(
        assinatura.status === "ativa"
          ? "Assinatura ativada com sucesso! Aproveite o Premium."
          : "Assinatura criada — aguardando confirmação de pagamento.",
        "sucesso"
      );
    } catch (e) {
      notificar(
        e instanceof api.ApiError ? e.message : "Não foi possível assinar este plano.",
        "erro"
      );
    } finally {
      setAssinando(null);
    }
  }

  return (
    <div>
      <h1>Planos Premium</h1>
      <p className="texto-suave">Sem anúncios e com recursos completos de personalização.</p>

      {erro && <p className="mensagem-erro">{erro}</p>}
      {carregando && <p className="texto-suave">Carregando planos...</p>}

      {!carregando && planos.length === 0 && !erro && (
        <p className="texto-suave">Nenhum plano disponível no momento.</p>
      )}

      {planos.map((plano) => (
        <div className="plano-cartao" key={plano.id}>
          <h2>{plano.nome}</h2>
          <p className="plano-preco">{formatarPreco(plano.preco)}</p>
          <p className="texto-suave">a cada {plano.duracao_dias} dias</p>
          <button
            type="button"
            className="botao"
            disabled={assinando === plano.id || usuario?.papel === "premium"}
            onClick={() => assinar(plano.id)}
          >
            {usuario?.papel === "premium"
              ? "Você já é Premium"
              : assinando === plano.id
              ? "Processando..."
              : "Assinar"}
          </button>
        </div>
      ))}
    </div>
  );
}
