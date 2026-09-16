"use client";

import { useMemo, useState } from "react";
import { useToast } from "@/components/ToastProvider";
import * as api from "@/lib/api";
import { useAdminAtualizarUsuario, useAdminUsuarios } from "@/lib/queries";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { CampoSelecao, CampoTexto } from "@/components/ui/FormField";
import { DataTable } from "@/components/ui/Data";
import { ErrorState, SkeletonLista } from "@/components/ui/Estados";
import { Card, CardContent } from "@/components/ui/card";

type Ordem = "email-asc" | "email-desc" | "nome-asc" | "nome-desc";

export default function AdminUsuariosPage() {
  const { notificar } = useToast();
  const [busca, setBusca] = useState("");
  const [buscaAplicada, setBuscaAplicada] = useState("");
  const [papelFiltro, setPapelFiltro] = useState("");
  const [page, setPage] = useState(1);
  const [ordem, setOrdem] = useState<Ordem>("email-asc");
  const lista = useAdminUsuarios({ search: buscaAplicada || undefined, papel: papelFiltro || undefined, page });
  const atualizar = useAdminAtualizarUsuario();

  const linhas = useMemo(() => {
    const copia = [...(lista.data?.results ?? [])];
    copia.sort((a, b) => {
      const [chave, dir] = ordem.split("-") as ["email" | "nome", "asc" | "desc"];
      const va = (chave === "email" ? a.email : a.nome).toLowerCase();
      const vb = (chave === "email" ? b.email : b.nome).toLowerCase();
      const cmp = va.localeCompare(vb, "pt-BR");
      return dir === "asc" ? cmp : -cmp;
    });
    return copia;
  }, [lista.data, ordem]);

  async function atualizarUsuario(id: number, dados: { papel?: string; is_active?: boolean }) {
    try {
      await atualizar.mutateAsync({ id, dados });
      notificar("Usuário atualizado.", "sucesso");
    } catch (e) {
      notificar(e instanceof api.ApiError ? e.message : "Não foi possível atualizar o usuário.", "erro");
    }
  }

  const totalPaginas = lista.data ? Math.max(1, Math.ceil(lista.data.count / Math.max(1, lista.data.results.length))) : 1;

  return (
    <section className="grid gap-6" aria-labelledby="admin-usuarios-titulo">
      <div className="grid gap-1">
        <h1 id="admin-usuarios-titulo" className="font-[var(--fonte-titulo)] text-2xl font-bold tracking-tight text-balance text-[var(--cor-texto)]">
          Usuários
        </h1>
        <p className="text-sm text-[var(--cor-texto-suave)]">Busque contas, troque papéis e ative ou desative acessos.</p>
      </div>
      <Card>
        <CardContent className="pt-6">
          <form
            className="flex flex-wrap items-end gap-3"
            onSubmit={(e) => {
              e.preventDefault();
              setBuscaAplicada(busca);
              setPage(1);
            }}
          >
            <div className="min-w-[220px] flex-1">
              <CampoTexto
                id="admin-usuarios-busca"
                name="admin-usuarios-busca"
                rotulo="Buscar e-mail ou nome"
                placeholder="nome ou e-mail…"
                autoComplete="off"
                value={busca}
                onChange={(e) => setBusca(e.target.value)}
              />
            </div>
            <div className="min-w-[160px] flex-1">
              <CampoSelecao
                id="admin-usuarios-papel"
                name="admin-usuarios-papel"
                rotulo="Papel"
                value={papelFiltro}
                onChange={(e) => {
                  setPapelFiltro(e.target.value);
                  setPage(1);
                }}
              >
                <option value="">Todos papéis</option>
                <option value="free">free</option>
                <option value="premium">premium</option>
                <option value="admin">admin</option>
              </CampoSelecao>
            </div>
            <Button type="submit" className="h-10">
              Buscar
            </Button>
            <div className="min-w-[180px] flex-1">
              <CampoSelecao
                id="admin-usuarios-ordem"
                name="admin-usuarios-ordem"
                rotulo="Ordenar"
                value={ordem}
                onChange={(e) => setOrdem(e.target.value as Ordem)}
              >
                <option value="email-asc">E-mail (A–Z)</option>
                <option value="email-desc">E-mail (Z–A)</option>
                <option value="nome-asc">Nome (A–Z)</option>
                <option value="nome-desc">Nome (Z–A)</option>
              </CampoSelecao>
            </div>
          </form>
        </CardContent>
      </Card>

      {lista.isLoading && <SkeletonLista quantidade={3} />}
      {lista.isError && <ErrorState mensagem="Erro ao carregar usuários." aoTentarNovamente={() => void lista.refetch()} />}
      {lista.data && (
        <div aria-live="polite">
          <DataTable
            legenda="Usuários"
            linhas={linhas}
            colunas={[
              { cabecalho: "E-mail", render: (u) => <span className="text-sm font-medium">{u.email}</span> },
              { cabecalho: "Nome", render: (u) => u.nome },
              {
                cabecalho: "Papel",
                render: (u) => (
                  <select
                    aria-label={`Papel de ${u.email}`}
                    value={u.papel}
                    onChange={(e) => void atualizarUsuario(u.id, { papel: e.target.value })}
                    className="h-10 min-h-[44px] rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] px-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]"
                  >
                    <option value="free">free</option>
                    <option value="premium">premium</option>
                    <option value="admin">admin</option>
                  </select>
                ),
              },
              { cabecalho: "Status", render: (u) => <Badge variant={u.is_active ? "success" : "destructive"}>{u.is_active ? "ativo" : "inativo"}</Badge> },
              {
                cabecalho: "Ações",
                render: (u) => (
                  <Button variante="secundaria" tamanho="pequeno" loading={atualizar.isPending} onClick={() => void atualizarUsuario(u.id, { is_active: !u.is_active })}>
                    {u.is_active ? "Desativar" : "Ativar"}
                  </Button>
                ),
              },
            ]}
            pagina={page}
            totalPaginas={totalPaginas}
            aoMudarPagina={setPage}
          />
        </div>
      )}
    </section>
  );
}
