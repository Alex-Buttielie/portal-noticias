"use client";
import { useState } from "react";
import { useAdminAssinaturas } from "@/lib/queries";
import Badge from "@/components/Badge";
import { Button } from "@/components/ui/Button";
import { CampoSelecao, CampoTexto } from "@/components/ui/FormField";
import { DataTable } from "@/components/ui/Data";
import { ErrorState, SkeletonLista } from "@/components/ui/Estados";
import { Card, CardContent } from "@/components/ui/Cards";

const STATUS = ["", "ativa", "teste", "pagamento_pendente", "inadimplente", "cancelada", "expirada", "encerrada"];

export default function AdminAssinaturasPage() {
  const [statusFiltro, setStatusFiltro] = useState("");
  const [search, setSearch] = useState("");
  const [searchAplicada, setSearchAplicada] = useState("");
  const [page, setPage] = useState(1);
  const lista = useAdminAssinaturas({ status: statusFiltro || undefined, search: searchAplicada || undefined, page });

  const totalPaginas = lista.data ? Math.max(1, Math.ceil(lista.data.count / Math.max(1, lista.data.results.length))) : 1;

  return (
<section className="grid gap-6 secao-bloco" aria-labelledby="admin-ass-titulo">
      <div className="grid gap-1">
        <p className="text-xs font-bold uppercase tracking-widest text-[var(--cor-primaria)] secao-eyebrow">Administração</p>
        <h1 id="admin-ass-titulo" className="font-[var(--fonte-titulo)] text-2xl font-bold tracking-tight secao-titulo">Assinaturas</h1>
        <p className="text-sm text-[var(--cor-texto-suave)]">Filtre por status, busque assinantes e confira os valores.</p>
      </div>
      <Card className="shadow-sm">
        <CardContent className="pt-6">
          <form className="flex flex-wrap items-end gap-3 controles-feed" onSubmit={(e) => { e.preventDefault(); setSearchAplicada(search); setPage(1); }}>
            <div className="min-w-[160px] flex-1 max-w-xs">
              <CampoSelecao id="admin-ass-status" rotulo="Status" value={statusFiltro} onChange={(e) => { setStatusFiltro(e.target.value); setPage(1); }}>
                <option value="">todos status</option>
                {STATUS.slice(1).map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </CampoSelecao>
            </div>
            <div className="min-w-[200px] flex-1">
              <CampoTexto id="admin-ass-busca" name="admin-ass-busca" rotulo="Buscar e-mail/nome" placeholder="nome ou e-mail…" value={search} onChange={(e) => setSearch(e.target.value)} />
            </div>
            <Button type="submit" className="h-10">Filtrar</Button>
          </form>
        </CardContent>
      </Card>

      {lista.isLoading && <SkeletonLista quantidade={3} />}
      {lista.isError && <ErrorState mensagem="Erro ao carregar assinaturas." aoTentarNovamente={() => void lista.refetch()} />}
      {lista.data && (
        <DataTable
          legenda="Assinaturas"
          linhas={lista.data.results}
          colunas={[
            { cabecalho: "Usuário", render: (a) => <span className="text-sm">{a.user_email}</span> },
            { cabecalho: "Plano", render: (a) => a.plan.nome },
            {
              cabecalho: "Status",
              render: (a) => <Badge variante={a.status === "ativa" ? "sucesso" : a.status === "cancelada" || a.status === "expirada" ? "erro" : "neutro"}>{a.status}</Badge>,
            },
            { cabecalho: "Preço", render: (a) => a.preco_cobrado },
          ]}
          pagina={page}
          totalPaginas={totalPaginas}
          aoMudarPagina={setPage}
        />
      )}
    </section>
  );
}
