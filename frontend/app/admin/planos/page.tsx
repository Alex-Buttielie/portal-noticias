"use client";

import { useState, type FormEvent } from "react";
import { useToast } from "@/components/ToastProvider";
import * as api from "@/lib/api";
import {
  useAdminAlternarPlano,
  useAdminEditarPlano,
  useAdminExcluirPlano,
  useAdminLimites,
  useAdminPlanos,
  useAdminSalvarLimite,
  useAdminSalvarPlano,
} from "@/lib/queries";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { CampoTexto } from "@/components/ui/FormField";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { DataTable } from "@/components/ui/Data";
import { ErrorState, SkeletonLista } from "@/components/ui/Estados";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

export default function AdminPlanosPage() {
  const { notificar } = useToast();
  const planosQuery = useAdminPlanos();
  const limitesQuery = useAdminLimites();
  const salvarPlano = useAdminSalvarPlano();
  const alternarPlano = useAdminAlternarPlano();
  const editarPlano = useAdminEditarPlano();
  const excluirPlano = useAdminExcluirPlano();
  const salvarLimite = useAdminSalvarLimite();

  const [novoPlano, setNovoPlano] = useState({ nome: "", preco: "", duracao_dias: "180" });
  const [erroNovo, setErroNovo] = useState<string | undefined>(undefined);
  const [editandoId, setEditandoId] = useState<number | null>(null);
  const [editForm, setEditForm] = useState({ nome: "", preco: "", duracao_dias: "" });
  const [excluirAlvo, setExcluirAlvo] = useState<api.Plano | null>(null);
  const [limiteAlvo, setLimiteAlvo] = useState<{ id: number; chave: string; plano: string; valor: string } | null>(null);
  const [novoValorLimite, setNovoValorLimite] = useState("");

  async function criarPlano(evento: FormEvent) {
    evento.preventDefault();
    if (!novoPlano.nome.trim()) {
      setErroNovo("Dê um nome ao plano.");
      document.getElementById("plano-nome")?.focus();
      return;
    }
    if (!novoPlano.preco.trim() || Number.isNaN(Number(novoPlano.preco))) {
      setErroNovo("Informe o preço no formato 30.00.");
      document.getElementById("plano-preco")?.focus();
      return;
    }
    if (!Number.isInteger(Number(novoPlano.duracao_dias)) || Number(novoPlano.duracao_dias) <= 0) {
      setErroNovo("A duração precisa ser um número inteiro de dias maior que zero.");
      document.getElementById("plano-dias")?.focus();
      return;
    }
    setErroNovo(undefined);
    try {
      await salvarPlano.mutateAsync({ nome: novoPlano.nome.trim(), preco: novoPlano.preco.trim(), duracao_dias: Number(novoPlano.duracao_dias) });
      setNovoPlano({ nome: "", preco: "", duracao_dias: "180" });
      notificar("Plano criado.", "sucesso");
    } catch (e) {
      notificar(e instanceof api.ApiError ? e.message : "Não foi possível criar o plano.", "erro");
    }
  }

  async function confirmarExclusao() {
    if (!excluirAlvo) return;
    try {
      await excluirPlano.mutateAsync(excluirAlvo.id);
      notificar("Plano excluído.", "info");
      setExcluirAlvo(null);
    } catch (e) {
      notificar(e instanceof api.ApiError ? e.message : "Não foi possível excluir o plano.", "erro");
    }
  }

  function iniciarEdicao(plano: api.Plano) {
    setEditandoId(plano.id);
    setEditForm({ nome: plano.nome, preco: plano.preco, duracao_dias: String(plano.duracao_dias) });
  }

  async function salvarEdicao(evento: FormEvent) {
    evento.preventDefault();
    if (editandoId === null) return;
    try {
      await editarPlano.mutateAsync({ id: editandoId, dados: { nome: editForm.nome, preco: editForm.preco, duracao_dias: Number(editForm.duracao_dias) } });
      setEditandoId(null);
      notificar("Plano atualizado.", "sucesso");
    } catch (e) {
      notificar(e instanceof api.ApiError ? e.message : "Não foi possível atualizar o plano.", "erro");
    }
  }

  function abrirLimite(limite: { id: number; chave: string; plano: string; valor: string }) {
    setLimiteAlvo(limite);
    setNovoValorLimite(limite.valor);
  }

  async function salvarLimiteDialogo(evento: FormEvent) {
    evento.preventDefault();
    if (!limiteAlvo) return;
    if (!novoValorLimite.trim()) {
      document.getElementById("limite-valor")?.focus();
      return;
    }
    try {
      await salvarLimite.mutateAsync({ id: limiteAlvo.id, valor: novoValorLimite.trim() });
      notificar("Limite atualizado.", "sucesso");
      setLimiteAlvo(null);
    } catch (e) {
      notificar(e instanceof api.ApiError ? e.message : "Não foi possível atualizar o limite.", "erro");
    }
  }

  const carregando = planosQuery.isLoading || limitesQuery.isLoading;
  const erro = planosQuery.isError || limitesQuery.isError;

  return (
    <section className="grid gap-6" aria-labelledby="admin-planos-titulo">
      <div className="grid gap-1">
        <h1 id="admin-planos-titulo" className="font-[var(--fonte-titulo)] text-2xl font-bold tracking-tight text-balance text-[var(--cor-texto)]">
          Planos e limites
        </h1>
        <p className="text-sm text-[var(--cor-texto-suave)]">Crie planos, ajuste preços e defina os limites Free e Premium.</p>
      </div>
      {carregando && <SkeletonLista quantidade={2} />}
      {erro && <ErrorState mensagem="Erro ao carregar planos e limites." aoTentarNovamente={() => { void planosQuery.refetch(); void limitesQuery.refetch(); }} />}
      {!carregando && !erro && (
        <div className="grid gap-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Planos</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-6">
              <form onSubmit={criarPlano} noValidate className="grid gap-3 rounded-lg border border-[var(--cor-borda)] bg-[var(--cor-fundo)] p-4">
                <div className="flex flex-wrap items-end gap-3">
                  <div className="min-w-[160px] flex-1">
                    <CampoTexto id="plano-nome" name="plano-nome" rotulo="Nome" placeholder="Premium mensal…" value={novoPlano.nome} onChange={(e) => setNovoPlano({ ...novoPlano, nome: e.target.value })} />
                  </div>
                  <div className="min-w-[120px] flex-1">
                    <CampoTexto id="plano-preco" name="plano-preco" rotulo="Preço (30.00)" placeholder="30.00…" inputMode="decimal" value={novoPlano.preco} onChange={(e) => setNovoPlano({ ...novoPlano, preco: e.target.value })} />
                  </div>
                  <div className="min-w-[120px] flex-1">
                    <CampoTexto id="plano-dias" name="plano-dias" rotulo="Duração (dias)" placeholder="180…" inputMode="numeric" value={novoPlano.duracao_dias} onChange={(e) => setNovoPlano({ ...novoPlano, duracao_dias: e.target.value })} />
                  </div>
                  <Button type="submit" loading={salvarPlano.isPending} className="h-10">
                    Criar plano
                  </Button>
                </div>
                {erroNovo && (
                  <p role="alert" className="text-xs font-medium text-[var(--cor-erro)]">
                    {erroNovo}
                  </p>
                )}
              </form>
              <div aria-live="polite">
                <DataTable
                  legenda="Planos"
                  linhas={planosQuery.data ?? []}
                  colunas={[
                    { cabecalho: "Nome", render: (p) => p.nome },
                    { cabecalho: "Preço", render: (p) => p.preco },
                    { cabecalho: "Dias", render: (p) => String(p.duracao_dias) },
                    { cabecalho: "Ativo", render: (p) => <Badge variant={p.ativo ? "success" : "destructive"}>{p.ativo ? "sim" : "não"}</Badge> },
                    {
                      cabecalho: "Ações",
                      render: (p) => (
                        <span className="flex flex-wrap gap-2">
                          <Button variante="secundaria" tamanho="pequeno" loading={alternarPlano.isPending} onClick={() => void alternarPlano.mutateAsync({ id: p.id, ativo: !p.ativo }).then(() => notificar(p.ativo ? "Plano desativado." : "Plano ativado.", "info")).catch((e: unknown) => notificar(e instanceof api.ApiError ? e.message : "Não foi possível alternar o plano.", "erro"))}>
                            {p.ativo ? "Desativar" : "Ativar"}
                          </Button>
                          <Button variante="secundaria" tamanho="pequeno" onClick={() => iniciarEdicao(p)}>
                            Editar
                          </Button>
                          <Button variante="perigo" tamanho="pequeno" loading={excluirPlano.isPending} onClick={() => setExcluirAlvo(p)}>
                            Excluir
                          </Button>
                        </span>
                      ),
                    },
                  ]}
                />
              </div>
              {editandoId !== null && (
                <form onSubmit={salvarEdicao} className="flex flex-wrap items-end gap-3 rounded-lg border border-[var(--cor-borda)] bg-[var(--cor-fundo)] p-4">
                  <div className="min-w-[140px] flex-1">
                    <CampoTexto id="plano-edit-nome" name="plano-edit-nome" rotulo="Nome" value={editForm.nome} onChange={(e) => setEditForm({ ...editForm, nome: e.target.value })} />
                  </div>
                  <div className="min-w-[120px] flex-1">
                    <CampoTexto id="plano-edit-preco" name="plano-edit-preco" rotulo="Preço" inputMode="decimal" value={editForm.preco} onChange={(e) => setEditForm({ ...editForm, preco: e.target.value })} />
                  </div>
                  <div className="min-w-[100px] flex-1">
                    <CampoTexto id="plano-edit-dias" name="plano-edit-dias" rotulo="Dias" inputMode="numeric" value={editForm.duracao_dias} onChange={(e) => setEditForm({ ...editForm, duracao_dias: e.target.value })} />
                  </div>
                  <Button type="submit" loading={editarPlano.isPending} className="h-10">
                    Salvar
                  </Button>
                  <Button type="button" variante="secundaria" onClick={() => setEditandoId(null)} className="h-10">
                    Cancelar
                  </Button>
                </form>
              )}
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Limites Free e Premium</CardTitle>
            </CardHeader>
            <CardContent>
              <DataTable
                legenda="Limites por plano"
                linhas={limitesQuery.data ?? []}
                colunas={[
                  { cabecalho: "Chave", render: (l) => l.chave },
                  { cabecalho: "Plano", render: (l) => l.plano },
                  { cabecalho: "Valor", render: (l) => l.valor },
                  { cabecalho: "Ação", render: (l) => <Button variante="secundaria" tamanho="pequeno" loading={salvarLimite.isPending} onClick={() => abrirLimite(l)}>Editar</Button> },
                ]}
              />
            </CardContent>
          </Card>
        </div>
      )}

      <Dialog open={excluirAlvo !== null} onOpenChange={(aberto) => !aberto && setExcluirAlvo(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Excluir o plano “{excluirAlvo?.nome}”?</DialogTitle>
            <DialogDescription>
              Só é possível excluir se não houver assinaturas vinculadas. Essa ação não pode ser desfeita.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setExcluirAlvo(null)} disabled={excluirPlano.isPending}>
              Manter plano
            </Button>
            <Button variant="destructive" loading={excluirPlano.isPending} onClick={() => void confirmarExclusao()}>
              Sim, excluir
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={limiteAlvo !== null} onOpenChange={(aberto) => !aberto && setLimiteAlvo(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Editar limite</DialogTitle>
            <DialogDescription>
              {limiteAlvo && (
                <>
                  Novo valor para <strong className="text-[var(--cor-texto)]">{limiteAlvo.chave}</strong> ({limiteAlvo.plano}).
                </>
              )}
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={salvarLimiteDialogo} className="grid gap-4">
            <div className="grid gap-1.5">
              <Label htmlFor="limite-valor">Valor</Label>
              <Input
                id="limite-valor"
                name="limite-valor"
                value={novoValorLimite}
                placeholder="Novo valor…"
                onChange={(e) => setNovoValorLimite(e.target.value)}
              />
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setLimiteAlvo(null)} disabled={salvarLimite.isPending}>
                Cancelar
              </Button>
              <Button type="submit" loading={salvarLimite.isPending}>
                Salvar limite
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </section>
  );
}
