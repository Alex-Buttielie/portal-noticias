"use client";
import { useState } from "react";
import { useAdminDecidirFila, useAdminFila } from "@/lib/queries";
import Badge from "@/components/Badge";
import { Button } from "@/components/ui/Button";
import { CampoSelecao } from "@/components/ui/FormField";
import { DataTable } from "@/components/ui/Data";
import { ErrorState, SkeletonLista } from "@/components/ui/Estados";
import { Card, CardContent } from "@/components/ui/Cards";

export default function AdminFilaPage() {
  const [statusFiltro, setStatusFiltro] = useState("pendente");
  const [page, setPage] = useState(1);
  const fila = useAdminFila({ status: statusFiltro, page });
  const decidir = useAdminDecidirFila();

  const totalPaginas = fila.data ? Math.max(1, Math.ceil(fila.data.count / Math.max(1, fila.data.results.length))) : 1;

  return (
<section className="grid gap-6 secao-bloco" aria-labelledby="admin-fila-titulo">
      <div className="grid gap-1">
        <p className="text-xs font-bold uppercase tracking-widest text-[var(--cor-primaria)] secao-eyebrow">Administração</p>
        <h1 id="admin-fila-titulo" className="font-[var(--fonte-titulo)] text-2xl font-bold tracking-tight secao-titulo">Fila editorial</h1>
        <p className="text-sm text-[var(--cor-texto-suave)]">Revise os itens pendentes e decida o que vai ao ar.</p>
      </div>
      <Card className="shadow-sm">
        <CardContent className="pt-6 flex flex-wrap gap-3">
          <div className="min-w-[200px] flex-1 max-w-xs">
            <CampoSelecao id="admin-fila-status" rotulo="Status" value={statusFiltro} onChange={(e) => { setStatusFiltro(e.target.value); setPage(1); }}>
              <option value="pendente">pendente</option>
              <option value="aprovado">aprovado</option>
              <option value="rejeitado">rejeitado</option>
              <option value="nao_aplicavel">não aplicável</option>
            </CampoSelecao>
          </div>
        </CardContent>
      </Card>

      {fila.isLoading && <SkeletonLista quantidade={3} />}
      {fila.isError && <ErrorState mensagem="Erro ao carregar a fila." aoTentarNovamente={() => void fila.refetch()} />}
      {fila.data && (
        <DataTable
          legenda="Fila editorial"
          linhas={fila.data.results}
          colunas={[
            { cabecalho: "Título", render: (it) => <span className="line-clamp-2 max-w-[28ch] text-sm font-medium">{it.titulo}</span> },
            { cabecalho: "Fonte", render: (it) => it.nome_fonte },
            { cabecalho: "Categoria", render: (it) => it.categoria },
            {
              cabecalho: "Status",
              render: (it) => (
                <Badge variante={it.status_revisao === "pendente" ? "neutro" : it.status_revisao === "aprovado" ? "sucesso" : "erro"}>{it.status_revisao}</Badge>
              ),
            },
            {
              cabecalho: "Ações",
              render: (it) => (
                <span className="flex gap-2">
                  <Button tamanho="pequeno" carregando={decidir.isPending} onClick={() => void decidir.mutateAsync({ id: it.id, acao: "aprovar" })}>Aprovar</Button>
                  <Button variante="perigo" tamanho="pequeno" carregando={decidir.isPending} onClick={() => void decidir.mutateAsync({ id: it.id, acao: "rejeitar" })}>Rejeitar</Button>
                </span>
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
