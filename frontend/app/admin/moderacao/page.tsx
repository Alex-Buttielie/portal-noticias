"use client";

import { useMemo, useState, type FormEvent } from "react";
import { useToast } from "@/components/ToastProvider";
import * as api from "@/lib/api";
import { useAdminAcaoDenuncia, useAdminDenuncias } from "@/lib/queries";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { CampoSelecao } from "@/components/ui/FormField";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { DataTable } from "@/components/ui/Data";
import { ErrorState, SkeletonLista } from "@/components/ui/Estados";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const TIPOS_ACAO = ["aviso", "remocao_conteudo", "bloqueio_temporario", "bloqueio_permanente"];

function formatarData(data: string): string {
  const d = new Date(data);
  if (Number.isNaN(d.getTime())) return data;
  return new Intl.DateTimeFormat("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric" }).format(d);
}

export default function AdminModeracaoPage() {
  const { notificar } = useToast();
  const [statusFiltro, setStatusFiltro] = useState("");
  const [page, setPage] = useState(1);
  const [ordem, setOrdem] = useState<"recentes" | "antigos">("recentes");
  const [alvoId, setAlvoId] = useState<number | null>(null);
  const [tipo, setTipo] = useState("aviso");
  const [motivo, setMotivo] = useState("");
  const [erroMotivo, setErroMotivo] = useState<string | undefined>(undefined);
  const lista = useAdminDenuncias({ status: statusFiltro || undefined, page });
  const agir = useAdminAcaoDenuncia();

  const linhas = useMemo(() => {
    const copia = [...(lista.data?.results ?? [])];
    copia.sort((a, b) => {
      const ta = new Date(a.criado_em).getTime();
      const tb = new Date(b.criado_em).getTime();
      return ordem === "recentes" ? tb - ta : ta - tb;
    });
    return copia;
  }, [lista.data, ordem]);

  function abrirDialogo(id: number) {
    setAlvoId(id);
    setTipo("aviso");
    setMotivo("");
    setErroMotivo(undefined);
  }

  async function aplicarAcao(evento: FormEvent) {
    evento.preventDefault();
    if (alvoId === null) return;
    if (!motivo.trim()) {
      setErroMotivo("Descreva o motivo da ação.");
      document.getElementById("moderacao-motivo")?.focus();
      return;
    }
    setErroMotivo(undefined);
    try {
      await agir.mutateAsync({ id: alvoId, tipo, motivo: motivo.trim(), procedente: true });
      notificar("Ação aplicada.", "sucesso");
      setAlvoId(null);
    } catch (e) {
      notificar(e instanceof api.ApiError ? e.message : "Não foi possível aplicar a ação.", "erro");
    }
  }

  const totalPaginas = lista.data ? Math.max(1, Math.ceil(lista.data.count / Math.max(1, lista.data.results.length))) : 1;

  return (
    <section className="grid gap-6" aria-labelledby="admin-mod-titulo">
      <div className="grid gap-1">
        <h1 id="admin-mod-titulo" className="font-[var(--fonte-titulo)] text-2xl font-bold tracking-tight text-balance text-[var(--cor-texto)]">
          Moderação
        </h1>
        <p className="text-sm text-[var(--cor-texto-suave)]">Trate as denúncias da comunidade e aplique a ação adequada.</p>
      </div>
      <Card>
        <CardContent className="flex flex-wrap items-end gap-3 pt-6">
          <div className="min-w-[200px] max-w-xs flex-1">
            <CampoSelecao
              id="admin-mod-status"
              name="admin-mod-status"
              rotulo="Status"
              value={statusFiltro}
              onChange={(e) => {
                setStatusFiltro(e.target.value);
                setPage(1);
              }}
            >
              <option value="">todos</option>
              <option value="pendente">pendente</option>
              <option value="procedente">procedente</option>
              <option value="improcedente">improcedente</option>
            </CampoSelecao>
          </div>
          <div className="min-w-[200px] max-w-xs flex-1">
            <CampoSelecao
              id="admin-mod-ordem"
              name="admin-mod-ordem"
              rotulo="Ordenar por data"
              value={ordem}
              onChange={(e) => setOrdem(e.target.value as "recentes" | "antigos")}
            >
              <option value="recentes">Mais recentes</option>
              <option value="antigos">Mais antigas</option>
            </CampoSelecao>
          </div>
        </CardContent>
      </Card>

      {lista.isLoading && <SkeletonLista quantidade={3} />}
      {lista.isError && <ErrorState mensagem="Erro ao carregar denúncias." aoTentarNovamente={() => void lista.refetch()} />}
      {lista.data && (
        <div aria-live="polite">
          <DataTable
            legenda="Denúncias"
            linhas={linhas}
            colunas={[
              { cabecalho: "#", render: (d) => String(d.id) },
              { cabecalho: "Motivo", render: (d) => <span className="line-clamp-2 max-w-[28ch] text-sm">{d.motivo}</span> },
              {
                cabecalho: "Status",
                render: (d) => (
                  <Badge variant={d.status === "pendente" ? "secondary" : d.status === "procedente" ? "destructive" : "success"}>
                    {d.status}
                  </Badge>
                ),
              },
              { cabecalho: "Denunciante", render: (d) => d.denunciante_email },
              { cabecalho: "Alvo", render: (d) => d.alvo_repr ?? "—" },
              { cabecalho: "Data", render: (d) => formatarData(d.criado_em) },
              { cabecalho: "Ação", render: (d) => <Button tamanho="pequeno" loading={agir.isPending} onClick={() => abrirDialogo(d.id)}>Aplicar ação</Button> },
            ]}
            pagina={page}
            totalPaginas={totalPaginas}
            aoMudarPagina={setPage}
          />
        </div>
      )}

      <Dialog open={alvoId !== null} onOpenChange={(aberto) => !aberto && setAlvoId(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Aplicar ação na denúncia #{alvoId}</DialogTitle>
            <DialogDescription>Escolha o tipo de ação e registre o motivo. A decisão fica no histórico.</DialogDescription>
          </DialogHeader>
          <form onSubmit={aplicarAcao} noValidate className="grid gap-4">
            <div className="grid gap-1.5">
              <Label htmlFor="moderacao-tipo">Tipo de ação</Label>
              <Select value={tipo} onValueChange={setTipo}>
                <SelectTrigger id="moderacao-tipo" className="text-[16px] sm:text-sm">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {TIPOS_ACAO.map((t) => (
                    <SelectItem key={t} value={t}>
                      {t}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="moderacao-motivo">Motivo</Label>
              <Textarea
                id="moderacao-motivo"
                name="moderacao-motivo"
                rows={3}
                placeholder="Descreva o motivo da ação…"
                value={motivo}
                aria-invalid={Boolean(erroMotivo)}
                aria-describedby={erroMotivo ? "moderacao-motivo-erro" : undefined}
                onChange={(e) => setMotivo(e.target.value)}
              />
              {erroMotivo && (
                <p id="moderacao-motivo-erro" role="alert" className="text-xs font-medium text-[var(--cor-erro)]">
                  {erroMotivo}
                </p>
              )}
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setAlvoId(null)} disabled={agir.isPending}>
                Cancelar
              </Button>
              <Button type="submit" variant="destructive" loading={agir.isPending}>
                Aplicar ação
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </section>
  );
}
