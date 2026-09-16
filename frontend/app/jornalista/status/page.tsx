"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { useToast } from "@/components/ToastProvider";
import * as api from "@/lib/api";
import { useMeuPerfilJornalista, useMinhaSolicitacao, useSalvarPerfilJornalista } from "@/lib/queries";
import Badge from "@/components/Badge";
import { Button } from "@/components/ui/Button";
import { CampoAreaTexto } from "@/components/ui/FormField";
import { ErrorState, SkeletonCard } from "@/components/ui/Estados";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/Cards";
import { cn } from "@/lib/utils";

const ROTULOS_STATUS: Record<api.StatusCredenciamento, string> = {
  pendente: "Em análise",
  aprovado: "Aprovado — você é um jornalista credenciado",
  reprovado: "Reprovado",
  info_solicitada: "Informação adicional solicitada",
};

export default function PaginaStatusCredenciamento() {
  const router = useRouter();
  const { token, carregando: carregandoAuth } = useAuth();
  const { notificar } = useToast();
  const solicitacaoQuery = useMinhaSolicitacao();
  const perfilQuery = useMeuPerfilJornalista();
  const salvarPerfil = useSalvarPerfilJornalista();

  const [editandoPerfil, setEditandoPerfil] = useState(false);
  const [miniBioPerfil, setMiniBioPerfil] = useState("");
  const [dadosProfissionaisPerfil, setDadosProfissionaisPerfil] = useState("");

  useEffect(() => {
    if (!carregandoAuth && !token) {
      router.push("/login");
    }
  }, [carregandoAuth, token, router]);

  if (carregandoAuth || solicitacaoQuery.isLoading)
    return (
      <div className={cn("container mx-auto max-w-lg px-4 py-10")}>
        <p className="text-sm text-[var(--cor-texto-suave)]">Carregando…</p>
      </div>
    );
  if (solicitacaoQuery.isError) {
    return (
      <div className={cn("container mx-auto max-w-lg px-4 py-10")}>
        <ErrorState mensagem="Não foi possível carregar sua solicitação." aoTentarNovamente={() => void solicitacaoQuery.refetch()} />
      </div>
    );
  }

  const solicitacao = solicitacaoQuery.data ?? null;
  const perfil = perfilQuery.data ?? null;

  function iniciarEdicaoPerfil() {
    if (!perfil) return;
    setMiniBioPerfil(perfil.mini_bio);
    setDadosProfissionaisPerfil(perfil.dados_profissionais);
    setEditandoPerfil(true);
  }

  async function salvarPerfilHandler(evento: FormEvent) {
    evento.preventDefault();
    if (!token) return;
    try {
      await salvarPerfil.mutateAsync({ mini_bio: miniBioPerfil, dados_profissionais: dadosProfissionaisPerfil });
      setEditandoPerfil(false);
      notificar("Perfil profissional atualizado.", "sucesso");
    } catch (e) {
      notificar(e instanceof api.ApiError ? e.message : "Não foi possível salvar o perfil.", "erro");
    }
  }

  if (solicitacao === null) {
    return (
<div className={cn("container mx-auto max-w-lg px-4 py-10 sm:px-6")}>
        <Card className="shadow-lg">
          <CardHeader className="space-y-2">
            <p className="text-xs font-bold uppercase tracking-widest text-[var(--cor-primaria)] secao-eyebrow">Imprensa</p>
            <CardTitle id="cred-vazio-titulo" className="text-2xl">Credencie-se como jornalista</CardTitle>
            <CardDescription>Você ainda não pediu credenciamento. Leva poucos minutos e libera a publicação de análises na comunidade.</CardDescription>
          </CardHeader>
          <CardContent>
            <Button asChild tamanho="grande" className="w-full">
              <Link href="/jornalista/solicitar">Solicitar agora</Link>
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
<div className={cn("container mx-auto max-w-2xl px-4 py-8 sm:px-6")}>
      <Card className="shadow-lg secao-bloco botao botao--primaria botao--medio secao-titulo formulario">
        <CardHeader className="space-y-2">
          <p className="text-xs font-bold uppercase tracking-widest text-[var(--cor-primaria)] secao-eyebrow">Imprensa</p>
          <CardTitle id="cred-status-titulo" className="text-2xl">Status do seu credenciamento</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-6">
          <div className="flex flex-col gap-2 rounded-xl border border-[var(--cor-borda)] bg-[var(--cor-fundo)] p-4 container--estreito cartao secao-cabecalho">
            <Badge variante={solicitacao.status === "aprovado" ? "sucesso" : solicitacao.status === "reprovado" ? "erro" : "neutro"}>
              {ROTULOS_STATUS[solicitacao.status]}
            </Badge>
            {solicitacao.motivo_decisao && <p className="text-sm text-[var(--cor-texto-suave)]">{solicitacao.motivo_decisao}</p>}
          </div>
          {solicitacao.status === "aprovado" && (
            <Button asChild tamanho="grande" className="w-fit">
              <Link href="/comunidade/nova">Escrever uma análise</Link>
            </Button>
          )}
          {perfilQuery.isLoading && <SkeletonCard />}
          {perfil && (
            <div className="grid gap-3">
              <h2 id="cred-perfil-titulo" className="text-base font-semibold text-[var(--cor-texto)]">Meu perfil profissional</h2>
              <div className="rounded-xl border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] p-4 shadow-sm">
                {editandoPerfil ? (
                  <form onSubmit={salvarPerfilHandler} className="grid gap-4">
                    <CampoAreaTexto id="mini-bio-perfil" rotulo="Mini bio" rows={3} value={miniBioPerfil} onChange={(e) => setMiniBioPerfil(e.target.value)} />
                    <CampoAreaTexto id="dados-profissionais-perfil" rotulo="Dados profissionais" rows={3} value={dadosProfissionaisPerfil} onChange={(e) => setDadosProfissionaisPerfil(e.target.value)} />
                    <div className="flex flex-wrap gap-3">
                      <Button type="submit" carregando={salvarPerfil.isPending}>Salvar perfil</Button>
                      <Button variante="secundaria" type="button" onClick={() => setEditandoPerfil(false)}>Cancelar</Button>
                    </div>
                  </form>
                ) : (
                  <div className="grid gap-3">
                    <p className="text-sm text-[var(--cor-texto-suave)]">{perfil.mini_bio || "Nenhuma bio cadastrada ainda."}</p>
                    <p className="text-sm text-[var(--cor-texto-suave)]">{perfil.dados_profissionais || "Nenhum dado profissional cadastrado ainda."}</p>
                    <Button variante="secundaria" onClick={iniciarEdicaoPerfil} className="w-fit">Editar perfil</Button>
                  </div>
                )}
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
