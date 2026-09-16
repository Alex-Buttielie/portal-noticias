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
import Badge from "@/components/Badge";
import { Button } from "@/components/ui/Button";
import { CampoTexto } from "@/components/ui/FormField";
import { DataTable } from "@/components/ui/Data";
import { ErrorState, SkeletonLista } from "@/components/ui/Estados";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Cards";

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
  const [editandoId, setEditandoId] = useState<number | null>(null);
  const [editForm, setEditForm] = useState({ nome: "", preco: "", duracao_dias: "" });

  async function criarPlano(evento: FormEvent) {
    evento.preventDefault();
    try {
      await salvarPlano.mutateAsync({ nome: novoPlano.nome, preco: novoPlano.preco, duracao_dias: Number(novoPlano.duracao_dias) });
      setNovoPlano({ nome: "", preco: "", duracao_dias: "180" });
      notificar("Plano criado.", "sucesso");
    } catch (e) {
      notificar(e instanceof api.ApiError ? e.message : "Não foi possível criar o plano.", "erro");
    }
  }

  async function excluir(id: number, nome: string) {
    if (!window.confirm(`Excluir o plano "${nome}"? Só é possível se não houver assinaturas vinculadas.`)) return;
    try {
      await excluirPlano.mutateAsync(id);
      notificar("Plano excluído.", "info");
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
  async function editarLimite(limite: { id: number; chave: string; plano: string; valor: string }) {
    const novo = window.prompt(`Novo valor para ${limite.chave} (${limite.plano}):`, limite.valor);
    if (novo === null) return;
    try {
      await salvarLimite.mutateAsync({ id: limite.id, valor: novo });
      notificar("Limite atualizado.", "sucesso");
    } catch (e) {
      notificar(e instanceof api.ApiError ? e.message : "Não foi possível atualizar o limite.", "erro");
    }
  }

  const carregando = planosQuery.isLoading || limitesQuery.isLoading;
  const erro = planosQuery.isError || limitesQuery.isError;

  return (
<section className="grid gap-6 secao-bloco" aria-labelledby="admin-planos-titulo">
      <div className="grid gap-1">
        <p className="text-xs font-bold uppercase tracking-widest text-[var(--cor-primaria)] secao-eyebrow">Administração</p>
        <h1 id="admin-planos-titulo" className="font-[var(--fonte-titulo)] text-2xl font-bold tracking-tight secao-titulo">Planos &amp; Limites</h1>
        <p className="text-sm text-[var(--cor-texto-suave)]">Crie planos, ajuste preços e defina os limites Free/Premium.</p>
      </div>
      {carregando && <SkeletonLista quantidade={2} />}
      {erro && <ErrorState mensagem="Erro ao carregar planos e limites." aoTentarNovamente={() => { void planosQuery.refetch(); void limitesQuery.refetch(); }} />}
      {!carregando && !erro && (
<div className="grid gap-6 secao-bloco secao-cabecalho secao-titulo">
          <Card className="shadow-sm">
            <CardHeader>
              <CardTitle id="admin-planos-lista" className="text-base">Planos</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-6">
              <form onSubmit={criarPlano} className="flex flex-wrap items-end gap-3 rounded-lg border border-[var(--cor-borda)] bg-[var(--cor-fundo)] p-4 controles-feed">
                <div className="min-w-[160px] flex-1"><CampoTexto id="plano-nome" name="plano-nome" rotulo="Nome" placeholder="Premium mensal…" value={novoPlano.nome} onChange={(e) => setNovoPlano({ ...novoPlano, nome: e.target.value })} /></div>
                <div className="min-w-[120px] flex-1"><CampoTexto id="plano-preco" name="plano-preco" rotulo="Preço (30.00)" placeholder="30.00…" value={novoPlano.preco} onChange={(e) => setNovoPlano({ ...novoPlano, preco: e.target.value })} /></div>
                <div className="min-w-[120px] flex-1"><CampoTexto id="plano-dias" name="plano-dias" rotulo="Duração (dias)" placeholder="180…" value={novoPlano.duracao_dias} onChange={(e) => setNovoPlano({ ...novoPlano, duracao_dias: e.target.value })} /></div>
                <Button type="submit" carregando={salvarPlano.isPending} className="h-10">Criar plano</Button>
              </form>
              <DataTable
                legenda="Planos"
                linhas={planosQuery.data ?? []}
                colunas={[
                  { cabecalho: "Nome", render: (p) => p.nome },
                  { cabecalho: "Preço", render: (p) => p.preco },
                  { cabecalho: "Dias", render: (p) => String(p.duracao_dias) },
                  { cabecalho: "Ativo", render: (p) => <Badge variante={p.ativo ? "sucesso" : "erro"}>{p.ativo ? "sim" : "não"}</Badge> },
                  {
                    cabecalho: "Ações",
                    render: (p) => (
                      <span className="flex flex-wrap gap-2">
                        <Button variante="secundaria" tamanho="pequeno" carregando={alternarPlano.isPending} onClick={() => void alternarPlano.mutateAsync({ id: p.id, ativo: !p.ativo })}>{p.ativo ? "Desativar" : "Ativar"}</Button>
                        <Button variante="secundaria" tamanho="pequeno" onClick={() => iniciarEdicao(p)}>Editar</Button>
                        <Button variante="perigo" tamanho="pequeno" carregando={excluirPlano.isPending} onClick={() => void excluir(p.id, p.nome)}>Excluir</Button>
                      </span>
                    ),
                  },
                ]}
              />
              {editandoId !== null && (
                <form onSubmit={salvarEdicao} className="flex flex-wrap items-end gap-3 rounded-lg border border-[var(--cor-borda)] bg-[var(--cor-fundo)] p-4">
                  <div className="min-w-[140px] flex-1"><CampoTexto id="plano-edit-nome" name="plano-edit-nome" rotulo="Nome" value={editForm.nome} onChange={(e) => setEditForm({ ...editForm, nome: e.target.value })} /></div>
                  <div className="min-w-[120px] flex-1"><CampoTexto id="plano-edit-preco" name="plano-edit-preco" rotulo="Preço" value={editForm.preco} onChange={(e) => setEditForm({ ...editForm, preco: e.target.value })} /></div>
                  <div className="min-w-[100px] flex-1"><CampoTexto id="plano-edit-dias" name="plano-edit-dias" rotulo="Dias" value={editForm.duracao_dias} onChange={(e) => setEditForm({ ...editForm, duracao_dias: e.target.value })} /></div>
                  <Button type="submit" carregando={editarPlano.isPending} className="h-10">Salvar</Button>
                  <Button variante="secundaria" onClick={() => setEditandoId(null)} className="h-10">Cancelar</Button>
                </form>
              )}
            </CardContent>
          </Card>
          <Card className="shadow-sm">
            <CardHeader>
              <CardTitle id="admin-limites" className="text-base">Limites Free/Premium</CardTitle>
            </CardHeader>
            <CardContent>
              <DataTable
                legenda="Limites por plano"
                linhas={limitesQuery.data ?? []}
                colunas={[
                  { cabecalho: "Chave", render: (l) => l.chave },
                  { cabecalho: "Plano", render: (l) => l.plano },
                  { cabecalho: "Valor", render: (l) => l.valor },
                  { cabecalho: "Ação", render: (l) => <Button variante="secundaria" tamanho="pequeno" carregando={salvarLimite.isPending} onClick={() => void editarLimite(l)}>Editar</Button> },
                ]}
              />
            </CardContent>
          </Card>
        </div>
      )}
    </section>
  );
}
