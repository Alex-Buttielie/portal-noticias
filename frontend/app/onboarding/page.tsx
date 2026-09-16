"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { useToast } from "@/components/ToastProvider";
import * as api from "@/lib/api";
import { useOnboarding, useSalvarOnboarding } from "@/lib/queries";
import { Button } from "@/components/ui/button";
import { CampoTexto } from "@/components/ui/FormField";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Card, CardContent, CardDescription, CardHeader } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { ErrorState, LoadingSpinner } from "@/components/ui/Estados";
import { CheckCircle2 } from "lucide-react";
import { cn } from "@/lib/utils";

const TEMAS_SUGERIDOS = [
  "política",
  "economia",
  "tecnologia",
  "esportes",
  "cultura",
  "saúde",
  "educação",
  "meio ambiente",
  "mundo",
  "Brasil",
];

const LOCALIDADES_SUGERIDAS = [
  "São Paulo, SP",
  "Rio de Janeiro, RJ",
  "Belo Horizonte, MG",
  "Brasília, DF",
  "Salvador, BA",
  "Curitiba, PR",
  "Porto Alegre, RS",
  "Recife, PE",
];

const PASSOS = [
  { numero: 1, titulo: "Interesses", descricao: "Escolha os temas que você acompanha." },
  { numero: 2, titulo: "Localidade", descricao: "Diga de onde você quer ver notícias." },
  { numero: 3, titulo: "Canal", descricao: "Escolha como receber os destaques." },
];

export default function PaginaOnboarding() {
  const router = useRouter();
  const { token, usuario, carregando: carregandoAuth } = useAuth();
  const { notificar } = useToast();
  const onboarding = useOnboarding();
  const salvarMutacao = useSalvarOnboarding();

  const [passo, setPasso] = useState(1);
  const [selecionados, setSelecionados] = useState<string[]>([]);
  const [interessesLivres, setInteressesLivres] = useState("");
  const [localidade, setLocalidade] = useState("");
  const [localidadeOutra, setLocalidadeOutra] = useState("");
  const [canalPreferido, setCanalPreferido] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [erroPasso, setErroPasso] = useState<string | undefined>(undefined);
  const [concluido, setConcluido] = useState(false);

  useEffect(() => {
    if (!carregandoAuth && !token) {
      router.push("/login");
    }
  }, [carregandoAuth, token, router]);

  useEffect(() => {
    const dados = onboarding.data;
    if (dados) {
      const salvos = dados.interesses ?? [];
      setSelecionados(salvos.filter((i) => TEMAS_SUGERIDOS.includes(i)));
      setInteressesLivres(salvos.filter((i) => !TEMAS_SUGERIDOS.includes(i)).join(", "));
      setLocalidade(dados.localidade || "");
      if (dados.localidade && !LOCALIDADES_SUGERIDAS.includes(dados.localidade)) {
        setLocalidade("outra");
        setLocalidadeOutra(dados.localidade);
      }
      setCanalPreferido(dados.canal_preferido || "");
    }
  }, [onboarding.data]);

  function interessesFinais(): string[] {
    const livres = interessesLivres
      .split(",")
      .map((i) => i.trim())
      .filter(Boolean);
    return [...new Set([...selecionados, ...livres])];
  }

  function localidadeFinal(): string {
    return localidade === "outra" ? localidadeOutra.trim() : localidade;
  }

  function alternarTema(tema: string, marcado: boolean) {
    setSelecionados((atual) => (marcado ? [...atual, tema] : atual.filter((t) => t !== tema)));
  }

  function validarPasso(passoAtual: number): boolean {
    if (passoAtual === 1 && interessesFinais().length === 0) {
      setErroPasso("Escolha ao menos um tema ou escreva seus interesses.");
      document.getElementById("interesses-livres")?.focus();
      return false;
    }
    if (passoAtual === 2 && localidade === "outra" && !localidadeOutra.trim()) {
      setErroPasso("Digite sua localidade.");
      document.getElementById("localidade-outra")?.focus();
      return false;
    }
    setErroPasso(undefined);
    return true;
  }

  function avancar() {
    if (!validarPasso(passo)) return;
    setPasso((p) => Math.min(3, p + 1));
  }

  async function salvar(pular: boolean) {
    if (!token) return;
    setErro(null);
    try {
      await salvarMutacao.mutateAsync({
        interesses: pular ? [] : interessesFinais(),
        localidade: pular ? "" : localidadeFinal(),
        canal_preferido: pular || !canalPreferido ? undefined : canalPreferido,
        pular,
      });
      setConcluido(true);
      notificar(pular ? "Onboarding pulado. Você pode ajustar depois." : "Preferências salvas.", "sucesso");
    } catch (e) {
      setErro(e instanceof api.ApiError ? e.message : "Não foi possível salvar.");
    }
  }

  if (carregandoAuth || onboarding.isLoading) {
    return (
      <div className="mx-auto w-full max-w-xl px-4 py-10">
        <LoadingSpinner rotulo="Carregando seu onboarding…" />
      </div>
    );
  }

  if (concluido) {
    return (
      <div className="mx-auto w-full max-w-xl px-4 py-10 sm:px-6">
        <Card>
          <CardHeader>
            <h1 className="font-[var(--fonte-titulo)] text-2xl font-bold tracking-tight text-balance text-[var(--cor-texto)]">
              Seu feed está pronto
            </h1>
            <CardDescription>Salvamos suas preferências. Boa leitura!</CardDescription>
          </CardHeader>
          <CardContent>
            <div aria-live="polite">
              <Alert variant="success">
                <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
                <AlertTitle>Tudo certo</AlertTitle>
                <AlertDescription>Suas escolhas já valem para o feed e a newsletter.</AlertDescription>
              </Alert>
            </div>
            <Button asChild tamanho="grande" className="mt-4 w-full">
              <a href="/">Ir para o feed</a>
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (usuario && !usuario.email_verificado) {
    return (
      <div className="mx-auto w-full max-w-xl px-4 py-10 sm:px-6">
        <Card>
          <CardHeader>
            <h1 className="font-[var(--fonte-titulo)] text-2xl font-bold tracking-tight text-balance text-[var(--cor-texto)]">
              Confirme seu e-mail
            </h1>
            <CardDescription>
              Você precisa confirmar seu e-mail antes de personalizar o feed. Abra sua caixa de entrada e clique no
              link de confirmação.
            </CardDescription>
          </CardHeader>
        </Card>
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-xl px-4 py-10 sm:px-6">
      <Card>
        <CardHeader>
          <h1 className="font-[var(--fonte-titulo)] text-2xl font-bold tracking-tight text-balance text-[var(--cor-texto)]">
            Personalize sua experiência
          </h1>
          <CardDescription>Conte do que você gosta e montaremos um feed sob medida. Leva menos de um minuto.</CardDescription>
          <ol className="mt-4 flex items-center gap-2" aria-label="Etapas do onboarding">
            {PASSOS.map((p) => (
              <li key={p.numero} className="flex flex-1 items-center gap-2" aria-current={passo === p.numero ? "step" : undefined}>
                <span
                  className={cn(
                    "flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-sm font-bold",
                    passo === p.numero
                      ? "bg-[var(--cor-primaria)] text-white"
                      : passo > p.numero
                        ? "bg-[var(--cor-sucesso)] text-white"
                        : "border border-[var(--cor-borda)] bg-[var(--cor-fundo)] text-[var(--cor-texto-suave)]"
                  )}
                  aria-hidden="true"
                >
                  {p.numero}
                </span>
                <span className={cn("hidden text-xs font-medium sm:block", passo === p.numero ? "text-[var(--cor-texto)]" : "text-[var(--cor-texto-suave)]")}>
                  Passo {p.numero}: {p.titulo}
                </span>
                {p.numero < 3 && <span className="h-px flex-1 bg-[var(--cor-borda)]" aria-hidden="true" />}
              </li>
            ))}
          </ol>
        </CardHeader>
        <CardContent className="grid gap-6">
          {erro && (
            <Alert variant="destructive">
              <AlertTitle>Não foi possível salvar</AlertTitle>
              <AlertDescription>{erro}</AlertDescription>
            </Alert>
          )}
          {onboarding.isError && (
            <ErrorState mensagem="Não foi possível carregar o onboarding." aoTentarNovamente={() => void onboarding.refetch()} />
          )}

          <h2 className="font-[var(--fonte-titulo)] text-lg font-bold text-[var(--cor-texto)]">
            Passo {passo} de 3 — {PASSOS[passo - 1].titulo}
          </h2>
          <p className="text-sm text-[var(--cor-texto-suave)]">{PASSOS[passo - 1].descricao}</p>

          {passo === 1 && (
            <Tabs defaultValue="sugeridos" className="grid gap-4">
              <TabsList aria-label="Como escolher interesses">
                <TabsTrigger value="sugeridos">Temas sugeridos</TabsTrigger>
                <TabsTrigger value="livres">Escrever os meus</TabsTrigger>
              </TabsList>
              <TabsContent value="sugeridos">
                <fieldset className="grid gap-2">
                  <legend className="text-sm font-medium text-[var(--cor-texto)]">Marque os temas que você acompanha</legend>
                  <div className="flex flex-wrap gap-2">
                    {TEMAS_SUGERIDOS.map((tema) => {
                      const marcado = selecionados.includes(tema);
                      return (
                        <label
                          key={tema}
                          className={cn(
                            "inline-flex min-h-[44px] cursor-pointer touch-manipulation items-center gap-2 rounded-full border px-4 py-2 text-sm font-medium",
                            "focus-within:ring-2 focus-within:ring-[var(--cor-foco)] focus-within:ring-offset-2",
                            marcado
                              ? "border-[var(--cor-primaria)] bg-[var(--cor-primaria)] text-white"
                              : "border-[var(--cor-borda)] bg-[var(--cor-fundo)] text-[var(--cor-texto)]"
                          )}
                        >
                          <Checkbox
                            checked={marcado}
                            onCheckedChange={(v) => alternarTema(tema, v === true)}
                            aria-label={tema}
                            className="sr-only"
                          />
                          {tema}
                        </label>
                      );
                    })}
                  </div>
                </fieldset>
              </TabsContent>
              <TabsContent value="livres">
                <CampoTexto
                  id="interesses-livres"
                  name="interesses"
                  rotulo="Interesses (separados por vírgula)"
                  placeholder="política, tecnologia, esportes…"
                  value={interessesLivres}
                  erro={erroPasso}
                  onChange={(e) => setInteressesLivres(e.target.value)}
                />
              </TabsContent>
            </Tabs>
          )}

          {passo === 2 && (
            <div className="grid gap-4">
              <div className="grid gap-1.5">
                <Label htmlFor="localidade">Localidade de interesse</Label>
                <Select value={localidade || undefined} onValueChange={(v) => setLocalidade(v === "nenhuma" ? "" : v)}>
                  <SelectTrigger id="localidade" className="text-[16px] sm:text-sm">
                    <SelectValue placeholder="Selecione uma localidade…" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="nenhuma">Sem localidade específica</SelectItem>
                    {LOCALIDADES_SUGERIDAS.map((l) => (
                      <SelectItem key={l} value={l}>
                        {l}
                      </SelectItem>
                    ))}
                    {localidade && !LOCALIDADES_SUGERIDAS.includes(localidade) && localidade !== "outra" && (
                      <SelectItem value={localidade}>{localidade}</SelectItem>
                    )}
                    <SelectItem value="outra">Outra…</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              {localidade === "outra" && (
                <CampoTexto
                  id="localidade-outra"
                  name="localidade-outra"
                  rotulo="Digite sua localidade"
                  autoComplete="address-level2"
                  placeholder="Cidade, estado…"
                  value={localidadeOutra}
                  erro={erroPasso}
                  onChange={(e) => setLocalidadeOutra(e.target.value)}
                />
              )}
            </div>
          )}

          {passo === 3 && (
            <RadioGroup value={canalPreferido} onValueChange={setCanalPreferido} aria-label="Canal preferido" className="grid gap-2">
              <div className="flex min-h-[44px] items-center gap-3 rounded-lg border border-[var(--cor-borda)] p-3">
                <RadioGroupItem value="email" id="canal-email" />
                <Label htmlFor="canal-email" className="flex-1 cursor-pointer text-sm font-normal">
                  E-mail — resumo diário na sua caixa de entrada
                </Label>
              </div>
              <div className="flex min-h-[44px] items-center gap-3 rounded-lg border border-[var(--cor-borda)] p-3">
                <RadioGroupItem value="push" id="canal-push" />
                <Label htmlFor="canal-push" className="flex-1 cursor-pointer text-sm font-normal">
                  Notificação push — alertas no navegador
                </Label>
              </div>
            </RadioGroup>
          )}

          {passo === 1 && erroPasso && !interessesLivres && (
            <p role="alert" className="text-xs font-medium text-[var(--cor-erro)]">
              {erroPasso}
            </p>
          )}

          <div className="flex flex-wrap gap-3" aria-live="polite">
            {passo > 1 && (
              <Button variante="secundaria" onClick={() => { setErroPasso(undefined); setPasso((p) => p - 1); }} disabled={salvarMutacao.isPending}>
                Voltar
              </Button>
            )}
            {passo < 3 ? (
              <Button onClick={avancar} className="flex-1">
                Continuar
              </Button>
            ) : (
              <Button loading={salvarMutacao.isPending} onClick={() => { if (validarPasso(3)) void salvar(false); }} className="flex-1">
                Salvar preferências
              </Button>
            )}
            <Button variante="secundaria" disabled={salvarMutacao.isPending} onClick={() => void salvar(true)}>
              Pular por agora
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
