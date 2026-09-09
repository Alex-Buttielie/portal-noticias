"use client";
import { useState } from "react";
import { useAdminAssinaturas } from "@/lib/queries";
import Badge from "@/components/Badge";
import { Button } from "@/components/ui/Button";
import { CampoSelecao, CampoTexto } from "@/components/ui/FormField";
import { DataTable } from "@/components/ui/Data";
import { ErrorState, SkeletonLista } from "@/components/ui/Estados";

const STATUS = ["", "ativa", "teste", "pagamento_pendente", "inadimplente", "cancelada", "expirada", "encerrada"];

export default function AdminAssinaturasPage() {
  const [statusFiltro, setStatusFiltro] = useState("");
  const [search, setSearch] = useState("");
  const [searchAplicada, setSearchAplicada] = useState("");
  const [page, setPage] = useState(1);
  const lista = useAdminAssinaturas({
    status: statusFiltro || undefined,
    search: searchAplicada || undefined,
    page,
  });

  const totalPaginas = lista.data ? Math.max(1, Math.ceil(lista.data.count / Math.max(1, lista.data.results.length))) : 1;

  return (
    <div className="secao-bloco">
      <div className="secao-cabecalho">
        <h1 className="secao-titulo">Assinaturas</h1>
      </div>
      <form
        className="controles-feed"
        onSubmit={(e) => {
          e.preventDefault();
          setSearchAplicada(search);
          setPage(1);
        }}
      >
        <CampoSelecao
          id="admin-ass-status"
          rotulo="Status"
          value={statusFiltro}
          onChange={(e) => {
            setStatusFiltro(e.target.value);
            setPage(1);
          }}
        >
          <option value="">todos status</option>
          {STATUS.slice(1).map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </CampoSelecao>
        <CampoTexto
          id="admin-ass-busca"
          rotulo="Buscar e-mail/nome"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <Button type="submit">Filtrar</Button>
      </form>

      {lista.isLoading && <SkeletonLista quantidade={3} />}
      {lista.isError && (
        <ErrorState mensagem="Erro ao carregar assinaturas." aoTentarNovamente={() => void lista.refetch()} />
      )}
      {lista.data && (
        <DataTable
          legenda="Assinaturas"
          linhas={lista.data.results}
          colunas={[
            { cabecalho: "Usuário", render: (a) => a.user_email },
            { cabecalho: "Plano", render: (a) => a.plan.nome },
            {
              cabecalho: "Status",
              render: (a) => (
                <Badge variante={a.status === "ativa" ? "sucesso" : a.status === "cancelada" || a.status === "expirada" ? "erro" : "neutro"}>
                  {a.status}
                </Badge>
              ),
            },
            { cabecalho: "Preço", render: (a) => a.preco_cobrado },
          ]}
          pagina={page}
          totalPaginas={totalPaginas}
          aoMudarPagina={setPage}
        />
      )}
    </div>
  );
}
