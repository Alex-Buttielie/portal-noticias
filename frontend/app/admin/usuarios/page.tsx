"use client";
import { useState } from "react";
import { useAdminAtualizarUsuario, useAdminUsuarios } from "@/lib/queries";
import Badge from "@/components/Badge";
import { Button } from "@/components/ui/Button";
import { CampoSelecao, CampoTexto } from "@/components/ui/FormField";
import { DataTable } from "@/components/ui/Data";
import { ErrorState, SkeletonLista } from "@/components/ui/Estados";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/Cards";
import { cn } from "@/lib/utils";

export default function AdminUsuariosPage() {
  const [busca, setBusca] = useState("");
  const [buscaAplicada, setBuscaAplicada] = useState("");
  const [papelFiltro, setPapelFiltro] = useState("");
  const [page, setPage] = useState(1);
  const lista = useAdminUsuarios({ search: buscaAplicada || undefined, papel: papelFiltro || undefined, page });
  const atualizar = useAdminAtualizarUsuario();

  function buscar() {
    setPage(1);
  }

  async function atualizarUsuario(id: number, dados: { papel?: string; is_active?: boolean }) {
    await atualizar.mutateAsync({ id, dados });
  }

  const totalPaginas = lista.data ? Math.max(1, Math.ceil(lista.data.count / Math.max(1, lista.data.results.length))) : 1;

  return (
<section className="grid gap-6 secao-bloco" aria-labelledby="admin-usuarios-titulo">
      <div className="grid gap-1">
        <p className="text-xs font-bold uppercase tracking-widest text-[var(--cor-primaria)] secao-eyebrow">Administração</p>
        <h1 id="admin-usuarios-titulo" className="font-[var(--fonte-titulo)] text-2xl font-bold tracking-tight secao-titulo">Usuários</h1>
        <p className="text-sm text-[var(--cor-texto-suave)]">Busque contas, troque papéis e ative ou desative acessos.</p>
      </div>
      <Card className="shadow-sm">
        <CardContent className="pt-6">
          <form className="flex flex-wrap items-end gap-3 controles-feed" onSubmit={(e) => { e.preventDefault(); setBuscaAplicada(busca); buscar(); }}>
            <div className="min-w-[220px] flex-1">
              <CampoTexto id="admin-usuarios-busca" name="admin-usuarios-busca" rotulo="Buscar e-mail/nome" placeholder="nome ou e-mail…" value={busca} onChange={(e) => setBusca(e.target.value)} />
            </div>
            <div className="min-w-[160px] flex-1">
              <CampoSelecao id="admin-usuarios-papel" rotulo="Papel" value={papelFiltro} onChange={(e) => { setPapelFiltro(e.target.value); setPage(1); }}>
                <option value="">Todos papéis</option>
                <option value="free">free</option>
                <option value="premium">premium</option>
                <option value="admin">admin</option>
              </CampoSelecao>
            </div>
            <Button type="submit" className="h-10">Buscar</Button>
          </form>
        </CardContent>
      </Card>

      {lista.isLoading && <SkeletonLista quantidade={3} />}
      {lista.isError && <ErrorState mensagem="Erro ao carregar usuários." aoTentarNovamente={() => void lista.refetch()} />}
      {lista.data && (
        <DataTable
          legenda="Usuários"
          linhas={lista.data.results}
          colunas={[
            { cabecalho: "Email", render: (u) => <span className="text-sm font-medium">{u.email}</span> },
            { cabecalho: "Nome", render: (u) => u.nome },
            {
              cabecalho: "Papel",
              render: (u) => (
                <select aria-label={`Papel de ${u.email}`} value={u.papel} onChange={(e) => void atualizarUsuario(u.id, { papel: e.target.value })} className={cn("h-8 rounded-md border border-[var(--cor-borda)] bg-white px-2 text-sm")}>
                  <option value="free">free</option>
                  <option value="premium">premium</option>
                  <option value="admin">admin</option>
                </select>
              ),
            },
            { cabecalho: "Status", render: (u) => <Badge variante={u.is_active ? "sucesso" : "erro"}>{u.is_active ? "ativo" : "inativo"}</Badge> },
            {
              cabecalho: "Ações",
              render: (u) => (
                <Button variante="secundaria" tamanho="pequeno" carregando={atualizar.isPending} onClick={() => void atualizarUsuario(u.id, { is_active: !u.is_active })}>
                  {u.is_active ? "Desativar" : "Ativar"}
                </Button>
              ),
            },
          ]}
          pagina={page}
          totalPaginas={totalPaginas}
          aoMudarPagina={setPage}
        />
      )}
    </section>
  );
}
