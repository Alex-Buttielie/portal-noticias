"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { useToast } from "@/components/ToastProvider";
import * as api from "@/lib/api";
import { useOnboarding, useSalvarOnboarding } from "@/lib/queries";
import { Button } from "@/components/ui/Button";
import { CampoSelecao, CampoTexto } from "@/components/ui/FormField";
import { ErrorState } from "@/components/ui/Estados";

export default function PaginaOnboarding() {
  const router = useRouter();
  const { token, usuario, carregando: carregandoAuth } = useAuth();
  const { notificar } = useToast();
  const onboarding = useOnboarding();
  const salvarMutacao = useSalvarOnboarding();

  const [interesses, setInteresses] = useState("");
  const [localidade, setLocalidade] = useState("");
  const [canalPreferido, setCanalPreferido] = useState<"email" | "push" | "">("");
  const [erro, setErro] = useState<string | null>(null);
  const [concluido, setConcluido] = useState(false);

  useEffect(() => {
    if (!carregandoAuth && !token) {
      router.push("/login");
    }
  }, [carregandoAuth, token, router]);

  useEffect(() => {
    const dados = onboarding.data;
    if (dados) {
      setInteresses(dados.interesses.join(", "));
      setLocalidade(dados.localidade);
      setCanalPreferido((dados.canal_preferido as "email" | "push" | "") || "");
    }
  }, [onboarding.data]);

  async function salvar(pular: boolean) {
    if (!token) return;
    setErro(null);
    try {
      await salvarMutacao.mutateAsync({
        interesses: interesses
          .split(",")
          .map((i) => i.trim())
          .filter(Boolean),
        localidade,
        canal_preferido: canalPreferido || undefined,
        pular,
      });
      setConcluido(true);
      notificar("Preferências salvas.", "sucesso");
    } catch (e) {
      setErro(e instanceof api.ApiError ? e.message : "Não foi possível salvar.");
    }
  }

  function aoSubmeter(evento: FormEvent) {
    evento.preventDefault();
    void salvar(false);
  }

  if (carregandoAuth || onboarding.isLoading) return <p className="texto-suave">Carregando...</p>;

  if (concluido) {
    return (
      <div className="formulario">
        <h1>Tudo pronto!</h1>
        <p className="mensagem-sucesso">Suas preferências foram salvas.</p>
        <a href="/" className="botao botao--primaria botao--medio">
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
      {erro && <ErrorState mensagem={erro} />}
      {onboarding.isError && <ErrorState mensagem="Não foi possível carregar o onboarding." aoTentarNovamente={() => void onboarding.refetch()} />}
      <form onSubmit={aoSubmeter}>
        <CampoTexto
          id="interesses"
          rotulo="Interesses (separados por vírgula)"
          placeholder="política, tecnologia, esportes"
          value={interesses}
          onChange={(e) => setInteresses(e.target.value)}
        />
        <CampoTexto
          id="localidade"
          rotulo="Localidade de interesse"
          placeholder="Cidade, estado"
          value={localidade}
          onChange={(e) => setLocalidade(e.target.value)}
        />
        <CampoSelecao
          id="canal"
          rotulo="Canal preferido"
          value={canalPreferido}
          onChange={(e) => setCanalPreferido(e.target.value as "email" | "push" | "")}
        >
          <option value="">Selecione</option>
          <option value="email">E-mail</option>
          <option value="push">Notificação push</option>
        </CampoSelecao>
        <div style={{ display: "flex", gap: "0.6rem" }}>
          <Button type="submit" carregando={salvarMutacao.isPending}>
            Salvar
          </Button>
          <Button variante="secundaria" disabled={salvarMutacao.isPending} onClick={() => void salvar(true)}>
            Pular por agora
          </Button>
        </div>
      </form>
    </div>
  );
}
