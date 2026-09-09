"use client";
import { useState } from "react";
import { useAdminDecidirFila, useAdminFila } from "@/lib/queries";
import Badge from "@/components/Badge";
import { Button } from "@/components/ui/Button";
import { CampoSelecao } from "@/components/ui/FormField";
import { DataTable } from "@/components/ui/Data";
import { ErrorState, SkeletonLista } from "@/components/ui/Estados";

export default function AdminFilaPage() {
  const [statusFiltro, setStatusFiltro] = useState("pendente");
  const [page, setPage] = useState(1);
  const fila = useAdminFila({ status: statusFiltro, page });
  const decidir = useAdminDecidirFila();

  const totalPaginas = fila.data ? Math.max(1, Math.ceil(fila.data.count / Math.max(1, fila.data.results.length))) : 1;

  return (
    <div className="secao-bloco">
      <div className="secao-cabecalho">
        <h1 className="secao-titulo">Fila editorial</h1>
      </div>
      <CampoSelecao
        id="admin-fila-status"
        rotulo="Status"
        value={statusFiltro}
        onChange={(e) => {
          setStatusFiltro(e.target.value);
          setPage(1);
        }}
      >
        <option value="pendente">pendente</option>
        <option value="aprovado">aprovado</option>
        <option value="rejeitado">rejeitado</option>
        <option value="nao_aplicavel">não aplicável</option>
      </CampoSelecao>

      {fila.isLoading && <SkeletonLista quantidade={3} />}
      {fila.isError && (
        <ErrorState mensagem="Erro ao carregar a fila." aoTentarNovamente={() => void fila.refetch()} />
      )}
      {fila.data && (
        <DataTable
          legenda="Fila editorial"
          linhas={fila.data.results}
          colunas={[
            { cabecalho: "Título", render: (it) => it.titulo },
            { cabecalho: "Fonte", render: (it) => it.nome_fonte },
            { cabecalho: "Categoria", render: (it) => it.categoria },
            {
              cabecalho: "Status",
              render: (it) => (
                <Badge variante={it.status_revisao === "pendente" ? "neutro" : it.status_revisao === "aprovado" ? "sucesso" : "erro"}>
                  {it.status_revisao}
                </Badge>
              ),
            },
            {
              cabecalho: "Ações",
              render: (it) => (
                <span style={{ display: "flex", gap: 6 }}>
                  <Button tamanho="pequeno" carregando={decidir.isPending} onClick={() => void decidir.mutateAsync({ id: it.id, acao: "aprovar" })}>
                    Aprovar
                  </Button>
                  <Button variante="perigo" tamanho="pequeno" carregando={decidir.isPending} onClick={() => void decidir.mutateAsync({ id: it.id, acao: "rejeitar" })}>
                    Rejeitar
                  </Button>
                </span>
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
