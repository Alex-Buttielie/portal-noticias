"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { useToast } from "@/components/ToastProvider";
import * as api from "@/lib/api";
import { useSolicitarCredenciamento } from "@/lib/queries";
import { Button } from "@/components/ui/button";
import { CampoAreaTexto, CampoTexto } from "@/components/ui/FormField";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Card, CardContent, CardDescription, CardHeader } from "@/components/ui/card";
import { CheckCircle2 } from "lucide-react";

interface Erros {
  cidade?: string;
  uf?: string;
  miniBio?: string;
  dadosProfissionais?: string;
  documento?: string;
}

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
  const [erros, setErros] = useState<Erros>({});
  const [erroEnvio, setErroEnvio] = useState<string | null>(null);
  const [sucesso, setSucesso] = useState(false);

  useEffect(() => {
    if (!carregandoAuth && !token) {
      router.push("/login");
    }
  }, [carregandoAuth, token, router]);

  async function aoSubmeter(evento: FormEvent) {
    evento.preventDefault();
    setErroEnvio(null);
    const novos: Erros = {};
    if (!cidade.trim()) novos.cidade = "Informe a cidade onde você atua.";
    if (!uf.trim()) {
      novos.uf = "Informe a UF.";
    } else if (uf.trim().length !== 2) {
      novos.uf = "Use a sigla com 2 letras (ex.: SP).";
    }
    if (!miniBio.trim()) novos.miniBio = "Conte em poucas linhas quem você é.";
    if (!dadosProfissionais.trim()) novos.dadosProfissionais = "Informe formação e veículos onde já publicou.";
    if (!documento) novos.documento = "Anexe o documento comprobatório (diploma ou registro profissional).";
    setErros(novos);
    if (Object.keys(novos).length > 0) {
      const mapa: Record<string, string> = {
        cidade: "cidade",
        uf: "uf",
        miniBio: "mini-bio",
        dadosProfissionais: "dados-profissionais",
        documento: "documento",
      };
      for (const campo of Object.keys(mapa)) {
        if (novos[campo as keyof Erros]) {
          document.getElementById(mapa[campo])?.focus();
          break;
        }
      }
      return;
    }
    if (!token || !documento) return;

    try {
      await solicitar.mutateAsync({
        telefone: telefone.trim(),
        cidade: cidade.trim(),
        uf: uf.trim().toUpperCase(),
        mini_bio: miniBio.trim(),
        dados_profissionais: dadosProfissionais.trim(),
        documento,
      });
      setSucesso(true);
      notificar("Solicitação de credenciamento enviada.", "sucesso");
    } catch (e) {
      const mensagem = e instanceof api.ApiError ? e.message : "Não foi possível enviar a solicitação.";
      setErroEnvio(mensagem);
      notificar(mensagem, "erro");
    }
  }

  if (sucesso) {
    return (
      <div className="mx-auto w-full max-w-xl px-4 py-10 sm:px-6">
        <Card>
          <CardHeader>
            <h1 className="font-[var(--fonte-titulo)] text-2xl font-bold tracking-tight text-balance text-[var(--cor-texto)]">
              Solicitação enviada
            </h1>
            <CardDescription>
              Sua solicitação de credenciamento está em análise. Você recebe a resposta em até 24h após o envio de
              documentação válida.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div aria-live="polite">
              <Alert variant="success">
                <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
                <AlertTitle>Pedido recebido</AlertTitle>
                <AlertDescription>Acompanhe o andamento na página de status.</AlertDescription>
              </Alert>
            </div>
            <Button asChild tamanho="grande" className="mt-4 w-full">
              <Link href="/jornalista/status">Acompanhar status</Link>
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-2xl px-4 py-8 sm:px-6">
      <Card>
        <CardHeader>
          <h1 className="font-[var(--fonte-titulo)] text-2xl font-bold tracking-tight text-balance text-[var(--cor-texto)]">
            Solicite seu credenciamento
          </h1>
          <CardDescription>
            O credenciamento é manual: anexe um documento que comprove sua formação em Jornalismo ou registro
            profissional equivalente e publique análises na comunidade.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-6">
          {erroEnvio && (
            <Alert variant="destructive">
              <AlertTitle>Não foi possível enviar</AlertTitle>
              <AlertDescription>{erroEnvio}</AlertDescription>
            </Alert>
          )}
          <form onSubmit={aoSubmeter} noValidate className="grid gap-4">
            <div className="grid gap-4 sm:grid-cols-2">
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
                erro={erros.cidade}
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
              erro={erros.uf}
              onChange={(e) => setUf(e.target.value.toUpperCase())}
            />
            <CampoAreaTexto
              id="mini-bio"
              name="mini-bio"
              rotulo="Mini bio"
              rows={3}
              placeholder="Conte em poucas linhas quem você é…"
              value={miniBio}
              erro={erros.miniBio}
              onChange={(e) => setMiniBio(e.target.value)}
            />
            <CampoAreaTexto
              id="dados-profissionais"
              name="dados-profissionais"
              rotulo="Dados profissionais"
              rows={3}
              placeholder="Formação, veículos onde já publicou, etc…"
              value={dadosProfissionais}
              erro={erros.dadosProfissionais}
              onChange={(e) => setDadosProfissionais(e.target.value)}
            />
            <div className="grid gap-1.5">
              <Label htmlFor="documento">Documento comprobatório (PDF ou imagem)</Label>
              <Input
                id="documento"
                name="documento"
                type="file"
                accept="application/pdf,image/*"
                aria-invalid={Boolean(erros.documento)}
                aria-describedby={erros.documento ? "documento-erro" : "documento-dica"}
                onChange={(e) => setDocumento(e.target.files?.[0] || null)}
                className="cursor-pointer file:mr-3 file:rounded-md file:border-0 file:bg-[var(--cor-primaria)] file:px-3 file:py-1 file:text-sm file:font-medium file:text-white"
              />
              <p id="documento-dica" className="text-xs text-[var(--cor-texto-suave)]">
                Diploma, registro profissional ou equivalente. Enviado via FormData seguro.
              </p>
              {erros.documento && (
                <p id="documento-erro" role="alert" className="text-xs font-medium text-[var(--cor-erro)]">
                  {erros.documento}
                </p>
              )}
            </div>
            <Button type="submit" tamanho="grande" loading={solicitar.isPending} className="w-full">
              Enviar solicitação
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
