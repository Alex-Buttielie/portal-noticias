"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { useToast } from "@/components/ToastProvider";
import * as api from "@/lib/api";
import { useOnboarding, useSalvarOnboarding } from "@/lib/queries";
import { Button } from "@/components/ui/Button";
import { CampoSelecao, CampoTexto } from "@/components/ui/FormField";
import { ErrorState, LoadingSpinner } from "@/components/ui/Estados";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/Cards";
import { cn } from "@/lib/utils";

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

  if (carregandoAuth || onboarding.isLoading)
    return (
      <div className={cn("container mx-auto max-w-md px-4 py-10")}>
        <LoadingSpinner rotulo="Carregando seu onboarding…" />
      </div>
    );

  if (concluido) {
    return (
<div className={cn("container mx-auto max-w-md px-4 py-10 sm:px-6")}>
        <Card className="shadow-lg botao--primaria botao--medio">
          <CardHeader className="space-y-2">
            <p className="text-xs font-bold uppercase tracking-widest text-[var(--cor-sucesso)] secao-eyebrow">Tudo certo</p>
            <CardTitle id="onboarding-ok-titulo" className="text-2xl">
              Seu feed está pronto
            </CardTitle>
            <CardDescription>Salvamos suas preferências. Boa leitura!</CardDescription>
          </CardHeader>
          <CardContent>
            <Button asChild className="w-full" tamanho="grande">
              <a href="/">Ir para o feed</a>
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (usuario && !usuario.email_verificado) {
    return (
<div className={cn("container mx-auto max-w-md px-4 py-10 sm:px-6")}>
        <Card className="shadow-lg">
          <CardHeader className="space-y-2">
            <p className="text-xs font-bold uppercase tracking-widest text-[var(--cor-erro)] secao-eyebrow">Falta um passo</p>
            <CardTitle id="onboarding-email-titulo" className="text-2xl">
              Confirme seu e-mail
            </CardTitle>
            <CardDescription>
              Você precisa confirmar seu e-mail antes de personalizar o feed. Abra sua caixa de entrada e clique no link de
              confirmação.
            </CardDescription>
          </CardHeader>
        </Card>
      </div>
    );
  }

  return (
<div className={cn("container mx-auto max-w-md px-4 py-10 sm:px-6")}>
      <Card className="shadow-lg secao-bloco formulario">
        <CardHeader className="space-y-2">
          <p className="text-xs font-bold uppercase tracking-widest text-[var(--cor-primaria)] secao-eyebrow texto-suave">Primeiros passos</p>
          <CardTitle id="onboarding-titulo" className="text-2xl">
            Personalize sua experiência
          </CardTitle>
          <CardDescription>Conte do que você gosta e montaremos um feed sob medida. Leva menos de um minuto.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-6">
          {erro && <ErrorState mensagem={erro} />}
          {onboarding.isError && <ErrorState mensagem="Não foi possível carregar o onboarding." aoTentarNovamente={() => void onboarding.refetch()} />}
          <form onSubmit={aoSubmeter} className="grid gap-4">
            <CampoTexto
              id="interesses"
              name="interesses"
              rotulo="Interesses (separados por vírgula)"
              placeholder="política, tecnologia, esportes…"
              autoFocus
              value={interesses}
              onChange={(e) => setInteresses(e.target.value)}
            />
            <CampoTexto
              id="localidade"
              name="localidade"
              rotulo="Localidade de interesse"
              placeholder="Cidade, estado…"
              autoComplete="address-level2"
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
            <div className="flex flex-wrap gap-3 container--estreito">
              <Button type="submit" carregando={salvarMutacao.isPending} className="flex-1 min-w-[160px]">
                Salvar preferências
              </Button>
              <Button variante="secundaria" disabled={salvarMutacao.isPending} onClick={() => void salvar(true)} className="flex-1 min-w-[160px]">
                Pular por agora
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
