"use client";
import { useState } from "react";
import { useAdminAtualizarUsuario, useAdminUsuarios } from "@/lib/queries";
import Badge from "@/components/Badge";
import { Button } from "@/components/ui/Button";
import { CampoSelecao, CampoTexto } from "@/components/ui/FormField";
import { DataTable } from "@/components/ui/Data";
import { ErrorState, SkeletonLista } from "@/components/ui/Estados";

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
    <div className="secao-bloco">
      <div className="secao-cabecalho">
        <h1 className="secao-titulo">Usuários</h1>
      </div>
      <form
        className="controles-feed"
        onSubmit={(e) => {
          e.preventDefault();
          setBuscaAplicada(busca);
          buscar();
        }}
      >
        <CampoTexto
          id="admin-usuarios-busca"
          rotulo="Buscar e-mail/nome"
          value={busca}
          onChange={(e) => setBusca(e.target.value)}
        />
        <CampoSelecao id="admin-usuarios-papel" rotulo="Papel" value={papelFiltro} onChange={(e) => { setPapelFiltro(e.target.value); setPage(1); }}>
          <option value="">Todos papéis</option>
          <option value="free">free</option>
          <option value="premium">premium</option>
          <option value="admin">admin</option>
        </CampoSelecao>
        <Button type="submit">Buscar</Button>
      </form>

      {lista.isLoading && <SkeletonLista quantidade={3} />}
      {lista.isError && (
        <ErrorState mensagem="Erro ao carregar usuários." aoTentarNovamente={() => void lista.refetch()} />
      )}
      {lista.data && (
        <DataTable
          legenda="Usuários"
          linhas={lista.data.results}
          colunas={[
            { cabecalho: "Email", render: (u) => u.email },
            { cabecalho: "Nome", render: (u) => u.nome },
            {
              cabecalho: "Papel",
              render: (u) => (
                <select
                  aria-label={`Papel de ${u.email}`}
                  value={u.papel}
                  onChange={(e) => void atualizarUsuario(u.id, { papel: e.target.value })}
                >
                  <option value="free">free</option>
                  <option value="premium">premium</option>
                  <option value="admin">admin</option>
                </select>
              ),
            },
            {
              cabecalho: "Status",
              render: (u) => <Badge variante={u.is_active ? "sucesso" : "erro"}>{u.is_active ? "ativo" : "inativo"}</Badge>,
            },
            {
              cabecalho: "Ações",
              render: (u) => (
                <Button
                  variante="secundaria"
                  tamanho="pequeno"
                  carregando={atualizar.isPending}
                  onClick={() => void atualizarUsuario(u.id, { is_active: !u.is_active })}
                >
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
    </div>
  );
}
