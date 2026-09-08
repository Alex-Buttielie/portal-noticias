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
      await salvarPlano.mutateAsync({
        nome: novoPlano.nome,
        preco: novoPlano.preco,
        duracao_dias: Number(novoPlano.duracao_dias),
      });
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
      await editarPlano.mutateAsync({
        id: editandoId,
        dados: { nome: editForm.nome, preco: editForm.preco, duracao_dias: Number(editForm.duracao_dias) },
      });
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
    <div>
      <h1>Planos & Limites</h1>
      {carregando && <SkeletonLista quantidade={2} />}
      {erro && (
        <ErrorState
          mensagem="Erro ao carregar planos e limites."
          aoTentarNovamente={() => {
            void planosQuery.refetch();
            void limitesQuery.refetch();
          }}
        />
      )}
      {!carregando && !erro && (
        <>
          <h2>Planos</h2>
          <form onSubmit={criarPlano} className="controles-feed">
            <CampoTexto id="plano-nome" rotulo="Nome" value={novoPlano.nome} onChange={(e) => setNovoPlano({ ...novoPlano, nome: e.target.value })} />
            <CampoTexto id="plano-preco" rotulo="Preço (30.00)" value={novoPlano.preco} onChange={(e) => setNovoPlano({ ...novoPlano, preco: e.target.value })} />
            <CampoTexto
              id="plano-dias"
              rotulo="Duração (dias)"
              value={novoPlano.duracao_dias}
              onChange={(e) => setNovoPlano({ ...novoPlano, duracao_dias: e.target.value })}
            />
            <Button type="submit" carregando={salvarPlano.isPending}>
              Criar plano
            </Button>
          </form>
          <DataTable
            legenda="Planos"
            linhas={planosQuery.data ?? []}
            colunas={[
              { cabecalho: "Nome", render: (p) => p.nome },
              { cabecalho: "Preço", render: (p) => p.preco },
              { cabecalho: "Dias", render: (p) => String(p.duracao_dias) },
              {
                cabecalho: "Ativo",
                render: (p) => <Badge variante={p.ativo ? "sucesso" : "erro"}>{p.ativo ? "sim" : "não"}</Badge>,
              },
              {
                cabecalho: "Ações",
                render: (p) => (
                  <span style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                    <Button
                      variante="secundaria"
                      tamanho="pequeno"
                      carregando={alternarPlano.isPending}
                      onClick={() => void alternarPlano.mutateAsync({ id: p.id, ativo: !p.ativo })}
                    >
                      {p.ativo ? "Desativar" : "Ativar"}
                    </Button>
                    <Button variante="secundaria" tamanho="pequeno" onClick={() => iniciarEdicao(p)}>
                      Editar
                    </Button>
                    <Button variante="perigo" tamanho="pequeno" carregando={excluirPlano.isPending} onClick={() => void excluir(p.id, p.nome)}>
                      Excluir
                    </Button>
                  </span>
                ),
              },
            ]}
          />
          {editandoId !== null && (
            <form onSubmit={salvarEdicao} className="controles-feed" style={{ marginTop: 12 }}>
              <CampoTexto id="plano-edit-nome" rotulo="Nome" value={editForm.nome} onChange={(e) => setEditForm({ ...editForm, nome: e.target.value })} />
              <CampoTexto id="plano-edit-preco" rotulo="Preço" value={editForm.preco} onChange={(e) => setEditForm({ ...editForm, preco: e.target.value })} />
              <CampoTexto id="plano-edit-dias" rotulo="Dias" value={editForm.duracao_dias} onChange={(e) => setEditForm({ ...editForm, duracao_dias: e.target.value })} />
              <Button type="submit" carregando={editarPlano.isPending}>
                Salvar
              </Button>
              <Button variante="secundaria" onClick={() => setEditandoId(null)}>
                Cancelar
              </Button>
            </form>
          )}
          <h2 style={{ marginTop: 24 }}>Limites Free/Premium</h2>
          <DataTable
            legenda="Limites por plano"
            linhas={limitesQuery.data ?? []}
            colunas={[
              { cabecalho: "Chave", render: (l) => l.chave },
              { cabecalho: "Plano", render: (l) => l.plano },
              { cabecalho: "Valor", render: (l) => l.valor },
              {
                cabecalho: "Ação",
                render: (l) => (
                  <Button variante="secundaria" tamanho="pequeno" carregando={salvarLimite.isPending} onClick={() => void editarLimite(l)}>
                    Editar
                  </Button>
                ),
              },
            ]}
          />
        </>
      )}
    </div>
  );
}
