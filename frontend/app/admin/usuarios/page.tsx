"use client";
import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { useAuth } from "@/lib/auth-context";
import * as api from "@/lib/api";
import { useQueryAdminUsuarios } from "@/lib/queries";
import { queryKeys } from "@/lib/query-keys";
import { formatarDataCurta } from "@/lib/datas";
import { Ban, CheckCircle2, Plus, Search, ShieldCheck, UserPlus } from "lucide-react";

const PAPEIS = ["free", "premium", "admin"] as const;

export default function Page() {
  const { usuario, token, carregando } = useAuth();
  const r = useRouter();
  const cliente = useQueryClient();

  useEffect(() => {
    if (!carregando && !token) r.replace("/login");
  }, [carregando, token, r]);

  const [busca, setBusca] = useState("");
  const [buscaAplicada, setBuscaAplicada] = useState<string | null>(null);
  const [papelFiltro, setPapelFiltro] = useState<string>("todos");
  const [page, setPage] = useState(1);
  const [erroMutacao, setErroMutacao] = useState<string | null>(null);
  const [mutandoId, setMutandoId] = useState<number | null>(null);

  // A tela só carrega após o clique em "Buscar" (buscaAplicada sai de null)
  // — mesmo padrão das outras telas de decisão da Central.
  const consulta = useQueryAdminUsuarios({
    token,
    usuarioId: usuario?.id ?? 0,
    busca: buscaAplicada,
    papel: papelFiltro === "todos" ? null : papelFiltro,
    page,
    habilitada: buscaAplicada !== null,
  });
  const itens = consulta.data?.results ?? [];
  const total = consulta.data?.count ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / 20));
  const loading = consulta.isFetching;
  const err = consulta.isError
    ? consulta.error instanceof Error
      ? consulta.error.message
      : "Falha ao carregar — tente novamente"
    : erroMutacao;

  const buscar = () => {
    setErroMutacao(null);
    setPage(1);
    setBuscaAplicada(busca || "");
  };

  const invalidar = () => cliente.invalidateQueries({ queryKey: queryKeys.admin.usuariosRaiz() });

  const alterarPapel = async (id: number, papel: string) => {
    setMutandoId(id);
    setErroMutacao(null);
    try {
      await api.adminAtualizarUsuario(token || "", id, { papel });
      await invalidar();
    } catch (e: unknown) {
      setErroMutacao(e instanceof Error ? e.message : "Falha ao alterar papel.");
    } finally {
      setMutandoId(null);
    }
  };

  const alternarBloqueio = async (u: api.AdminUsuario) => {
    setMutandoId(u.id);
    setErroMutacao(null);
    try {
      await api.adminAtualizarUsuario(token || "", u.id, { is_active: !u.is_active });
      await invalidar();
    } catch (e: unknown) {
      setErroMutacao(e instanceof Error ? e.message : "Falha ao bloquear/desbloquear.");
    } finally {
      setMutandoId(null);
    }
  };

  // --- Criação de usuário (C-01) ---
  const [criarAberto, setCriarAberto] = useState(false);
  const [novoEmail, setNovoEmail] = useState("");
  const [novoNome, setNovoNome] = useState("");
  const [novaSenha, setNovaSenha] = useState("");
  const [novoPapel, setNovoPapel] = useState<string>("free");
  const [criando, setCriando] = useState(false);
  const [erroCriacao, setErroCriacao] = useState<string | null>(null);

  const criarUsuario = async () => {
    setErroCriacao(null);
    if (!novoEmail.trim() || !novaSenha.trim()) {
      setErroCriacao("E-mail e senha são obrigatórios.");
      return;
    }
    setCriando(true);
    try {
      await api.adminCriarUsuario(token || "", {
        email: novoEmail.trim(),
        nome: novoNome.trim(),
        senha: novaSenha,
        papel: novoPapel as "free" | "premium" | "admin",
      });
      setCriarAberto(false);
      setNovoEmail("");
      setNovoNome("");
      setNovaSenha("");
      setNovoPapel("free");
      await invalidar();
    } catch (e: unknown) {
      setErroCriacao(e instanceof Error ? e.message : "Falha ao criar usuário.");
    } finally {
      setCriando(false);
    }
  };

  if (usuario && usuario.papel !== "admin") {
    return (
      <div className="mx-auto max-w-xl py-8">
        <Card className="border-[var(--cor-erro)] bg-[var(--cor-erro-suave)]">
          <CardContent className="p-6 text-center">
            <p className="text-sm text-[var(--cor-erro)]">Acesso restrito a admin.</p>
            <Link href="/" className="text-sm text-[var(--cor-primaria)] underline">
              Voltar
            </Link>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <Card className="bento border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
        <CardHeader>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <CardTitle>Usuários</CardTitle>
              <CardDescription className="text-[var(--cor-texto-suave)]">Busca, filtro por papel, promoção, bloqueio e criação de contas.</CardDescription>
            </div>
            <Button onClick={() => setCriarAberto(true)} className="min-h-[40px] gap-1.5 bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]">
              <UserPlus className="h-4 w-4" /> Criar usuário
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex flex-wrap gap-2">
            <div className="relative min-w-[200px] flex-1">
              <Search className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--cor-texto-suave)]" />
              <Input
                placeholder="Buscar por e-mail ou nome..."
                value={busca}
                onChange={(e) => setBusca(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && buscar()}
                className="bg-[var(--cor-fundo-card)] pl-8"
              />
            </div>
            <Select value={papelFiltro} onValueChange={(v) => { setPapelFiltro(v); setPage(1); }}>
              <SelectTrigger className="w-[160px] bg-[var(--cor-fundo-card)]"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="todos">Todos os papéis</SelectItem>
                {PAPEIS.map((p) => (
                  <SelectItem key={p} value={p}>{p}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button onClick={buscar} disabled={loading} className="min-h-[40px] bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]">
              {loading ? "Buscando..." : "Buscar"}
            </Button>
          </div>
          {err && <p className="rounded-md border border-[var(--cor-erro)] bg-[var(--cor-erro-suave)] px-3 py-2 text-sm text-[var(--cor-erro)]">{err}</p>}

          <div className="grid gap-2">
            {itens.map((u) => (
              <div key={u.id} className="flex flex-col gap-2 rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] p-3 md:flex-row md:items-center md:justify-between">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="truncate font-medium text-[var(--cor-texto)]">{u.email}</p>
                    {!u.is_active && (
                      <Badge variant="outline" className="border-[var(--cor-erro)] text-[var(--cor-erro)]">bloqueado</Badge>
                    )}
                    {!u.email_verificado && (
                      <Badge variant="outline" className="border-[var(--cor-borda)] text-[var(--cor-texto-suave)]">e-mail não verificado</Badge>
                    )}
                  </div>
                  <p className="truncate text-xs text-[var(--cor-texto-suave)]">{u.nome || "—"} · desde {formatarDataCurta(u.date_joined)}</p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <Select
                    value={u.papel}
                    onValueChange={(v) => alterarPapel(u.id, v)}
                  >
                    <SelectTrigger className="h-9 w-[130px] bg-[var(--cor-fundo-card)]" disabled={mutandoId === u.id}>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {PAPEIS.map((p) => (
                        <SelectItem key={p} value={p}>{p}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={mutandoId === u.id}
                    onClick={() => alternarBloqueio(u)}
                    className={u.is_active ? "border-[var(--cor-erro)] text-[var(--cor-erro)]" : "border-[var(--cor-sucesso)] text-[var(--cor-sucesso)]"}
                  >
                    {u.is_active ? (
                      <><Ban className="mr-1 h-3.5 w-3.5" /> Bloquear</>
                    ) : (
                      <><CheckCircle2 className="mr-1 h-3.5 w-3.5" /> Desbloquear</>
                    )}
                  </Button>
                </div>
              </div>
            ))}
            {!itens.length && !loading && buscaAplicada !== null && (
              <p className="text-sm text-[var(--cor-texto-suave)]">Nenhum usuário encontrado para os filtros atuais.</p>
            )}
            {!itens.length && buscaAplicada === null && (
              <p className="text-sm text-[var(--cor-texto-suave)]">Clique em Buscar para carregar.</p>
            )}
          </div>

          {total > 0 && (
            <div className="flex flex-wrap items-center justify-between gap-2 border-t border-[var(--cor-borda)] pt-3">
              <div className="flex gap-2">
                <Button size="sm" variant="outline" disabled={page <= 1 || loading} onClick={() => setPage((p) => Math.max(1, p - 1))}>← Anterior</Button>
                <Button size="sm" variant="outline" disabled={page >= totalPages || loading} onClick={() => setPage((p) => p + 1)}>Próxima →</Button>
              </div>
              <span className="text-xs text-[var(--cor-texto-suave)]">Página {page} de {totalPages} · {total} usuários</span>
            </div>
          )}
        </CardContent>
      </Card>

      <Dialog open={criarAberto} onOpenChange={(o) => { setCriarAberto(o); if (!o) setErroCriacao(null); }}>
        <DialogContent className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2"><Plus className="h-4 w-4 text-[var(--cor-primaria)]" /> Criar usuário</DialogTitle>
            <DialogDescription>A conta é criada com e-mail já verificado e senha temporária — o usuário troca a senha no primeiro login.</DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div className="space-y-1"><Label htmlFor="novo-email">E-mail *</Label><Input id="novo-email" type="email" value={novoEmail} onChange={(e) => setNovoEmail(e.target.value)} placeholder="pessoa@exemplo.com" /></div>
            <div className="space-y-1"><Label htmlFor="novo-nome">Nome</Label><Input id="novo-nome" value={novoNome} onChange={(e) => setNovoNome(e.target.value)} placeholder="Nome completo" /></div>
            <div className="space-y-1"><Label htmlFor="nova-senha">Senha temporária *</Label><Input id="nova-senha" type="password" value={novaSenha} onChange={(e) => setNovaSenha(e.target.value)} placeholder="mín. 8 caracteres" /></div>
            <div className="space-y-1">
              <Label>Papel inicial</Label>
              <Select value={novoPapel} onValueChange={setNovoPapel}>
                <SelectTrigger className="bg-[var(--cor-fundo-elevado)]"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {PAPEIS.map((p) => (
                    <SelectItem key={p} value={p}>{p}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            {erroCriacao && <p role="alert" className="rounded-md border border-[var(--cor-erro)] bg-[var(--cor-erro-suave)] px-3 py-2 text-sm text-[var(--cor-erro)]">{erroCriacao}</p>}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCriarAberto(false)} className="min-h-[44px]">Cancelar</Button>
            <Button onClick={criarUsuario} disabled={criando} className="min-h-[44px] gap-1.5 bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]">
              <ShieldCheck className="h-4 w-4" /> {criando ? "Criando..." : "Criar usuário"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
