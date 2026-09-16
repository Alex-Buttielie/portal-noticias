"use client";

import { useState, type FormEvent } from "react";
import * as api from "@/lib/api";
import { useListaEspera } from "@/lib/queries";
import { Button } from "@/components/ui/button";
import { CampoSelecao, CampoTexto } from "@/components/ui/FormField";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Card, CardContent, CardDescription, CardHeader } from "@/components/ui/card";
import { CheckCircle2 } from "lucide-react";

interface Erros {
  nome?: string;
  email?: string;
  aceite?: string;
}

export default function PaginaListaDeEspera() {
  const inscrever = useListaEspera();
  const [nome, setNome] = useState("");
  const [email, setEmail] = useState("");
  const [interesses, setInteresses] = useState("");
  const [localidade, setLocalidade] = useState("");
  const [canalPreferido, setCanalPreferido] = useState("");
  const [aceiteComunicacao, setAceiteComunicacao] = useState(false);
  const [erros, setErros] = useState<Erros>({});
  const [erroEnvio, setErroEnvio] = useState<string | null>(null);
  const [sucesso, setSucesso] = useState<string | null>(null);

  async function aoSubmeter(evento: FormEvent) {
    evento.preventDefault();
    setErroEnvio(null);
    setSucesso(null);
    const novos: Erros = {};
    if (!nome.trim()) novos.nome = "Conte pra gente o seu nome.";
    if (!email.trim()) {
      novos.email = "Informe seu e-mail.";
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
      novos.email = "Esse e-mail parece inválido.";
    }
    if (!aceiteComunicacao) {
      novos.aceite = "É necessário aceitar receber comunicações para entrar na lista de espera.";
    }
    setErros(novos);
    const primeira = (["nome", "email", "aceite-comunicacao"] as const)[["nome", "email", "aceite"].findIndex((c) => novos[c as keyof Erros])];
    if (Object.keys(novos).length > 0) {
      if (primeira) document.getElementById(primeira)?.focus();
      return;
    }

    try {
      const resultado = await inscrever.mutateAsync({
        nome: nome.trim(),
        email: email.trim(),
        interesses: interesses
          .split(",")
          .map((i) => i.trim())
          .filter(Boolean),
        localidade: localidade.trim() || undefined,
        canal_preferido: canalPreferido || undefined,
        aceite_comunicacao: aceiteComunicacao,
      });
      setSucesso(resultado.detail || "Inscrição realizada! Avisaremos você em breve.");
      setNome("");
      setEmail("");
      setInteresses("");
      setLocalidade("");
      setCanalPreferido("");
      setAceiteComunicacao(false);
      setErros({});
    } catch (e) {
      setErroEnvio(e instanceof api.ApiError ? e.message : "Não foi possível enviar sua inscrição.");
    }
  }

  return (
    <div className="mx-auto w-full max-w-2xl px-4 py-8 sm:px-6">
      <Card>
        <CardHeader>
          <h1 className="font-[var(--fonte-titulo)] text-2xl font-bold tracking-tight text-balance text-[var(--cor-texto)]">
            Entre na lista de espera
          </h1>
          <CardDescription>
            Agrupamos notícias de várias fontes sobre o mesmo assunto, resumimos o essencial e mostramos o que está
            em alta na sua região. Deixe seu contato e avisaremos assim que novas funcionalidades e regiões forem
            liberadas.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-6">
          <div className="rounded-lg border border-[var(--cor-borda)] bg-[var(--cor-fundo)] p-4" aria-label="Como funciona">
            <p className="mb-2 text-sm font-semibold text-[var(--cor-texto)]">Como funciona</p>
            <ol className="grid list-decimal gap-1.5 pl-5 text-sm text-[var(--cor-texto-suave)]">
              <li>Nós agrupamos notícias de várias fontes sobre o mesmo fato.</li>
              <li>Você lê um resumo direto ao ponto, com link para as fontes originais.</li>
              <li>Assinantes Premium acompanham a evolução dos assuntos em alta por região.</li>
            </ol>
          </div>

          <div aria-live="polite">
            {erroEnvio && (
              <Alert variant="destructive">
                <AlertTitle>Não foi possível enviar</AlertTitle>
                <AlertDescription>{erroEnvio}</AlertDescription>
              </Alert>
            )}
            {sucesso && (
              <Alert variant="success">
                <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
                <AlertTitle>Inscrição recebida</AlertTitle>
                <AlertDescription>{sucesso}</AlertDescription>
              </Alert>
            )}
          </div>

          <form onSubmit={aoSubmeter} noValidate className="grid gap-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <CampoTexto
                id="nome"
                name="nome"
                rotulo="Nome"
                required
                autoComplete="name"
                placeholder="Seu nome…"
                value={nome}
                erro={erros.nome}
                onChange={(e) => setNome(e.target.value)}
              />
              <CampoTexto
                id="email"
                name="email"
                rotulo="E-mail"
                type="email"
                required
                autoComplete="email"
                placeholder="voce@exemplo.com…"
                value={email}
                erro={erros.email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>
            <CampoTexto
              id="interesses"
              name="interesses"
              rotulo="Interesses (separados por vírgula)"
              placeholder="política, tecnologia, esportes…"
              value={interesses}
              onChange={(e) => setInteresses(e.target.value)}
            />
            <CampoTexto
              id="localidade"
              name="localidade"
              rotulo="Localidade"
              placeholder="cidade, estado ou país…"
              autoComplete="address-level2"
              value={localidade}
              onChange={(e) => setLocalidade(e.target.value)}
            />
            <CampoSelecao
              id="canal"
              name="canal"
              rotulo="Canal preferido"
              value={canalPreferido}
              onChange={(e) => setCanalPreferido(e.target.value)}
            >
              <option value="">Sem preferência</option>
              <option value="email">E-mail</option>
              <option value="whatsapp">WhatsApp</option>
              <option value="push">Notificação push</option>
            </CampoSelecao>
            <div className="flex items-start gap-3 rounded-lg border border-[var(--cor-borda)] bg-[var(--cor-fundo)] p-3">
              <Checkbox
                id="aceite-comunicacao"
                checked={aceiteComunicacao}
                onCheckedChange={(v) => setAceiteComunicacao(v === true)}
                aria-describedby={erros.aceite ? "aceite-comunicacao-erro" : undefined}
                aria-invalid={Boolean(erros.aceite)}
              />
              <div className="grid gap-1">
                <Label htmlFor="aceite-comunicacao" className="text-sm font-normal leading-relaxed">
                  Aceito receber comunicações sobre o lançamento.
                </Label>
                {erros.aceite && (
                  <p id="aceite-comunicacao-erro" role="alert" className="text-xs font-medium text-[var(--cor-erro)]">
                    {erros.aceite}
                  </p>
                )}
              </div>
            </div>
            <Button type="submit" tamanho="grande" loading={inscrever.isPending} className="w-full">
              Quero acesso antecipado
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
