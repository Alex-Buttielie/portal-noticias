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
import Badge from "@/components/Badge";
import { Button } from "@/components/ui/Button";
import { CampoSelecao, CampoTexto } from "@/components/ui/FormField";
import { DataTable, StatCard } from "@/components/ui/Data";
import { EmptyState, ErrorState, SkeletonLista } from "@/components/ui/Estados";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/Cards";
import { cn } from "@/lib/utils";

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
  const [emailConvite, setEmailConvite] = useState("");
  const [erroConvite, setErroConvite] = useState<string | null>(null);

  useEffect(() => {
    if (!carregandoAuth && !token) {
      router.push("/login");
    }
  }, [carregandoAuth, token, router]);

  if (carregandoAuth)
    return (
      <div className={cn("container mx-auto max-w-5xl px-4 py-10")}>
        <p className="text-sm text-[var(--cor-texto-suave)]">Carregando…</p>
      </div>
    );

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
    if (!token || !valorCriterio.trim()) return;
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
    if (!token || !emailConvite.trim()) return;
    setErroConvite(null);
    try {
      await convidar.mutateAsync(emailConvite.trim());
      setEmailConvite("");
      notificar("Convite enviado.", "sucesso");
    } catch (e) {
      setErroConvite(e instanceof api.ApiError ? e.message : "Não foi possível convidar este usuário.");
    }
  }

  async function aoRemoverCriterio(id: number, valor: string) {
    const confirmado = window.confirm(`Remover o critério "${valor}"? O monitoramento correspondente para.`);
    if (!confirmado) return;
    try {
      await excluirCriterio.mutateAsync(id);
      notificar("Critério removido.", "info");
    } catch (e) {
      notificar(e instanceof api.ApiError ? e.message : "Não foi possível remover o critério.", "erro");
    }
  }

  async function aoRemoverMembro(email: string) {
    if (!token) return;
    const confirmado = window.confirm(`Remover ${email} da organização?`);
    if (!confirmado) return;
    try {
      await remover.mutateAsync(email);
      notificar("Membro removido.", "info");
    } catch (e) {
      notificar(e instanceof api.ApiError ? e.message : "Não foi possível remover este membro.", "erro");
    }
  }

  const souAdmin = membros.some((m) => m.email === usuario?.email && m.papel_na_organizacao === "admin_organizacao");

  return (
<div className={cn("container mx-auto max-w-5xl px-4 py-8 sm:px-6")}>
      <div className="mb-8 grid gap-2 secao-bloco cartao kpi-grid secao-cabecalho">
        <p className="text-xs font-bold uppercase tracking-widest text-[var(--cor-primaria)] secao-eyebrow">Monitoramento corporativo</p>
        <h1 id="empresa-titulo" className="font-[var(--fonte-titulo)] text-3xl font-bold tracking-tight text-[var(--cor-texto)] secao-titulo">
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
            <Card className="shadow-sm">
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

          <Card className="shadow-sm">
            <CardHeader>
              <CardTitle id="empresa-criterios" className="text-base">
                Critérios de monitoramento
              </CardTitle>
            </CardHeader>
            <CardContent className="grid gap-6">
              <form onSubmit={aoCriarCriterio} className="flex flex-wrap items-end gap-3 rounded-lg border border-[var(--cor-borda)] bg-[var(--cor-fundo)] p-4 controles-feed">
                <div className="min-w-[160px] flex-1">
                  <CampoSelecao id="tipo-criterio" rotulo="Tipo" value={tipoCriterio} onChange={(e) => setTipoCriterio(e.target.value as api.TipoCriterioMonitoramento)}>
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
                    onChange={(e) => setValorCriterio(e.target.value)}
                  />
                </div>
                <Button type="submit" carregando={criarCriterio.isPending} className="h-10">
                  Adicionar critério
                </Button>
              </form>

{criterios.length === 0 && <EmptyState titulo="Nenhum critério configurado" descricao="Adicione o primeiro critério acima." />}
              <div className="grid gap-4 cartao cartao-meta secao-bloco secao-cabecalho secao-titulo">
                {criterios.map((c) => {
                  const grupo = itensMonitorados[String(c.id)];
                  return (
                    <div key={c.id} className="rounded-xl border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] p-4 shadow-sm">
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge variante="neutro">{ROTULOS_TIPO[c.tipo]}</Badge>
                        <span className="text-sm font-medium text-[var(--cor-texto)]">{c.valor}</span>
                        {!c.ativo && <Badge variante="erro">Inativo</Badge>}
                        <span className="ml-auto">
                          <Button variante="fantasma" tamanho="pequeno" carregando={excluirCriterio.isPending} onClick={() => void aoRemoverCriterio(c.id, c.valor)}>
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
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>

          <Card className="shadow-sm">
            <CardHeader>
              <CardTitle id="empresa-membros" className="text-base">
                Membros da organização
              </CardTitle>
            </CardHeader>
            <CardContent className="grid gap-4">
              <DataTable
                legenda="Membros da organização"
                linhas={membros}
                colunas={[
                  { cabecalho: "E-mail", render: (m) => m.email },
                  {
                    cabecalho: "Papel",
                    render: (m) => (
                      <Badge variante={m.papel_na_organizacao === "admin_organizacao" ? "premium" : "neutro"}>
                        {m.papel_na_organizacao === "admin_organizacao" ? "Administrador" : "Membro"}
                      </Badge>
                    ),
                  },
                  {
                    cabecalho: "Ações",
                    render: (m) =>
                      souAdmin && m.email !== usuario?.email ? (
                        <Button variante="perigo" tamanho="pequeno" carregando={remover.isPending} onClick={() => void aoRemoverMembro(m.email)}>
                          Remover
                        </Button>
                      ) : (
<span className="text-sm text-[var(--cor-texto-suave)] texto-suave">—</span>
                      ),
                  },
                ]}
              />
{souAdmin && (
                <form onSubmit={aoConvidar} className="flex flex-wrap items-end gap-3 rounded-lg border border-[var(--cor-borda)] bg-[var(--cor-fundo)] p-4 controles-feed">
                  {erroConvite && <ErrorState mensagem={erroConvite} />}
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
                      onChange={(e) => setEmailConvite(e.target.value)}
                    />
                  </div>
                  <Button type="submit" carregando={convidar.isPending} className="h-10">
                    Convidar membro
                  </Button>
                </form>
              )}
</CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
