"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import * as api from "@/lib/api";

export default function PaginaOnboarding() {
  const router = useRouter();
  const { token, usuario, carregando: carregandoAuth } = useAuth();

  const [interesses, setInteresses] = useState("");
  const [localidade, setLocalidade] = useState("");
  const [canalPreferido, setCanalPreferido] = useState<"email" | "push" | "">("");
  const [carregando, setCarregando] = useState(true);
  const [salvando, setSalvando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [concluido, setConcluido] = useState(false);

  useEffect(() => {
    if (carregandoAuth) return;
    if (!token) {
      router.push("/login");
      return;
    }
    api
      .obterOnboarding(token)
      .then((dados) => {
        setInteresses(dados.interesses.join(", "));
        setLocalidade(dados.localidade);
        setCanalPreferido((dados.canal_preferido as "email" | "push" | "") || "");
      })
      .catch((e: unknown) => {
        setErro(
          e instanceof api.ApiError ? e.message : "Não foi possível carregar o onboarding."
        );
      })
      .finally(() => setCarregando(false));
  }, [token, carregandoAuth, router]);

  async function salvar(pular: boolean) {
    if (!token) return;
    setErro(null);
    setSalvando(true);
    try {
      await api.atualizarOnboarding(token, {
        interesses: interesses
          .split(",")
          .map((i) => i.trim())
          .filter(Boolean),
        localidade,
        canal_preferido: canalPreferido || undefined,
        pular,
      });
      setConcluido(true);
    } catch (e) {
      setErro(e instanceof api.ApiError ? e.message : "Não foi possível salvar.");
    } finally {
      setSalvando(false);
    }
  }

  function aoSubmeter(evento: FormEvent) {
    evento.preventDefault();
    salvar(false);
  }

  if (carregandoAuth || carregando) return <p className="texto-suave">Carregando...</p>;

  if (concluido) {
    return (
      <div className="formulario">
        <h1>Tudo pronto!</h1>
        <p className="mensagem-sucesso">Suas preferências foram salvas.</p>
        <a href="/" className="botao">
          Ir para o feed
        </a>
      </div>
    );
  }

  if (usuario && !usuario.email_verificado) {
    return (
      <div className="formulario">
        <h1>Confirme seu e-mail</h1>
        <p className="texto-suave">
          Você precisa confirmar seu e-mail antes de completar o onboarding. Verifique sua
          caixa de entrada.
        </p>
      </div>
    );
  }

  return (
    <div className="formulario">
      <h1>Personalize sua experiência</h1>
      {erro && <p className="mensagem-erro">{erro}</p>}
      <form onSubmit={aoSubmeter}>
        <div className="campo">
          <label htmlFor="interesses">Interesses (separados por vírgula)</label>
          <input
            id="interesses"
            type="text"
            placeholder="política, tecnologia, esportes"
            value={interesses}
            onChange={(e) => setInteresses(e.target.value)}
          />
        </div>
        <div className="campo">
          <label htmlFor="localidade">Localidade de interesse</label>
          <input
            id="localidade"
            type="text"
            placeholder="Cidade, estado"
            value={localidade}
            onChange={(e) => setLocalidade(e.target.value)}
          />
        </div>
        <div className="campo">
          <label htmlFor="canal">Canal preferido</label>
          <select
            id="canal"
            value={canalPreferido}
            onChange={(e) => setCanalPreferido(e.target.value as "email" | "push" | "")}
          >
            <option value="">Selecione</option>
            <option value="email">E-mail</option>
            <option value="push">Notificação push</option>
          </select>
        </div>
        <div style={{ display: "flex", gap: "0.6rem" }}>
          <button type="submit" className="botao" disabled={salvando}>
            {salvando ? "Salvando..." : "Salvar"}
          </button>
          <button
            type="button"
            className="botao botao-secundario"
            disabled={salvando}
            onClick={() => salvar(true)}
          >
            Pular por agora
          </button>
        </div>
      </form>
    </div>
  );
}
