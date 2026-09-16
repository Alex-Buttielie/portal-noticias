"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { useToast } from "@/components/ToastProvider";
import * as api from "@/lib/api";
import {
  useConvidarMembroB2B,
  useCriarCriterioB2B,
  useExcluirCriterioB2B,
  usePainelB2B,
  useRemoverMembroB2B,
} from "@/lib/queries";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { CampoSelecao, CampoTexto } from "@/components/ui/FormField";
import { DataTable, StatCard } from "@/components/ui/Data";
import { EmptyState, ErrorState, SkeletonLista } from "@/components/ui/Estados";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

const ROTULOS_TIPO: Record<api.TipoCriterioMonitoramento, string> = {
  empresa: "Empresa",
  concorrente: "Concorrente",
  setor: "Setor",
  palavra_chave: "Palavra-chave",
};

export default function PaginaEmpresa() {
  const router = useRouter();
  const { token, usuario, carregando: carregandoAuth } = useAuth();
  const { notificar } = useToast();
  const painel = usePainelB2B();
  const criarCriterio = useCriarCriterioB2B(painel.recarregar);
  const excluirCriterio = useExcluirCriterioB2B(painel.recarregar);
  const convidar = useConvidarMembroB2B(painel.recarregar);
  const remover = useRemoverMembroB2B(painel.recarregar);

  const [tipoCriterio, setTipoCriterio] = useState<api.TipoCriterioMonitoramento>("palavra_chave");
  const [valorCriterio, setValorCriterio] = useState("");
  const [erroCriterio, setErroCriterio] = useState<string | undefined>(undefined);
  const [emailConvite, setEmailConvite] = useState("");
  const [erroConvite, setErroConvite] = useState<string | null>(null);
  const [criterioAlvo, setCriterioAlvo] = useState<api.CriterioMonitoramento | null>(null);
  const [membroAlvo, setMembroAlvo] = useState<string | null>(null);

  useEffect(() => {
    if (!carregandoAuth && !token) {
      router.push("/login");
    }
  }, [carregandoAuth, token, router]);

  if (carregandoAuth) {
    return (
      <div className="mx-auto w-full max-w-5xl px-4 py-10">
        <p className="text-sm text-[var(--cor-texto-suave)]">Carregando…</p>
      </div>
    );
  }

  const carregando =
    painel.criterios.isLoading || painel.itens.isLoading || painel.resumo.isLoading || painel.membros.isLoading;
  const erroQuery =
    painel.criterios.error ?? painel.itens.error ?? painel.resumo.error ?? painel.membros.error;
  const semOrganizacao = erroQuery instanceof api.ApiError && erroQuery.status === 403;

  const criterios = painel.criterios.data ?? [];
  const itensMonitorados = painel.itens.data ?? {};
  const resumo = painel.resumo.data ?? null;
  const membros = painel.membros.data ?? [];

  async function aoCriarCriterio(evento: FormEvent) {
    evento.preventDefault();
    if (!token) return;
    if (!valorCriterio.trim()) {
      setErroCriterio("Digite o valor a monitorar.");
      document.getElementById("valor-criterio")?.focus();
      return;
    }
    setErroCriterio(undefined);
    try {
      await criarCriterio.mutateAsync({ tipo: tipoCriterio, valor: valorCriterio.trim() });
      setValorCriterio("");
      notificar("Critério adicionado.", "sucesso");
    } catch (e) {
      notificar(e instanceof api.ApiError ? e.message : "Não foi possível criar o critério.", "erro");
    }
  }

  async function aoConvidar(evento: FormEvent) {
    evento.preventDefault();
    if (!token) return;
    setErroConvite(null);
    if (!emailConvite.trim()) {
      setErroConvite("Informe o e-mail do convidado.");
      document.getElementById("email-convite")?.focus();
      return;
    }
    try {
      await convidar.mutateAsync(emailConvite.trim());
      setEmailConvite("");
      notificar("Convite enviado.", "sucesso");
    } catch (e) {
      setErroConvite(e instanceof api.ApiError ? e.message : "Não foi possível convidar este usuário.");
    }
  }

  async function confirmarRemoverCriterio() {
    if (!criterioAlvo) return;
    try {
      await excluirCriterio.mutateAsync(criterioAlvo.id);
      notificar("Critério removido.", "info");
      setCriterioAlvo(null);
    } catch (e) {
      notificar(e instanceof api.ApiError ? e.message : "Não foi possível remover o critério.", "erro");
    }
  }

  async function confirmarRemoverMembro() {
    if (!membroAlvo || !token) return;
    try {
      await remover.mutateAsync(membroAlvo);
      notificar("Membro removido.", "info");
      setMembroAlvo(null);
    } catch (e) {
      notificar(e instanceof api.ApiError ? e.message : "Não foi possível remover este membro.", "erro");
    }
  }

  const souAdmin = membros.some((m) => m.email === usuario?.email && m.papel_na_organizacao === "admin_organizacao");

  return (
    <div className="mx-auto w-full max-w-5xl px-4 py-8 sm:px-6">
      <div className="mb-8 grid gap-2">
        <h1 className="font-[var(--fonte-titulo)] text-3xl font-bold tracking-tight text-balance text-[var(--cor-texto)]">
          Painel da empresa
        </h1>
        <p className="max-w-2xl text-sm text-[var(--cor-texto-suave)]">Acompanhe o que sai na imprensa sobre sua marca, seus concorrentes e seu setor.</p>
      </div>

      {carregando && <SkeletonLista quantidade={3} />}
      {erroQuery && (
        <ErrorState
          mensagem={semOrganizacao ? "Sua conta não pertence a nenhuma organização corporativa." : "Não foi possível carregar o painel da empresa."}
          aoTentarNovamente={() => painel.recarregar()}
        />
      )}

      {!carregando && !erroQuery && (
        <div className="grid gap-6">
          {resumo && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">{resumo.organizacao}</CardTitle>
                <CardDescription>Resumo dos últimos 30 dias por critério.</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  {resumo.criterios.map((c) => (
                    <StatCard key={`${c.tipo}-${c.valor}`} rotulo={`${ROTULOS_TIPO[c.tipo]}: ${c.valor}`} valor={`${c.numero_itens} itens`} detalhe="nos últimos 30 dias" />
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          <Tabs defaultValue="criterios" className="grid gap-6">
            <TabsList aria-label="Seções do painel da empresa">
              <TabsTrigger value="criterios">Critérios ({criterios.length})</TabsTrigger>
              <TabsTrigger value="membros">Membros ({membros.length})</TabsTrigger>
            </TabsList>

            <TabsContent value="criterios">
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Critérios de monitoramento</CardTitle>
                  <CardDescription>Adicione marcas, concorrentes, setores ou palavras-chave.</CardDescription>
                </CardHeader>
                <CardContent className="grid gap-6">
                  <form onSubmit={aoCriarCriterio} noValidate className="flex flex-wrap items-end gap-3 rounded-lg border border-[var(--cor-borda)] bg-[var(--cor-fundo)] p-4">
                    <div className="min-w-[160px] flex-1">
                      <CampoSelecao
                        id="tipo-criterio"
                        name="tipo-criterio"
                        rotulo="Tipo"
                        value={tipoCriterio}
                        onChange={(e) => setTipoCriterio(e.target.value as api.TipoCriterioMonitoramento)}
                      >
                        {Object.entries(ROTULOS_TIPO).map(([valor, rotulo]) => (
                          <option key={valor} value={valor}>
                            {rotulo}
                          </option>
                        ))}
                      </CampoSelecao>
                    </div>
                    <div className="min-w-[200px] flex-1">
                      <CampoTexto
                        id="valor-criterio"
                        name="valor-criterio"
                        rotulo="Valor a monitorar"
                        placeholder="Nome da empresa, tema…"
                        value={valorCriterio}
                        erro={erroCriterio}
                        onChange={(e) => setValorCriterio(e.target.value)}
                      />
                    </div>
                    <Button type="submit" loading={criarCriterio.isPending} className="h-10">
                      Adicionar critério
                    </Button>
                  </form>

                  {criterios.length === 0 && <EmptyState titulo="Nenhum critério configurado" descricao="Adicione o primeiro critério acima." />}
                  <ul className="grid gap-4">
                    {criterios.map((c) => {
                      const grupo = itensMonitorados[String(c.id)];
                      return (
                        <li key={c.id} className="rounded-xl border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-4 shadow-sm">
                          <div className="flex flex-wrap items-center gap-2">
                            <Badge variant="secondary">{ROTULOS_TIPO[c.tipo]}</Badge>
                            <span className="text-sm font-medium text-[var(--cor-texto)]">{c.valor}</span>
                            {!c.ativo && <Badge variant="destructive">Inativo</Badge>}
                            <span className="ml-auto">
                              <Button variante="fantasma" tamanho="pequeno" loading={excluirCriterio.isPending} onClick={() => setCriterioAlvo(c)}>
                                Remover
                              </Button>
                            </span>
                          </div>
                          {grupo && grupo.itens.length > 0 ? (
                            <ul className="mt-3 grid gap-2">
                              {grupo.itens.map((item) => (
                                <li key={item.id} className="text-sm">
                                  <a href={item.url_fonte_original} target="_blank" rel="noreferrer" className="font-medium text-[var(--cor-primaria)] hover:underline">
                                    {item.titulo}
                                  </a>{" "}
                                  <span className="text-[var(--cor-texto-suave)]">— {item.nome_fonte}</span>
                                </li>
                              ))}
                            </ul>
                          ) : (
                            <p className="mt-3 text-sm text-[var(--cor-texto-suave)]">Nenhum item encontrado para este critério ainda.</p>
                          )}
                        </li>
                      );
                    })}
                  </ul>
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="membros">
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Membros da organização</CardTitle>
                  <CardDescription>Quem tem acesso ao monitoramento da sua empresa.</CardDescription>
                </CardHeader>
                <CardContent className="grid gap-4">
                  <div aria-live="polite">
                    <DataTable
                      legenda="Membros da organização"
                      linhas={membros}
                      colunas={[
                        { cabecalho: "E-mail", render: (m) => m.email },
                        {
                          cabecalho: "Papel",
                          render: (m) => (
                            <Badge variant={m.papel_na_organizacao === "admin_organizacao" ? "default" : "secondary"}>
                              {m.papel_na_organizacao === "admin_organizacao" ? "Administrador" : "Membro"}
                            </Badge>
                          ),
                        },
                        {
                          cabecalho: "Ações",
                          render: (m) =>
                            souAdmin && m.email !== usuario?.email ? (
                              <Button variante="perigo" tamanho="pequeno" loading={remover.isPending} onClick={() => setMembroAlvo(m.email)}>
                                Remover
                              </Button>
                            ) : (
                              <span className="text-sm text-[var(--cor-texto-suave)]">—</span>
                            ),
                        },
                      ]}
                    />
                  </div>
                  {souAdmin && (
                    <form onSubmit={aoConvidar} noValidate className="grid gap-3 rounded-lg border border-[var(--cor-borda)] bg-[var(--cor-fundo)] p-4">
                      <div className="flex flex-wrap items-end gap-3">
                        <div className="min-w-[240px] flex-1">
                          <CampoTexto
                            id="email-convite"
                            name="email-convite"
                            rotulo="E-mail do convidado"
                            type="email"
                            required
                            autoComplete="email"
                            placeholder="colega@empresa.com…"
                            value={emailConvite}
                            erro={erroConvite ?? undefined}
                            onChange={(e) => setEmailConvite(e.target.value)}
                          />
                        </div>
                        <Button type="submit" loading={convidar.isPending} className="h-10">
                          Convidar membro
                        </Button>
                      </div>
                    </form>
                  )}
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </div>
      )}

      <Dialog open={criterioAlvo !== null} onOpenChange={(aberto) => !aberto && setCriterioAlvo(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Remover o critério “{criterioAlvo?.valor}”?</DialogTitle>
            <DialogDescription>O monitoramento correspondente para. Essa ação não pode ser desfeita.</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCriterioAlvo(null)} disabled={excluirCriterio.isPending}>
              Manter critério
            </Button>
            <Button variant="destructive" loading={excluirCriterio.isPending} onClick={() => void confirmarRemoverCriterio()}>
              Sim, remover
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={membroAlvo !== null} onOpenChange={(aberto) => !aberto && setMembroAlvo(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Remover {membroAlvo} da organização?</DialogTitle>
            <DialogDescription>A pessoa perde acesso imediato ao painel da empresa.</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setMembroAlvo(null)} disabled={remover.isPending}>
              Cancelar
            </Button>
            <Button variant="destructive" loading={remover.isPending} onClick={() => void confirmarRemoverMembro()}>
              Sim, remover
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
