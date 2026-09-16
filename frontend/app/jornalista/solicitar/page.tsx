"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { useToast } from "@/components/ToastProvider";
import * as api from "@/lib/api";
import { useSolicitarCredenciamento } from "@/lib/queries";
import { Button } from "@/components/ui/Button";
import { CampoAreaTexto, CampoTexto } from "@/components/ui/FormField";
import { Label } from "@/components/ui/FormField";
import { Input } from "@/components/ui/FormField";
import { ErrorState } from "@/components/ui/Estados";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/Cards";
import { cn } from "@/lib/utils";

export default function PaginaSolicitarCredenciamento() {
  const router = useRouter();
  const { token, carregando: carregandoAuth } = useAuth();
  const { notificar } = useToast();
  const solicitar = useSolicitarCredenciamento();

  const [telefone, setTelefone] = useState("");
  const [cidade, setCidade] = useState("");
  const [uf, setUf] = useState("");
  const [miniBio, setMiniBio] = useState("");
  const [dadosProfissionais, setDadosProfissionais] = useState("");
  const [documento, setDocumento] = useState<File | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [sucesso, setSucesso] = useState(false);

  useEffect(() => {
    if (!carregandoAuth && !token) {
      router.push("/login");
    }
  }, [carregandoAuth, token, router]);

  async function aoSubmeter(evento: FormEvent) {
    evento.preventDefault();
    setErro(null);

    if (!token) return;
    if (!documento) {
      setErro("Anexe o documento comprobatório (diploma ou registro profissional).");
      return;
    }

    try {
      await solicitar.mutateAsync({
        telefone,
        cidade,
        uf,
        mini_bio: miniBio,
        dados_profissionais: dadosProfissionais,
        documento,
      });
      setSucesso(true);
      notificar("Solicitação de credenciamento enviada.", "sucesso");
    } catch (e) {
      const mensagem = e instanceof api.ApiError ? e.message : "Não foi possível enviar a solicitação.";
      setErro(mensagem);
      notificar(mensagem, "erro");
    }
  }

  if (sucesso) {
    return (
<div className={cn("container mx-auto max-w-lg px-4 py-10 sm:px-6")}>
        <Card className="shadow-lg botao--primaria botao--medio">
          <CardHeader className="space-y-2">
            <p className="text-xs font-bold uppercase tracking-widest text-[var(--cor-sucesso)] secao-eyebrow">Pedido recebido</p>
            <CardTitle id="cred-ok-titulo" className="text-2xl">
              Solicitação enviada
            </CardTitle>
            <CardDescription>Sua solicitação de credenciamento está em análise. Você recebe a resposta em até 24h após o envio de documentação válida.</CardDescription>
          </CardHeader>
          <CardContent>
            <Button asChild tamanho="grande" className="w-full">
              <Link href="/jornalista/status">Acompanhar status</Link>
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
<div className={cn("container mx-auto max-w-2xl px-4 py-8 sm:px-6")}>
      <Card className="shadow-lg secao-bloco formulario campo campo__rotulo campo__dica">
        <CardHeader className="space-y-2">
          <p className="text-xs font-bold uppercase tracking-widest text-[var(--cor-primaria)] secao-eyebrow">Imprensa</p>
          <CardTitle id="cred-titulo" className="text-2xl">
            Solicite seu credenciamento
          </CardTitle>
          <CardDescription>O credenciamento é manual: anexe um documento que comprove sua formação em Jornalismo ou registro profissional equivalente e publique análises na comunidade.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-6">
          {erro && <ErrorState mensagem={erro} />}
          <form onSubmit={aoSubmeter} className="grid gap-4">
            <div className="grid gap-4 sm:grid-cols-2 container--estreito">
              <CampoTexto
                id="telefone"
                name="telefone"
                rotulo="Telefone (opcional)"
                type="tel"
                placeholder="(11) 99999-0000…"
                autoComplete="tel"
                value={telefone}
                onChange={(e) => setTelefone(e.target.value)}
              />
              <CampoTexto
                id="cidade"
                name="cidade"
                rotulo="Cidade"
                placeholder="Onde você atua…"
                autoComplete="address-level2"
                value={cidade}
                onChange={(e) => setCidade(e.target.value)}
              />
            </div>
            <CampoTexto
              id="uf"
              name="uf"
              rotulo="UF"
              maxLength={2}
              placeholder="SP…"
              autoComplete="address-level1"
              value={uf}
              onChange={(e) => setUf(e.target.value.toUpperCase())}
            />
            <CampoAreaTexto
              id="mini-bio"
              rotulo="Mini bio"
              rows={3}
              placeholder="Conte em poucas linhas quem você é…"
              value={miniBio}
              onChange={(e) => setMiniBio(e.target.value)}
            />
            <CampoAreaTexto
              id="dados-profissionais"
              rotulo="Dados profissionais"
              rows={3}
              placeholder="Formação, veículos onde já publicou, etc…"
              value={dadosProfissionais}
              onChange={(e) => setDadosProfissionais(e.target.value)}
            />
            <div className="grid gap-1.5">
              <Label htmlFor="documento">Documento comprobatório (PDF ou imagem)</Label>
              <Input
                id="documento"
                name="documento"
                type="file"
                accept="application/pdf,image/*"
                onChange={(e) => setDocumento(e.target.files?.[0] || null)}
                className="cursor-pointer file:mr-3 file:rounded-md file:border-0 file:bg-[var(--cor-primaria)] file:px-3 file:py-1 file:text-sm file:font-medium file:text-white"
              />
              <p className="text-xs text-[var(--cor-texto-suave)]">Diploma, registro profissional ou equivalente. Enviado via FormData seguro.</p>
            </div>
            <Button type="submit" tamanho="grande" carregando={solicitar.isPending} className="w-full">
              Enviar solicitação
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
