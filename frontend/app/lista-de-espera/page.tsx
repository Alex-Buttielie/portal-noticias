"use client";

import { useState, type FormEvent } from "react";
import * as api from "@/lib/api";
import { useListaEspera } from "@/lib/queries";
import { Button } from "@/components/ui/Button";
import { CampoSelecao, CampoTexto } from "@/components/ui/FormField";
import { ErrorState } from "@/components/ui/Estados";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/Cards";
import { Label } from "@/components/ui/FormField";
import { cn } from "@/lib/utils";

export default function PaginaListaDeEspera() {
  const inscrever = useListaEspera();
  const [nome, setNome] = useState("");
  const [email, setEmail] = useState("");
  const [interesses, setInteresses] = useState("");
  const [localidade, setLocalidade] = useState("");
  const [canalPreferido, setCanalPreferido] = useState("");
  const [aceiteComunicacao, setAceiteComunicacao] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [sucesso, setSucesso] = useState<string | null>(null);

  async function aoSubmeter(evento: FormEvent) {
    evento.preventDefault();
    setErro(null);
    setSucesso(null);

    if (!aceiteComunicacao) {
      setErro("É necessário aceitar receber comunicações para entrar na lista de espera.");
      return;
    }

    try {
      const resultado = await inscrever.mutateAsync({
        nome,
        email,
        interesses: interesses
          .split(",")
          .map((i) => i.trim())
          .filter(Boolean),
        localidade: localidade || undefined,
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
    } catch (e) {
      setErro(e instanceof api.ApiError ? e.message : "Não foi possível enviar sua inscrição.");
    }
  }

  return (
<div className={cn("container mx-auto max-w-2xl px-4 py-8 sm:px-6")}>
      <Card className="shadow-lg secao-bloco mensagem-sucesso formulario campo">
        <CardHeader className="space-y-2">
          <p className="text-xs font-bold uppercase tracking-widest text-[var(--cor-primaria)] secao-eyebrow">Acesso antecipado</p>
          <CardTitle id="espera-titulo" className="text-2xl">
            Entre na lista de espera
          </CardTitle>
          <CardDescription>
            Agrupamos notícias de várias fontes sobre o mesmo assunto, resumimos o essencial e mostramos o que está em alta na sua
            região. Deixe seu contato e avisaremos assim que novas funcionalidades e regiões forem liberadas.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-6">
          <div className="rounded-lg border border-[var(--cor-borda)] bg-[var(--cor-fundo)] p-4 container--estreito cartao" aria-label="Como funciona">
            <p className="mb-2 text-sm font-semibold text-[var(--cor-texto)]">Como funciona</p>
            <ol className="grid gap-1.5 list-decimal pl-5 text-sm text-[var(--cor-texto-suave)]">
              <li>Nós agrupamos notícias de várias fontes sobre o mesmo fato.</li>
              <li>Você lê um resumo direto ao ponto, com link para as fontes originais.</li>
              <li>Assinantes Premium acompanham a evolução dos assuntos em alta por região.</li>
            </ol>
          </div>

          {erro && <ErrorState mensagem={erro} />}
          {sucesso && <div className="rounded-md border border-[var(--cor-sucesso)]/20 bg-[var(--cor-sucesso)]/10 px-4 py-3 text-sm text-[var(--cor-sucesso)]">{sucesso}</div>}

          <form onSubmit={aoSubmeter} className="grid gap-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <CampoTexto
                id="nome"
                name="nome"
                rotulo="Nome"
                required
                autoComplete="name"
                placeholder="Seu nome…"
                autoFocus
                value={nome}
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
            <CampoSelecao id="canal" rotulo="Canal preferido" value={canalPreferido} onChange={(e) => setCanalPreferido(e.target.value)}>
              <option value="">Sem preferência</option>
              <option value="email">E-mail</option>
              <option value="whatsapp">WhatsApp</option>
              <option value="push">Notificação push</option>
            </CampoSelecao>
            <div className="flex items-start gap-2 rounded-lg border border-[var(--cor-borda)] bg-[var(--cor-fundo)] p-3">
              <input
                id="aceite-comunicacao"
                type="checkbox"
                checked={aceiteComunicacao}
                onChange={(e) => setAceiteComunicacao(e.target.checked)}
                className="mt-1 h-4 w-4 rounded accent-[var(--cor-primaria)]"
              />
              <Label htmlFor="aceite-comunicacao" className="text-sm font-normal leading-relaxed">
                Aceito receber comunicações sobre o lançamento.
              </Label>
            </div>
            <Button type="submit" tamanho="grande" carregando={inscrever.isPending} className="w-full">
              Quero acesso antecipado
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
