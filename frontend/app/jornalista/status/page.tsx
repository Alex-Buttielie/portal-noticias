"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { useToast } from "@/components/ToastProvider";
import * as api from "@/lib/api";
import { useMeuPerfilJornalista, useMinhaSolicitacao, useSalvarPerfilJornalista } from "@/lib/queries";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { CampoAreaTexto } from "@/components/ui/FormField";
import { ErrorState, SkeletonCard } from "@/components/ui/Estados";
import { Card, CardContent, CardDescription, CardHeader } from "@/components/ui/card";

const ROTULOS_STATUS: Record<api.StatusCredenciamento, string> = {
  pendente: "Em análise",
  aprovado: "Aprovado — você é um jornalista credenciado",
  reprovado: "Reprovado",
  info_solicitada: "Informação adicional solicitada",
};

const VARIANTE_STATUS: Record<api.StatusCredenciamento, "secondary" | "success" | "destructive" | "warning"> = {
  pendente: "secondary",
  aprovado: "success",
  reprovado: "destructive",
  info_solicitada: "warning",
};

function formatarData(data: string | null): string {
  if (!data) return "—";
  const d = new Date(data);
  if (Number.isNaN(d.getTime())) return data;
  return new Intl.DateTimeFormat("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric" }).format(d);
}

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
  const [erroPerfil, setErroPerfil] = useState<string | undefined>(undefined);

  useEffect(() => {
    if (!carregandoAuth && !token) {
      router.push("/login");
    }
  }, [carregandoAuth, token, router]);

  if (carregandoAuth || solicitacaoQuery.isLoading) {
    return (
      <div className="mx-auto w-full max-w-xl px-4 py-10">
        <p className="text-sm text-[var(--cor-texto-suave)]">Carregando…</p>
      </div>
    );
  }
  if (solicitacaoQuery.isError) {
    return (
      <div className="mx-auto w-full max-w-xl px-4 py-10">
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
    setErroPerfil(undefined);
    setEditandoPerfil(true);
  }

  async function salvarPerfilHandler(evento: FormEvent) {
    evento.preventDefault();
    if (!token) return;
    if (!miniBioPerfil.trim()) {
      setErroPerfil("Escreva uma mini bio.");
      document.getElementById("mini-bio-perfil")?.focus();
      return;
    }
    setErroPerfil(undefined);
    try {
      await salvarPerfil.mutateAsync({ mini_bio: miniBioPerfil.trim(), dados_profissionais: dadosProfissionaisPerfil.trim() });
      setEditandoPerfil(false);
      notificar("Perfil profissional atualizado.", "sucesso");
    } catch (e) {
      notificar(e instanceof api.ApiError ? e.message : "Não foi possível salvar o perfil.", "erro");
    }
  }

  if (solicitacao === null) {
    return (
      <div className="mx-auto w-full max-w-xl px-4 py-10 sm:px-6">
        <Card>
          <CardHeader>
            <h1 className="font-[var(--fonte-titulo)] text-2xl font-bold tracking-tight text-balance text-[var(--cor-texto)]">
              Credencie-se como jornalista
            </h1>
            <CardDescription>
              Você ainda não pediu credenciamento. Leva poucos minutos e libera a publicação de análises na comunidade.
            </CardDescription>
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
    <div className="mx-auto w-full max-w-2xl px-4 py-8 sm:px-6">
      <Card>
        <CardHeader>
          <h1 className="font-[var(--fonte-titulo)] text-2xl font-bold tracking-tight text-balance text-[var(--cor-texto)]">
            Status do seu credenciamento
          </h1>
          <CardDescription>
            Pedido feito em {formatarData(solicitacao.criado_em)}
            {solicitacao.decidido_em ? ` — decidido em ${formatarData(solicitacao.decidido_em)}` : ""}.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-6">
          <div className="flex flex-col gap-2 rounded-xl border border-[var(--cor-borda)] bg-[var(--cor-fundo)] p-4" aria-live="polite">
            <Badge variant={VARIANTE_STATUS[solicitacao.status]} className="w-fit">
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
            <section className="grid gap-3" aria-labelledby="cred-perfil-titulo">
              <h2 id="cred-perfil-titulo" className="text-base font-semibold text-[var(--cor-texto)]">
                Meu perfil profissional
              </h2>
              <div className="rounded-xl border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-4 shadow-sm">
                {editandoPerfil ? (
                  <form onSubmit={salvarPerfilHandler} noValidate className="grid gap-4">
                    <CampoAreaTexto
                      id="mini-bio-perfil"
                      name="mini-bio-perfil"
                      rotulo="Mini bio"
                      rows={3}
                      value={miniBioPerfil}
                      erro={erroPerfil}
                      onChange={(e) => setMiniBioPerfil(e.target.value)}
                    />
                    <CampoAreaTexto
                      id="dados-profissionais-perfil"
                      name="dados-profissionais-perfil"
                      rotulo="Dados profissionais"
                      rows={3}
                      value={dadosProfissionaisPerfil}
                      onChange={(e) => setDadosProfissionaisPerfil(e.target.value)}
                    />
                    <div className="flex flex-wrap gap-3">
                      <Button type="submit" loading={salvarPerfil.isPending}>
                        Salvar perfil
                      </Button>
                      <Button variante="secundaria" type="button" onClick={() => setEditandoPerfil(false)}>
                        Cancelar
                      </Button>
                    </div>
                  </form>
                ) : (
                  <div className="grid gap-3">
                    <p className="text-sm text-[var(--cor-texto-suave)]">{perfil.mini_bio || "Nenhuma bio cadastrada ainda."}</p>
                    <p className="text-sm text-[var(--cor-texto-suave)]">
                      {perfil.dados_profissionais || "Nenhum dado profissional cadastrado ainda."}
                    </p>
                    <Button variante="secundaria" onClick={iniciarEdicaoPerfil} className="w-fit">
                      Editar perfil
                    </Button>
                  </div>
                )}
              </div>
            </section>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
